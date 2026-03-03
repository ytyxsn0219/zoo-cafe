"""Agent registry and factory."""

from typing import Any, Optional

from ..models.registry import resolve_model_string
from ..utils.config import get_agents_config
from ..utils.logger import get_logger
from .base import AgentConfig, BaseAgent

logger = get_logger("agent_registry")


class AgentRegistry:
    """Registry for managing agents."""

    def __init__(self):
        """Initialize agent registry."""
        self._agents: dict[str, BaseAgent] = {}
        self._moderator: Optional[BaseAgent] = None

    def load_from_config(self) -> None:
        """Load agents from configuration."""
        agents_config = get_agents_config()

        for agent_data in agents_config:
            if not agent_data.get("enabled", True):
                continue

            config = AgentConfig(
                name=agent_data.get("name", ""),
                model_ref=agent_data.get("model_ref", ""),
                display_name=agent_data.get("display_name", ""),
                description=agent_data.get("description", ""),
                is_moderator=agent_data.get("is_moderator", False),
                enabled=agent_data.get("enabled", True),
            )

            agent = UniversalAgent(config)
            self._agents[config.name] = agent

            if config.is_moderator:
                self._moderator = agent

            logger.debug(
                "agent_loaded",
                name=config.name,
                is_moderator=config.is_moderator,
            )

    def get(self, name: str) -> Optional[BaseAgent]:
        """
        Get agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None
        """
        return self._agents.get(name)

    def get_moderator(self) -> Optional[BaseAgent]:
        """Get moderator agent."""
        return self._moderator

    def get_all_agents(self) -> list[BaseAgent]:
        """Get all registered agents (excluding moderator)."""
        return [
            agent for agent in self._agents.values()
            if not agent.is_moderator
        ]

    def get_all_including_moderator(self) -> list[BaseAgent]:
        """Get all agents including moderator."""
        return list(self._agents.values())

    def list_agent_names(self) -> list[str]:
        """List all agent names."""
        return list(self._agents.keys())


class UniversalAgent(BaseAgent):
    """Universal agent that can take on any role."""

    pass


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get global agent registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
        _registry.load_from_config()
    return _registry


def get_moderator() -> Optional[BaseAgent]:
    """Get moderator agent."""
    registry = get_agent_registry()
    return registry.get_moderator()


def get_participants() -> list[BaseAgent]:
    """Get all participant agents (excluding moderator)."""
    registry = get_agent_registry()
    return registry.get_all_agents()


def get_all_agents() -> list[BaseAgent]:
    """Get all agents including moderator."""
    registry = get_agent_registry()
    return registry.get_all_including_moderator()


def create_agent(config: AgentConfig) -> UniversalAgent:
    """
    Create a new agent instance.

    Args:
        config: Agent configuration

    Returns:
        UniversalAgent instance
    """
    return UniversalAgent(config)
