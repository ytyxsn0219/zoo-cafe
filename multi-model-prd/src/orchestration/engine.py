"""Discussion engine for multi-agent collaboration."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..agents.base import AgentMessage
from ..agents.registry import get_all_agents, get_moderator
from ..utils.config import get_discussion_config
from ..utils.logger import get_discussion_logger
from ..utils.prompt_loader import get_prompt_loader
from .consensus import create_consensus_detector
from .summarizer import create_summarizer


@dataclass
class StageResult:
    """Result of a discussion stage."""

    stage: str
    messages: list[AgentMessage]
    consensus_reached: bool
    max_turns_reached: bool
    duration_seconds: float


class DiscussionEngine:
    """Engine for managing multi-agent discussions."""

    def __init__(self, session_id: str):
        """
        Initialize discussion engine.

        Args:
            session_id: Session identifier
        """
        self.session_id = session_id
        self._logger = get_discussion_logger(session_id)
        self._config = get_discussion_config()
        self._consensus_detector = create_consensus_detector()
        self._summarizer = create_summarizer()
        self._prompt_loader = get_prompt_loader()

        self._context: list[dict[str, str]] = []
        self._all_messages: list[AgentMessage] = []
        self._current_stage: str = ""

        self._compression_config = self._config.get("context_compression", {})

    async def run_stage(
        self,
        stage: str,
        topic: str,
        max_turns: Optional[int] = None,
    ) -> StageResult:
        """
        Run a discussion stage.

        Args:
            stage: Stage name (elicitation, design, writing, finalizing)
            topic: Discussion topic
            max_turns: Maximum turns (from config if not provided)

        Returns:
            StageResult with messages and status
        """
        self._current_stage = stage
        max_turns = max_turns or self._config["max_turns_per_stage"].get(stage, 5)

        self._logger.info(
            "stage_started",
            stage=stage,
            topic=topic,
            max_turns=max_turns,
        )

        start_time = datetime.now()

        # Initialize context with topic
        self._context.append({
            "role": "user",
            "content": f"【{stage}阶段】讨论主题：{topic}",
        })

        # Get agents
        participants = get_all_agents()
        moderator = get_moderator()

        if not participants:
            raise ValueError("No participant agents available")

        # Stage intro from moderator
        if moderator:
            await self._moderator_announce(stage, "start")

        # Discussion rounds
        consensus_reached = False
        for round_num in range(1, max_turns + 1):
            self._logger.debug("round_started", round=round_num, stage=stage)

            # Each participant speaks
            for agent in participants:
                role_hint = self._get_role_hint(stage)

                try:
                    message = await agent.speak(
                        context=self._context,
                        stage=stage,
                        round_num=round_num,
                        role_hint=role_hint,
                    )
                    self._all_messages.append(message)

                    # Add to context
                    self._context.append({
                        "role": "assistant",
                        "name": agent.name,
                        "content": message.content,
                    })

                except Exception as e:
                    self._logger.error(
                        "agent_error",
                        agent=agent.name,
                        error=str(e),
                    )

            # Check for consensus
            recent_messages = [
                {"content": msg.content}
                for msg in self._all_messages[-len(participants):]
            ]
            consensus_reached, reason = self._consensus_detector.check_consensus(
                recent_messages, stage
            )

            if consensus_reached:
                self._logger.info("consensus_reached", reason=reason)
                break

            # Context compression if enabled
            if self._compression_config.get("enabled", True):
                trigger_after = self._compression_config.get("trigger_after_turns", 5)
                if self._summarizer.should_compress(self._context, trigger_after):
                    self._context = await self._summarizer.summarize(
                        self._context,
                        stage,
                    )

        # Stage end from moderator
        if moderator:
            await self._moderator_announce(stage, "end", consensus_reached)

        duration = (datetime.now() - start_time).total_seconds()

        result = StageResult(
            stage=stage,
            messages=self._all_messages.copy(),
            consensus_reached=consensus_reached,
            max_turns_reached=round_num >= max_turns and not consensus_reached,
            duration_seconds=duration,
        )

        self._logger.info(
            "stage_completed",
            stage=stage,
            total_messages=len(self._all_messages),
            consensus_reached=consensus_reached,
            duration_seconds=duration,
        )

        return result

    async def _moderator_announce(
        self,
        stage: str,
        phase: str,
        consensus: bool = False,
    ) -> None:
        """Moderator announces stage start/end."""
        moderator = get_moderator()
        if not moderator:
            return

        try:
            # Load moderator stage intro
            moderator_data = self._prompt_loader.load("moderator")
            stage_intros = moderator_data.get("stage_intro", {})

            if phase == "start":
                intro = stage_intros.get(stage, "")
            else:
                intro = "讨论阶段结束。" + ("各方已达成共识。" if consensus else "未完全达成共识。")

            message = await moderator.speak(
                context=self._context,
                stage=stage,
                round_num=0,
                role_hint="主持人",
            )
            message.content = intro + "\n\n" + message.content
            self._all_messages.append(message)

        except Exception as e:
            self._logger.warning("moderator_announce_failed", error=str(e))

    def _get_role_hint(self, stage: str) -> str:
        """Get role hint for current stage."""
        role_hints = {
            "elicitation": "需求分析师",
            "design": "产品经理/架构师",
            "writing": "产品经理",
            "finalizing": "文档撰写者",
        }
        return role_hints.get(stage, "参与者")

    def get_context(self) -> list[dict[str, str]]:
        """Get current discussion context."""
        return self._context.copy()

    def get_all_messages(self) -> list[AgentMessage]:
        """Get all messages from discussion."""
        return self._all_messages.copy()

    def reset(self) -> None:
        """Reset discussion state."""
        self._context.clear()
        self._all_messages.clear()
        self._current_stage = ""


def create_engine(session_id: str) -> DiscussionEngine:
    """
    Create a discussion engine for a session.

    Args:
        session_id: Session identifier

    Returns:
        DiscussionEngine instance
    """
    return DiscussionEngine(session_id)
