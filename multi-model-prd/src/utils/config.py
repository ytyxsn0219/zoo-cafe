"""Configuration management utilities."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment and config files."""

    # App settings
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]

    # Redis settings
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_ttl: int = 86400

    # VectorDB settings
    vector_db_provider: str = "chroma"
    vector_db_collection: str = "prd_history"
    embedding_model: str = "text-embedding-3-small"

    # Discussion settings
    max_turns_elicitation: int = 5
    max_turns_design: int = 10
    max_turns_writing: int = 10
    max_turns_finalizing: int = 1
    consensus_threshold: float = 0.8
    context_compression_enabled: bool = True
    context_compression_trigger: int = 5
    max_context_tokens: int = 100000

    # Output settings
    default_output_format: str = "markdown"

    # Paths
    config_dir: Path = Path(__file__).parent.parent.parent / "config"
    prompts_dir: Path = Path(__file__).parent.parent.parent / "prompts"

    class Config:
        env_file = ".env"
        env_prefix = "PRD_"
        extra = "allow"


def load_yaml_config(filename: str) -> dict[str, Any]:
    """Load YAML configuration file."""
    settings = get_settings()
    config_path = settings.config_dir / filename

    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


@lru_cache
def get_models_config() -> list[dict[str, Any]]:
    """Get models configuration."""
    return load_yaml_config("models.yaml").get("models", [])


@lru_cache
def get_agents_config() -> list[dict[str, Any]]:
    """Get agents configuration."""
    return load_yaml_config("agents.yaml").get("agents", [])


@lru_cache
def get_discussion_config() -> dict[str, Any]:
    """Get discussion configuration."""
    settings = get_settings()
    base_config = load_yaml_config("settings.yaml")
    discussion = base_config.get("discussion", {})

    # Merge with environment-based settings
    return {
        "max_turns_per_stage": discussion.get("max_turns_per_stage", {
            "elicitation": settings.max_turns_elicitation,
            "design": settings.max_turns_design,
            "writing": settings.max_turns_writing,
            "finalizing": settings.max_turns_finalizing,
        }),
        "consensus_threshold": discussion.get("consensus_threshold", settings.consensus_threshold),
        "context_compression": discussion.get("context_compression", {
            "enabled": settings.context_compression_enabled,
            "trigger_after_turns": settings.context_compression_trigger,
            "max_context_tokens": settings.max_context_tokens,
        }),
    }


@lru_cache
def get_memory_config() -> dict[str, Any]:
    """Get memory configuration."""
    settings = get_settings()
    base_config = load_yaml_config("settings.yaml")
    memory = base_config.get("memory", {})

    return {
        "redis": memory.get("redis", {
            "url": settings.redis_url,
            "ttl": settings.redis_ttl,
        }),
        "vector_db": memory.get("vector_db", {
            "provider": settings.vector_db_provider,
            "collection": settings.vector_db_collection,
            "embedding_model": settings.embedding_model,
        }),
    }
