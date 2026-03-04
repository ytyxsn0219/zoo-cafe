"""Model gateway using LiteLLM for unified API access."""

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import litellm

from ..utils.logger import get_logger
from ..utils.token_counter import TokenCounter

logger = get_logger("model_gateway")


@dataclass
class ModelResponse:
    """Standardized model response."""

    content: str
    model: str
    token_usage: int
    latency_ms: float
    raw_response: Any
    tool_calls: Optional[list[dict[str, Any]]] = None


@dataclass
class ToolCallResult:
    """Result of a tool execution."""

    tool_name: str
    result: Any
    error: Optional[str] = None


class ModelGateway:
    """Unified gateway for multiple LLM providers using LiteLLM."""

    def __init__(self):
        """Initialize the model gateway."""
        self._token_counter = TokenCounter()
        # Configure litellm
        litellm.drop_params = True
        litellm.set_verbose = False

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 60,
        **kwargs: Any,
    ) -> ModelResponse:
        """
        Send chat completion request.

        Args:
            model: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet")
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional model-specific parameters

        Returns:
            ModelResponse with content and metadata
        """
        start_time = asyncio.get_event_loop().time()

        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                ),
                timeout=timeout,
            )

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            content = response.choices[0].message.content or ""
            token_usage = response.usage.total_tokens if response.usage else 0

            logger.debug(
                "model_response",
                model=model,
                tokens=token_usage,
                latency_ms=round(latency_ms, 2),
            )

            return ModelResponse(
                content=content,
                model=model,
                token_usage=token_usage,
                latency_ms=latency_ms,
                raw_response=response,
            )

        except asyncio.TimeoutError:
            logger.error("model_timeout", model=model, timeout=timeout)
            raise TimeoutError(f"Model request timed out after {timeout}s")

        except litellm.exceptions.APIError as e:
            logger.error("model_api_error", model=model, error=str(e))
            raise

        except Exception as e:
            logger.error("model_request_failed", model=model, error=str(e))
            raise

    async def chat_completion_with_retry(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        **kwargs: Any,
    ) -> ModelResponse:
        """
        Send chat completion request with retry logic.

        Args:
            model: Model identifier
            messages: List of message dicts
            max_attempts: Maximum retry attempts
            backoff_factor: Exponential backoff multiplier
            **kwargs: Additional parameters

        Returns:
            ModelResponse
        """
        timeout = kwargs.get("timeout", 60)
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                return await self.chat_completion(
                    model=model,
                    messages=messages,
                    **kwargs,
                )
            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    wait_time = timeout * (backoff_factor ** (attempt - 1))
                    logger.warning(
                        "model_retry",
                        model=model,
                        attempt=attempt,
                        wait_seconds=wait_time,
                        error=str(e),
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "model_max_retries_exceeded",
                        model=model,
                        attempts=max_attempts,
                        error=str(e),
                    )

        raise last_error or Exception("Max retries exceeded")

    async def chat_completion_with_tools(
        self,
        model: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
        max_tool_calls: int = 5,
        **kwargs: Any,
    ) -> tuple[ModelResponse, list[dict[str, Any]]]:
        """
        Send chat completion request with tools.

        Args:
            model: Model identifier
            messages: Message list
            tools: Tool definitions
            tool_choice: Tool choice strategy ("auto", "none", or {"type": "function", "function": {"name": "xxx"}})
            max_tool_calls: Maximum number of tool calls per request
            **kwargs: Additional parameters

        Returns:
            Tuple of (ModelResponse, tool_calls)
        """
        start_time = asyncio.get_event_loop().time()

        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    **kwargs,
                ),
                timeout=kwargs.get("timeout", 60),
            )

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            # Extract content and tool calls
            message = response.choices[0].message
            content = message.content or ""
            token_usage = response.usage.total_tokens if response.usage else 0

            # Extract tool calls
            tool_calls = []
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls[:max_tool_calls]:
                    tool_calls.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })

            logger.debug(
                "model_response_with_tools",
                model=model,
                tokens=token_usage,
                tool_calls=len(tool_calls),
                latency_ms=round(latency_ms, 2),
            )

            return (
                ModelResponse(
                    content=content,
                    model=model,
                    token_usage=token_usage,
                    latency_ms=latency_ms,
                    raw_response=response,
                    tool_calls=tool_calls,
                ),
                tool_calls
            )

        except asyncio.TimeoutError:
            logger.error("model_timeout", model=model)
            raise TimeoutError(f"Model request timed out")

        except Exception as e:
            logger.error("model_request_failed", model=model, error=str(e))
            raise

    async def chat_completion_with_function_calling(
        self,
        model: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        execute_tool_func: callable,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> ModelResponse:
        """
        Execute chat completion with function calling (auto tool execution).

        This method will:
        1. Send message to model with tools
        2. If model requests tool call, execute the tool
        3. Add tool result to messages and continue
        4. Repeat until no more tool calls or max iterations reached

        Args:
            model: Model identifier
            messages: Message list (will be modified during execution)
            tools: Tool definitions
            execute_tool_func: Async function to execute tools (tool_name, arguments) -> result
            max_iterations: Maximum tool call iterations
            **kwargs: Additional parameters

        Returns:
            Final ModelResponse
        """
        current_messages = messages.copy()

        for iteration in range(max_iterations):
            response, tool_calls = await self.chat_completion_with_tools(
                model=model,
                messages=current_messages,
                tools=tools,
                **kwargs
            )

            # If no tool calls, return the response
            if not tool_calls:
                return response

            # Execute each tool call and add results
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                arguments_str = tc["function"]["arguments"]

                # Parse arguments
                import json
                try:
                    arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    arguments = {"raw": arguments_str}

                # Execute tool
                try:
                    result = await execute_tool_func(tool_name, arguments)
                    logger.info("tool_executed", tool=tool_name, iteration=iteration)
                except Exception as e:
                    logger.error("tool_execution_failed", tool=tool_name, error=str(e))
                    result = {"error": str(e)}

                # Add tool result to messages
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result) if not isinstance(result, str) else result
                })

            # Continue loop to get final response after tool execution

        logger.warning("max_tool_iterations_reached", iterations=max_iterations)
        return response


# Global gateway instance
_gateway: Optional[ModelGateway] = None


def get_gateway() -> ModelGateway:
    """Get global model gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = ModelGateway()
    return _gateway


async def chat_completion(
    model: str,
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> ModelResponse:
    """
    Convenience function for chat completion.

    Args:
        model: Model identifier
        messages: Message list
        **kwargs: Additional parameters

    Returns:
        ModelResponse
    """
    gateway = get_gateway()
    return await gateway.chat_completion(model, messages, **kwargs)
