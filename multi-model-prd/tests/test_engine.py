"""Tests for discussion engine."""

import pytest

from src.orchestration.engine import DiscussionEngine, StageResult


class TestDiscussionEngine:
    """Test cases for DiscussionEngine."""

    @pytest.fixture
    def engine(self) -> DiscussionEngine:
        """Create discussion engine."""
        return DiscussionEngine(session_id="test-session-123")

    def test_engine_initialization(self, engine: DiscussionEngine) -> None:
        """Test engine initializes correctly."""
        assert engine.session_id == "test-session-123"
        assert engine._context == []
        assert engine._all_messages == []

    def test_engine_get_context(self, engine: DiscussionEngine) -> None:
        """Test getting context."""
        context = engine.get_context()
        assert context == []

    def test_engine_get_all_messages(self, engine: DiscussionEngine) -> None:
        """Test getting all messages."""
        messages = engine.get_all_messages()
        assert messages == []

    def test_engine_reset(self, engine: DiscussionEngine) -> None:
        """Test engine reset."""
        # Add some data
        engine._context.append({"role": "user", "content": "test"})
        engine.reset()

        assert engine._context == []
        assert engine._all_messages == []


class TestStageResult:
    """Test cases for StageResult."""

    def test_stage_result_creation(self) -> None:
        """Test StageResult can be created."""
        result = StageResult(
            stage="elicitation",
            messages=[],
            consensus_reached=True,
            max_turns_reached=False,
            duration_seconds=10.5,
        )

        assert result.stage == "elicitation"
        assert result.consensus_reached is True
        assert result.max_turns_reached is False
        assert result.duration_seconds == 10.5
