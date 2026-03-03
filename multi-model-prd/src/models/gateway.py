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
