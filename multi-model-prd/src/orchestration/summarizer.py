"""Context summarization for long discussions."""

from typing import Any, Optional

from ..models.gateway import get_gateway
from ..models.registry import resolve_model_string
from ..utils.logger import get_logger
from ..utils.prompt_loader import get_prompt_loader
from ..utils.token_counter import TokenCounter

logger = get_logger("summarizer")


class ContextSummarizer:
    """Summarize long discussion contexts."""

    def __init__(self, max_tokens: int = 100000):
        """
        Initialize context summarizer.

        Args:
            max_tokens: Maximum tokens before compression
        """
        self.max_tokens = max_tokens
        self._token_counter = TokenCounter()
        self._gateway = get_gateway()

    def should_compress(self, messages: list[dict[str, str]], trigger_after: int = 5) -> bool:
        """
        Check if context should be compressed.

        Args:
            messages: Current context messages
            trigger_after: Trigger after this many messages

        Returns:
            True if compression is needed
        """
        return len(messages) >= trigger_after

    async def summarize(
        self,
        messages: list[dict[str, str]],
        stage: str,
        model_ref: str = "cheap_model",
    ) -> list[dict[str, str]]:
        """
        Summarize context messages.

        Args:
            messages: Messages to summarize
            stage: Current stage
            model_ref: Model to use for summarization

        Returns:
            Summarized messages
        """
        if len(messages) < 3:
            return messages

        logger.info(
            "compressing_context",
            message_count=len(messages),
            stage=stage,
        )

        # Build summary prompt
        loader = get_prompt_loader()
        summary_template = """
请总结以下讨论的要点，保留关键信息和决策。

讨论上下文：
{context}

请用简洁的段落总结：
1. 主要讨论内容
2. 达成的一致意见
3. 未解决的问题
4. 下一步建议
"""

        # Format context
        context_text = self._format_messages(messages)
        summary_prompt = summary_template.format(context=context_text)

        # Call model
        model_string = resolve_model_string(model_ref)

        if not model_string:
            logger.warning("summarizer_model_not_found, using default")
            model_string = "openai/gpt-4o-mini"

        try:
            response = await self._gateway.chat_completion(
                model=model_string,
                messages=[
                    {"role": "system", "content": "你是一个专业的讨论总结助手。"},
                    {"role": "user", "content": summary_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                timeout=30,
            )

            summary = response.content

            logger.info(
                "context_compressed",
                original_messages=len(messages),
                summary_tokens=response.token_usage,
            )

            # Return summarized context
            return [
                {"role": "system", "content": f"【讨论摘要 - {stage}阶段】\n{summary}"}
            ]

        except Exception as e:
            logger.error("summarization_failed", error=str(e))
            # Fallback: keep last few messages
            return messages[-5:]

    def _format_messages(self, messages: list[dict[str, str]]) -> str:
        """Format messages for summarization."""
        formatted = []

        for msg in messages:
            role = msg.get("role", "assistant")
            name = msg.get("name", "")
            content = msg.get("content", "")

            if name:
                formatted.append(f"{name} ({role}): {content}")
            else:
                formatted.append(f"{role}: {content}")

        return "\n\n".join(formatted)

    def count_tokens(self, messages: list[dict[str, str]]) -> int:
        """Count total tokens in messages."""
        return self._token_counter.count_messages(messages)


def create_summarizer() -> ContextSummarizer:
    """Create context summarizer with config."""
    from ..utils.config import get_discussion_config

    config = get_discussion_config()
    compression_config = config.get("context_compression", {})
    max_tokens = compression_config.get("max_context_tokens", 100000)

    return ContextSummarizer(max_tokens=max_tokens)
