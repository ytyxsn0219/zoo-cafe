"""Token counting utilities using tiktoken."""

from typing import Optional

try:
    import tiktoken
except ImportError:
    tiktoken = None

from .logger import get_logger

logger = get_logger("token_counter")


class TokenCounter:
    """Token counter using tiktoken for OpenAI models."""

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize token counter for a specific model.

        Args:
            model: Model name to use for encoding
        """
        self.model = model
        self._encoder: Optional[Any] = None
        self._init_encoder()

    def _init_encoder(self) -> None:
        """Initialize the tiktoken encoder."""
        if tiktoken is None:
            logger.warning("tiktoken not installed, token counting will use estimation")
            return

        try:
            # Map model names to tiktoken encodings
            encoding_name = self._get_encoding_name(self.model)
            self._encoder = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning("failed to initialize tiktoken encoder", error=str(e))
            self._encoder = None

    @staticmethod
    def _get_encoding_name(model: str) -> str:
        """Map model name to tiktoken encoding name."""
        model_lower = model.lower()

        if "gpt-4" in model_lower or "gpt3.5" in model_lower:
            return "cl100k_base"
        elif "gpt-3" in model_lower:
            return "p50k_base"
        elif "claude" in model_lower:
            return "cl100k_base"
        else:
            return "cl100k_base"

    def count(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if self._encoder is None:
            # Fallback: rough estimate (~4 characters per token)
            return len(text) // 4

        try:
            return len(self._encoder.encode(text))
        except Exception as e:
            logger.warning("token counting failed, using estimation", error=str(e))
            return len(text) // 4

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """
        Count tokens for a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys

        Returns:
            Total token count
        """
        # Add overhead for message formatting (approximately 4 tokens per message)
        overhead = len(messages) * 4

        content_tokens = sum(self.count(msg.get("content", "")) for msg in messages)

        return overhead + content_tokens


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Convenience function to count tokens for a text.

    Args:
        text: Text to count
        model: Model name

    Returns:
        Token count
    """
    counter = TokenCounter(model)
    return counter.count(text)
