"""Tests for model gateway."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.gateway import ModelGateway, ModelResponse


class TestModelGateway:
    """Test cases for ModelGateway."""

    @pytest.fixture
    def gateway(self) -> ModelGateway:
        """Create gateway instance."""
        return ModelGateway()

    @pytest.mark.asyncio
    async def test_gateway_initialization(self, gateway: ModelGateway) -> None:
        """Test gateway initializes correctly."""
        assert gateway is not None

    @pytest.mark.asyncio
    @patch("src.models.gateway.litellm")
    async def test_chat_completion(
        self,
        mock_litellm: MagicMock,
        gateway: ModelGateway,
        mock_model_response: dict[str, Any],
    ) -> None:
        """Test chat completion call."""
        # Mock the litellm response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.total_tokens = 100
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ]

        response = await gateway.chat_completion(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        assert response.content == "Test response"
        assert response.token_usage == 100
        assert response.model == "gpt-4o"

    @pytest.mark.asyncio
    @patch("src.models.gateway.litellm")
    async def test_chat_completion_timeout(
        self,
        mock_litellm: MagicMock,
        gateway: ModelGateway,
    ) -> None:
        """Test chat completion timeout handling."""
        import asyncio

        mock_litellm.acompletion = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(TimeoutError):
            await gateway.chat_completion(
                model="gpt-4o",
                messages=messages,
                timeout=1,
            )


class TestModelResponse:
    """Test cases for ModelResponse dataclass."""

    def test_model_response_creation(self) -> None:
        """Test ModelResponse can be created."""
        response = ModelResponse(
            content="Test content",
            model="gpt-4o",
            token_usage=100,
            latency_ms=500.0,
            raw_response={},
        )

        assert response.content == "Test content"
        assert response.model == "gpt-4o"
        assert response.token_usage == 100
        assert response.latency_ms == 500.0
