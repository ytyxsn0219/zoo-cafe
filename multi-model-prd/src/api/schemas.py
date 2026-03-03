"""Pydantic schemas for API request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Session status enum."""

    CREATED = "created"
    ELICITATION = "elicitation"
    DESIGN = "design"
    WRITING = "writing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentMessageSchema(BaseModel):
    """Agent message schema."""

    agent_name: str
    agent_role: str
    content: str
    model_used: str
    stage: str
    round_num: int
    token_usage: int
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    """Session creation request."""

    initial_requirement: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="Initial user requirement"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "initial_requirement": "我想做一个给宠物用的外卖 App"
            }
        }


class SessionCreateResponse(BaseModel):
    """Session creation response."""

    session_id: str
    status: SessionStatus
    message: str


class SessionResponse(BaseModel):
    """Session response."""

    session_id: str
    status: SessionStatus
    current_stage: str
    messages: list[AgentMessageSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MessageSend(BaseModel):
    """Message send request."""

    content: str = Field(..., min_length=1, max_length=5000)
    stage: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "content": "用户回答：目标用户是年轻白领..."
            }
        }


class MessageResponse(BaseModel):
    """Message response."""

    session_id: str
    message: AgentMessageSchema
    stage: str


class PRDOutput(BaseModel):
    """PRD output schema."""

    session_id: str
    title: str
    content: str
    format: str = "markdown"
    total_tokens_used: int = 0
    total_rounds: int = 0
    generated_at: datetime = Field(default_factory=datetime.now)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "0.1.0"
    models_loaded: int = 0
    agents_loaded: int = 0


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: Optional[str] = None
    session_id: Optional[str] = None


class StageProgress(BaseModel):
    """Stage progress info."""

    stage: str
    status: str
    messages_count: int
    consensus_reached: bool = False
