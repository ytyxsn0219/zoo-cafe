"""FastAPI routes for PRD generation."""

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from ..memory.short_term import delete_session, get_session, store_session
from ..models.registry import get_model_registry
from ..orchestration.workflow import PRDWorkflow, create_workflow
from ..utils.logger import get_api_logger
from .schemas import (
    AgentMessageSchema,
    ErrorResponse,
    HealthResponse,
    MessageResponse,
    PRDOutput,
    SessionCreate,
    SessionCreateResponse,
    SessionResponse,
    SessionStatus,
)

logger = get_api_logger("routes")

router = APIRouter(prefix="/api/v1", tags=["PRD Generation"])

# In-memory workflow storage (in production, use Redis)
_workflows: dict[str, PRDWorkflow] = {}


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    model_registry = get_model_registry()

    return HealthResponse(
        status="healthy",
        models_loaded=len(model_registry.list_models()),
        agents_loaded=len(get_model_registry().list_models()),
    )


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    responses={500: {"model": ErrorResponse}},
)
async def create_session(
    request: SessionCreate,
    background_tasks: BackgroundTasks,
) -> SessionCreateResponse:
    """
    Create a new PRD generation session.

    Args:
        request: Session creation request

    Returns:
        Session creation response
    """
    session_id = str(uuid.uuid4())

    logger.info("session_created", session_id=session_id)

    # Initialize session state
    session_data = {
        "session_id": session_id,
        "status": SessionStatus.CREATED.value,
        "initial_requirement": request.initial_requirement,
        "created_at": datetime.now().isoformat(),
        "current_stage": "elicitation",
    }

    await store_session(session_id, session_data)

    # Start workflow in background
    workflow = create_workflow(session_id)
    _workflows[session_id] = workflow

    background_tasks.add_task(
        run_workflow,
        session_id,
        request.initial_requirement,
    )

    return SessionCreateResponse(
        session_id=session_id,
        status=SessionStatus.CREATED,
        message="Session created. Workflow started.",
    )


async def run_workflow(session_id: str, requirement: str) -> None:
    """Run workflow in background."""
    try:
        workflow = _workflows.get(session_id)
        if not workflow:
            logger.error("workflow_not_found", session_id=session_id)
            return

        # Update session status
        session_data = await get_session(session_id)
        if session_data:
            session_data["status"] = SessionStatus.ELICITATION.value
            await store_session(session_id, session_data)

        # Execute workflow
        result = await workflow.execute(requirement)

        # Update final status
        session_data = await get_session(session_id)
        if session_data:
            session_data["status"] = SessionStatus.COMPLETED.value
            session_data["completed_at"] = datetime.now().isoformat()
            session_data["result"] = result
            await store_session(session_id, session_data)

        logger.info("workflow_completed", session_id=session_id)

    except Exception as e:
        logger.error("workflow_failed", session_id=session_id, error=str(e))

        # Update error status
        session_data = await get_session(session_id)
        if session_data:
            session_data["status"] = SessionStatus.FAILED.value
            session_data["error"] = str(e)
            await store_session(session_id, session_data)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_session_status(session_id: str) -> SessionResponse:
    """
    Get session status and messages.

    Args:
        session_id: Session identifier

    Returns:
        Session response
    """
    session_data = await get_session(session_id)

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )

    # Get workflow messages if available
    workflow = _workflows.get(session_id)
    messages = []
    if workflow:
        for msg in workflow._engine.get_all_messages():
            messages.append(AgentMessageSchema(
                agent_name=msg.agent_name,
                agent_role=msg.agent_role,
                content=msg.content,
                model_used=msg.model_used,
                stage=msg.stage,
                round_num=msg.round_num,
                token_usage=msg.token_usage,
                timestamp=msg.timestamp,
            ))

    return SessionResponse(
        session_id=session_id,
        status=SessionStatus(session_data.get("status", "created")),
        current_stage=session_data.get("current_stage", ""),
        messages=messages,
        created_at=datetime.fromisoformat(session_data.get("created_at", datetime.now().isoformat())),
        updated_at=datetime.now(),
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}},
)
async def send_message(
    session_id: str,
    message: dict[str, Any],
) -> MessageResponse:
    """
    Send a message to the session.

    Args:
        session_id: Session identifier
        message: Message content

    Returns:
        Message response
    """
    session_data = await get_session(session_id)

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )

    # Process message (in a real implementation, this would update the workflow)
    logger.info("message_received", session_id=session_id, content=message.get("content", ""))

    return MessageResponse(
        session_id=session_id,
        message=AgentMessageSchema(
            agent_name="system",
            agent_role="system",
            content="Message received",
            model_used="",
            stage=session_data.get("current_stage", ""),
            round_num=0,
            token_usage=0,
        ),
        stage=session_data.get("current_stage", ""),
    )


@router.get(
    "/sessions/{session_id}/output",
    response_model=PRDOutput,
    responses={404: {"model": ErrorResponse}},
)
async def get_prd_output(
    session_id: str,
    format: str = "markdown",
) -> PRDOutput:
    """
    Get PRD output.

    Args:
        session_id: Session identifier
        format: Output format (markdown or pdf)

    Returns:
        PRD output
    """
    session_data = await get_session(session_id)

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )

    result = session_data.get("result", {})
    prd = result.get("prd", {})

    if not prd:
        raise HTTPException(
            status_code=404,
            detail=f"PRD not yet generated for session {session_id}"
        )

    return PRDOutput(
        session_id=session_id,
        title="PRD Document",
        content=prd.get("content", ""),
        format=format,
        total_tokens_used=sum(
            m.get("token_usage", 0)
            for m in prd.get("all_messages", [])
        ),
        total_rounds=len(prd.get("all_messages", [])),
    )


@router.get(
    "/sessions/{session_id}/stream")
async def stream_session(
    session_id: str,
) -> StreamingResponse:
    """
    Stream session updates via SSE.

    Args:
        session_id: Session identifier

    Returns:
        Streaming response with SSE
    """
    async def event_generator():
        # This is a placeholder - implement SSE streaming
        yield f"data: session {session_id} started\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.delete(
    "/sessions/{session_id}",
    responses={404: {"model": ErrorResponse}},
)
async def delete_session_endpoint(session_id: str) -> dict[str, str]:
    """
    Delete a session.

    Args:
        session_id: Session identifier

    Returns:
        Deletion confirmation
    """
    success = await delete_session(session_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )

    # Remove workflow
    if session_id in _workflows:
        del _workflows[session_id]

    return {"message": f"Session {session_id} deleted"}
