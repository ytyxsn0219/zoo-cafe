"""Workflow orchestration using LangGraph."""

from dataclasses import dataclass
from typing import Any, Optional

from ..agents.registry import get_agent_registry
from ..utils.logger import get_logger
from .engine import DiscussionEngine, StageResult

logger = get_logger("workflow")


@dataclass
class WorkflowState:
    """State of the workflow."""

    session_id: str
    current_stage: str = "elicitation"
    requirement: str = ""
    elicitation_result: Optional[dict[str, Any]] = None
    design_result: Optional[dict[str, Any]] = None
    writing_result: Optional[dict[str, Any]] = None
    final_result: Optional[dict[str, Any]] = None
    status: str = "pending"  # pending, running, completed, failed
    error: Optional[str] = None


class PRDWorkflow:
    """Workflow for generating PRD through multi-agent discussion."""

    STAGES = ["elicitation", "design", "writing", "finalizing"]

    def __init__(self, session_id: str):
        """
        Initialize PRD workflow.

        Args:
            session_id: Session identifier
        """
        self.session_id = session_id
        self._engine = DiscussionEngine(session_id)
        self._state = WorkflowState(session_id=session_id)

    async def execute(
        self,
        requirement: str,
        user_answers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Execute the full PRD generation workflow.

        Args:
            requirement: Initial user requirement
            user_answers: Optional answers to elicitation questions

        Returns:
            Final PRD result
        """
        self._state.requirement = requirement
        self._state.status = "running"

        try:
            logger.info("workflow_started", session_id=self.session_id)

            # Stage 1: Requirement Elicitation
            result_elicitation = await self._run_elicitation(requirement)
            self._state.elicitation_result = self._extract_result(result_elicitation)

            # If user provides answers, process them
            if user_answers:
                requirement = self._update_requirement_with_answers(
                    requirement, user_answers
                )

            # Stage 2: Feature Design
            result_design = await self._run_design(requirement)
            self._state.design_result = self._extract_result(result_design)

            # Stage 3: PRD Writing
            result_writing = await self._run_writing(requirement)
            self._state.writing_result = self._extract_result(result_writing)

            # Stage 4: Finalizing
            result_final = await self._run_finalizing()
            self._state.final_result = result_final

            self._state.status = "completed"

            logger.info(
                "workflow_completed",
                session_id=self.session_id,
                stages_completed=len(self.STAGES),
            )

            return {
                "session_id": self.session_id,
                "status": "completed",
                "prd": self._state.final_result,
                "stages": {
                    "elicitation": self._state.elicitation_result,
                    "design": self._state.design_result,
                    "writing": self._state.writing_result,
                },
            }

        except Exception as e:
            self._state.status = "failed"
            self._state.error = str(e)
            logger.error("workflow_failed", session_id=self.session_id, error=str(e))
            raise

    async def _run_elicitation(self, requirement: str) -> StageResult:
        """Run elicitation stage."""
        logger.info("stage_elicitation_started")

        topic = f"用户需求：{requirement}\n\n请各位提出需要澄清的关键问题。"
        result = await self._engine.run_stage("elicitation", topic)

        logger.info(
            "stage_elicitation_completed",
            messages=len(result.messages),
            consensus=result.consensus_reached,
        )

        return result

    async def _run_design(self, requirement: str) -> StageResult:
        """Run design stage."""
        logger.info("stage_design_started")

        # Build context from elicitation
        elicitation_summary = self._summarize_messages(
            self._state.elicitation_result
        )

        topic = f"""
需求背景：{requirement}

需求澄清结果：{elicitation_summary}

请各位提出核心功能列表。
"""
        result = await self._engine.run_stage("design", topic)

        logger.info(
            "stage_design_completed",
            messages=len(result.messages),
            consensus=result.consensus_reached,
        )

        return result

    async def _run_writing(self, requirement: str) -> StageResult:
        """Run writing stage."""
        logger.info("stage_writing_started")

        design_summary = self._summarize_messages(self._state.design_result)

        topic = f"""
需求：{requirement}

功能列表：{design_summary}

请各位撰写 PRD 文档的各个模块。
"""
        result = await self._engine.run_stage("writing", topic)

        logger.info(
            "stage_writing_completed",
            messages=len(result.messages),
            consensus=result.consensus_reached,
        )

        return result

    async def _run_finalizing(self) -> dict[str, Any]:
        """Run finalizing stage."""
        logger.info("stage_finalizing_started")

        writing_summary = self._summarize_messages(self._state.writing_result)

        topic = f"请将以下内容整合为标准格式的 PRD 文档：\n\n{writing_summary}"
        result = await self._engine.run_stage("finalizing", topic)

        logger.info("stage_finalizing_completed")

        return {
            "content": writing_summary,
            "final_message": result.messages[-1].content if result.messages else "",
            "all_messages": [msg.to_dict() for msg in result.messages],
        }

    def _extract_result(self, stage_result: StageResult) -> dict[str, Any]:
        """Extract result from stage result."""
        return {
            "stage": stage_result.stage,
            "messages": [msg.to_dict() for msg in stage_result.messages],
            "consensus_reached": stage_result.consensus_reached,
            "max_turns_reached": stage_result.max_turns_reached,
            "duration_seconds": stage_result.duration_seconds,
            "summary": self._summarize_messages(stage_result.messages),
        }

    def _summarize_messages(self, data: Any) -> str:
        """Summarize messages for context."""
        if isinstance(data, list):
            if not data:
                return ""
            # Get last few messages
            recent = data[-3:] if len(data) > 3 else data
            return "\n\n".join(
                msg.get("content", "") if isinstance(msg, dict) else str(msg)
                for msg in recent
            )
        elif isinstance(data, dict):
            return data.get("summary", str(data))
        return str(data) if data else ""

    def _update_requirement_with_answers(
        self,
        requirement: str,
        answers: dict[str, str],
    ) -> str:
        """Update requirement with user answers."""
        answers_text = "\n".join(f"- {k}: {v}" for k, v in answers.items())
        return f"{requirement}\n\n用户回答：\n{answers_text}"


def create_workflow(session_id: str) -> PRDWorkflow:
    """
    Create a PRD workflow instance.

    Args:
        session_id: Session identifier

    Returns:
        PRDWorkflow instance
    """
    return PRDWorkflow(session_id)
