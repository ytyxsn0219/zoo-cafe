"""Tests for agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.base import AgentConfig, AgentMessage, UniversalAgent


class TestAgentConfig:
    """Test cases for AgentConfig."""

    def test_agent_config_creation(self) -> None:
        """Test AgentConfig can be created."""
        config = AgentConfig(
            name="test_agent",
            model_ref="gpt4o_model",
            display_name="Test Agent",
            description="A test agent",
        )

        assert config.name == "test_agent"
        assert config.model_ref == "gpt4o_model"
        assert config.display_name == "Test Agent"
        assert config.enabled is True

    def test_agent_config_with_moderator(self) -> None:
        """Test AgentConfig for moderator."""
        config = AgentConfig(
            name="moderator",
            model_ref="cheap_model",
            display_name="主持人",
            description="Discussion moderator",
            is_moderator=True,
        )

        assert config.is_moderator is True


class TestAgentMessage:
    """Test cases for AgentMessage."""

    def test_agent_message_creation(self) -> None:
        """Test AgentMessage can be created."""
        message = AgentMessage(
            agent_name="agent_01",
            agent_role="product_manager",
            content="This is my proposal.",
            model_used="gpt-4o",
            stage="elicitation",
            round_num=1,
            token_usage=150,
        )

        assert message.agent_name == "agent_01"
        assert message.agent_role == "product_manager"
        assert message.content == "This is my proposal."
        assert message.stage == "elicitation"
        assert message.round_num == 1

    def test_agent_message_to_dict(self) -> None:
        """Test AgentMessage to_dict conversion."""
        message = AgentMessage(
            agent_name="agent_01",
            agent_role="product_manager",
            content="Test content",
            model_used="gpt-4o",
        )

        data = message.to_dict()

        assert data["agent_name"] == "agent_01"
        assert data["agent_role"] == "product_manager"
        assert "timestamp" in data


class TestUniversalAgent:
    """Test cases for UniversalAgent."""

    @pytest.fixture
    def agent_config(self) -> AgentConfig:
        """Create test agent config."""
        return AgentConfig(
            name="test_agent",
            model_ref="gpt4o_model",
            display_name="Test Agent",
            description="A test agent",
        )

    @pytest.fixture
    def agent(self, agent_config: AgentConfig) -> UniversalAgent:
        """Create test agent."""
        return UniversalAgent(agent_config)

    def test_agent_initialization(self, agent: UniversalAgent) -> None:
        """Test agent initializes correctly."""
        assert agent.name == "test_agent"
        assert agent.display_name == "Test Agent"
        assert agent.is_moderator is False

    def test_agent_get_system_prompt(self, agent: UniversalAgent) -> None:
        """Test agent can get system prompt."""
        # Should load from template
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)

    def test_agent_history(self, agent: UniversalAgent) -> None:
        """Test agent history management."""
        assert agent.get_history() == []

        agent._history.append({"role": "user", "content": "Hello"})
        assert len(agent.get_history()) == 1

        agent.reset_history()
        assert agent.get_history() == []
