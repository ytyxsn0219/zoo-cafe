"""Model registry for managing available models."""

from dataclasses import dataclass
from typing import Any, Optional

from ..utils.config import get_models_config
from ..utils.logger import get_logger

logger = get_logger("model_registry")


@dataclass
class ModelConfig:
    """Model configuration."""

    name: str
    provider: str
    model: str
    description: str
    config: dict[str, Any]


class ModelRegistry:
    """Registry for managing available LLM models."""

    def __init__(self):
        """Initialize model registry from config."""
        self._models: dict[str, ModelConfig] = {}
        self._load_models()

    def _load_models(self) -> None:
        """Load models from configuration."""
        models_config = get_models_config()

        for model_data in models_config:
            config = ModelConfig(
                name=model_data.get("name", ""),
                provider=model_data.get("provider", ""),
                model=model_data.get("model", ""),
                description=model_data.get("description", ""),
                config=model_data.get("config", {}),
            )
            self._models[config.name] = config
            logger.debug("model_registered", name=config.name, provider=config.provider)

    def get(self, name: str) -> Optional[ModelConfig]:
        """
        Get model configuration by name.

        Args:
            name: Model name

        Returns:
            ModelConfig or None if not found
        """
        return self._models.get(name)

    def get_model_string(self, name: str) -> Optional[str]:
        """
        Get the actual model identifier for LiteLLM.

        Args:
            name: Model reference name

        Returns:
            Model string for LiteLLM (e.g., "openai/gpt-4o") or None
        """
        config = self.get(name)
        if not config:
            return None

        # Format: provider/model
        return f"{config.provider}/{config.model}"

    def list_models(self) -> list[str]:
        """List all registered model names."""
        return list(self._models.keys())

    def get_all_configs(self) -> list[ModelConfig]:
        """Get all model configurations."""
        return list(self._models.values())


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get global model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def get_model_config(name: str) -> Optional[ModelConfig]:
    """
    Convenience function to get model config.

    Args:
        name: Model name

    Returns:
        ModelConfig or None
    """
    registry = get_model_registry()
    return registry.get(name)


def resolve_model_string(name: str) -> Optional[str]:
    """
    Convenience function to resolve model reference to LiteLLM string.

    Args:
        name: Model reference name

    Returns:
        LiteLLM model string or None
    """
    registry = get_model_registry()
    return registry.get_model_string(name)
