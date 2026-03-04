"""Base agent implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..models.gateway import ModelGateway, get_gateway
from ..models.registry import ModelRegistry, get_model_registry
from ..utils.logger import get_agent_logger
from ..utils.prompt_loader import get_prompt_loader
from ..tools import get_tool_registry


@dataclass
class AgentMessage:
    """Agent message in a discussion."""

    agent_name: str
    agent_role: str
    content: str
    model_used: str
    stage: str = ""
    round_num: int = 0
    token_usage: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "content": self.content,
            "model_used": self.model_used,
            "stage": self.stage,
            "round_num": self.round_num,
            "token_usage": self.token_usage,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AgentConfig:
    """Agent configuration."""

    name: str
    model_ref: str
    display_name: str
    description: str
    system_prompt: str = ""
    is_moderator: bool = False
    enabled: bool = True
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    enabled_tools: Optional[list[str]] = None  # 启用的工具列表


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, config: AgentConfig, session_id: Optional[str] = None):
        """
        Initialize base agent.

        Args:
            config: Agent configuration
            session_id: Optional session ID for logging
        """
        self.config = config
        self.session_id = session_id
        self._gateway: Optional[ModelGateway] = None
        self._registry: Optional[ModelRegistry] = None
        self._history: list[dict[str, str]] = []
        self._logger = get_agent_logger(config.name, session_id)

    @property
    def gateway(self) -> ModelGateway:
        """Get model gateway."""
        if self._gateway is None:
            self._gateway = get_gateway()
        return self._gateway

    @property
    def registry(self) -> ModelRegistry:
        """Get model registry."""
        if self._registry is None:
            self._registry = get_model_registry()
        return self._registry

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.config.name

    @property
    def display_name(self) -> str:
        """Get agent display name."""
        return self.config.display_name

    @property
    def is_moderator(self) -> bool:
        """Check if agent is moderator."""
        return self.config.is_moderator

    def get_system_prompt(self) -> str:
        """
        Get agent system prompt.

        Returns:
            System prompt string
        """
        if self.config.system_prompt:
            return self.config.system_prompt

        # Load from prompt templates
        loader = get_prompt_loader()
        template_name = "moderator" if self.is_moderator else "universal_agent"
        data = loader.load(template_name)

        return data.get("system_prompt", "")

    async def speak(
        self,
        context: list[dict[str, str]],
        stage: str = "",
        round_num: int = 0,
        role_hint: Optional[str] = None,
    ) -> AgentMessage:
        """
        Agent speaks in the discussion.

        Args:
            context: Discussion context (previous messages)
            stage: Current discussion stage
            round_num: Current round number
            role_hint: Optional role hint for the agent

        Returns:
            AgentMessage with response
        """
        # Build messages
        system_prompt = self.get_system_prompt()

        # Add role hint if provided
        if role_hint:
            system_prompt += f"\n\n当前任务：{role_hint}"

        messages = [
            {"role": "system", "content": system_prompt}
        ] + context

        # Get model string
        model_string = self.registry.get_model_string(self.config.model_ref)

        if not model_string:
            self._logger.error("model_not_found", model_ref=self.config.model_ref)
            raise ValueError(f"Model not found: {self.config.model_ref}")

        self._logger.debug(
            "agent_speaking",
            model=model_string,
            stage=stage,
            round=round_num,
        )

        # Call model
        response = await self.gateway.chat_completion_with_retry(
            model=model_string,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
        )

        # Create message
        message = AgentMessage(
            agent_name=self.config.name,
            agent_role=role_hint or "participant",
            content=response.content,
            model_used=self.config.model_ref,
            stage=stage,
            round_num=round_num,
            token_usage=response.token_usage,
        )

        # Add to history
        self._history.append({
            "role": "assistant",
            "name": self.config.name,
            "content": response.content,
        })

        self._logger.info(
            "agent_response",
            token_usage=response.token_usage,
            latency_ms=round(response.latency_ms, 2),
        )

        return message

    async def speak_with_tools(
        self,
        context: list[dict[str, str]],
        stage: str = "",
        round_num: int = 0,
        role_hint: Optional[str] = None,
    ) -> AgentMessage:
        """
        Agent speaks with tool calling capability.

        Args:
            context: Discussion context
            stage: Current discussion stage
            round_num: Current round number
            role_hint: Optional role hint

        Returns:
            AgentMessage with response
        """
        # Build messages
        system_prompt = self.get_system_prompt()

        if role_hint:
            system_prompt += f"\n\n当前任务：{role_hint}"

        # Add tool usage instructions
        if self.config.enabled_tools:
            system_prompt += "\n\n你可以使用以下工具来帮助你完成任务："
            for tool_name in self.config.enabled_tools:
                system_prompt += f"\n- {tool_name}"

        messages = [
            {"role": "system", "content": system_prompt}
        ] + context

        model_string = self.registry.get_model_string(self.config.model_ref)
        if not model_string:
            raise ValueError(f"Model not found: {self.config.model_ref}")

        # Get tool definitions
        tool_registry = get_tool_registry()
        tool_definitions = tool_registry.get_tools_for_agent(self.config.enabled_tools)

        # Execute with function calling
        async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
            tool = tool_registry.get(tool_name)
            if not tool:
                return {"error": f"Tool not found: {tool_name}"}
            return await tool.execute(**arguments)

        response = await self.gateway.chat_completion_with_function_calling(
            model=model_string,
            messages=messages,
            tools=tool_definitions,
            execute_tool_func=execute_tool,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
        )

        message = AgentMessage(
            agent_name=self.config.name,
            agent_role=role_hint or "participant",
            content=response.content,
            model_used=self.config.model_ref,
            stage=stage,
            round_num=round_num,
            token_usage=response.token_usage,
        )

        self._history.append({
            "role": "assistant",
            "name": self.config.name,
            "content": response.content,
        })

        return message

    def reset_history(self) -> None:
        """Reset agent conversation history."""
        self._history.clear()

    def get_history(self) -> list[dict[str, str]]:
        """Get agent conversation history."""
        return self._history.copy()
