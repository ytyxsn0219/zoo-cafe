"""Pytest configuration and fixtures."""

import asyncio
from typing import Any, Generator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[Any, None, None]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_model_response() -> dict[str, Any]:
    """Mock model response for testing."""
    return {
        "choices": [
            {
                "message": {
                    "content": "Test response from model"
                }
            }
        ],
        "usage": {
            "total_tokens": 100
        }
    }


@pytest.fixture
def sample_requirement() -> str:
    """Sample user requirement for testing."""
    return "我想做一个给宠物用的外卖 App"


@pytest.fixture
def session_id() -> str:
    """Generate a test session ID."""
    import uuid
    return str(uuid.uuid4())
