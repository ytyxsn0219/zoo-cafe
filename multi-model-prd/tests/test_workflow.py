"""Tests for workflow."""

import pytest

from src.orchestration.workflow import PRDWorkflow, WorkflowState


class TestWorkflowState:
    """Test cases for WorkflowState."""

    def test_workflow_state_creation(self) -> None:
        """Test WorkflowState can be created."""
        state = WorkflowState(
            session_id="test-session",
            requirement="Test requirement",
        )

        assert state.session_id == "test-session"
        assert state.requirement == "Test requirement"
        assert state.status == "pending"
        assert state.current_stage == "elicitation"

    def test_workflow_state_with_results(self) -> None:
        """Test WorkflowState with stage results."""
        state = WorkflowState(
            session_id="test-session",
            requirement="Test requirement",
            elicitation_result={"key": "value"},
            design_result={"key": "value"},
            writing_result={"key": "value"},
            final_result={"key": "value"},
            status="completed",
        )

        assert state.elicitation_result == {"key": "value"}
        assert state.status == "completed"


class TestPRDWorkflow:
    """Test cases for PRDWorkflow."""

    @pytest.fixture
    def workflow(self) -> PRDWorkflow:
        """Create workflow."""
        return PRDWorkflow(session_id="test-session")

    def test_workflow_initialization(self, workflow: PRDWorkflow) -> None:
        """Test workflow initializes correctly."""
        assert workflow.session_id == "test-session"
        assert isinstance(workflow._engine, object)
        assert workflow._state.session_id == "test-session"

    def test_workflow_stages(self, workflow: PRDWorkflow) -> None:
        """Test workflow has correct stages."""
        assert workflow.STAGES == ["elicitation", "design", "writing", "finalizing"]
