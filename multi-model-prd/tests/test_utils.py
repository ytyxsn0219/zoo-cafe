"""Tests for utility modules."""

import pytest

from src.utils.token_counter import TokenCounter
from src.utils.config import Settings


class TestTokenCounter:
    """Test cases for TokenCounter."""

    def test_token_counter_initialization(self) -> None:
        """Test TokenCounter can be initialized."""
        counter = TokenCounter(model="gpt-4o")
        assert counter.model == "gpt-4o"

    def test_count_tokens(self) -> None:
        """Test token counting."""
        counter = TokenCounter()

        # Test with simple text
        text = "Hello, world!"
        count = counter.count(text)

        assert count > 0
        assert isinstance(count, int)

    def test_count_messages(self) -> None:
        """Test message counting."""
        counter = TokenCounter()

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        count = counter.count_messages(messages)

        assert count > 0
        assert isinstance(count, int)


class TestConfig:
    """Test cases for configuration."""

    def test_settings_defaults(self) -> None:
        """Test Settings default values."""
        settings = Settings()

        assert settings.debug is False
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.redis_url == "redis://localhost:6379/0"
