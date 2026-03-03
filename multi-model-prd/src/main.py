"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .models.registry import get_model_registry
from .agents.registry import get_agent_registry
from .memory.short_term import get_short_term_memory, ShortTermMemory
from .utils.config import get_settings
from .utils.logger import get_logger, setup_logging

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    logger.info("application_starting")

    # Initialize components
    try:
        # Load models
        model_registry = get_model_registry()
        logger.info("models_loaded", count=len(model_registry.list_models()))

        # Load agents
        agent_registry = get_agent_registry()
        logger.info("agents_loaded", count=len(agent_registry.list_agent_names()))

        # Connect to Redis
        memory = await get_short_term_memory()
        logger.info("redis_connected")

    except Exception as e:
        logger.error("startup_error", error=str(e))

    yield

    # Shutdown
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Multi-Model PRD Generation System",
        description="A collaborative PRD generation system using multiple AI models",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(router)

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
