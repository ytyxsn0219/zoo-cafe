"""Prompt template loading and rendering utilities."""

from pathlib import Path
from typing import Any, Optional

import yaml
from jinja2 import BaseLoader, Environment, TemplateNotFound

from .config import get_settings
from .logger import get_logger

logger = get_logger("prompt_loader")


class PromptLoader:
    """Load and render prompt templates from YAML files."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize prompt loader.

        Args:
            prompts_dir: Directory containing prompt YAML files
        """
        self.prompts_dir = prompts_dir or get_settings().prompts_dir
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            autoescape=False,
            keep_trailing_newline=True,
        )
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str, use_cache: bool = True) -> dict[str, Any]:
        """
        Load prompt template from YAML file.

        Args:
            name: Template name (without .yaml extension)
            use_cache: Whether to use cached template

        Returns:
            Parsed prompt template dictionary
        """
        if use_cache and name in self._cache:
            return self._cache[name]

        template_path = self.prompts_dir / f"{name}.yaml"

        if not template_path.exists():
            logger.error("prompt_template_not_found", path=str(template_path))
            raise TemplateNotFound(f"Prompt template not found: {name}")

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_data = yaml.safe_load(f) or {}

            if use_cache:
                self._cache[name] = template_data

            logger.debug("prompt_loaded", name=name)
            return template_data

        except yaml.YAMLError as e:
            logger.error("prompt_yaml_parse_error", name=name, error=str(e))
            raise

    def render(self, name: str, context: dict[str, Any]) -> str:
        """
        Render prompt template with context.

        Args:
            name: Template name
            context: Context variables for rendering

        Returns:
            Rendered prompt string
        """
        template_data = self.load(name)
        template_str = template_data.get("system_prompt", "")

        try:
            template = self._env.from_string(template_str)
            return template.render(**context)
        except Exception as e:
            logger.error("prompt_render_error", name=name, error=str(e))
            # Fallback to simple string replacement
            return template_str.format(**context)

    def get_stage_prompt(self, stage: str, context: dict[str, Any]) -> str:
        """
        Get stage-specific prompt.

        Args:
            stage: Stage name (elicitation, design, writing, finalizing)
            context: Context variables

        Returns:
            Rendered prompt
        """
        return self.render(f"stage_{stage}", context)

    def get_role_prompt(self, role: str, context: dict[str, Any]) -> str:
        """
        Get role-specific prompt.

        Args:
            role: Role name (elicitation, design, writing, review, finalizing)
            context: Context variables

        Returns:
            Rendered prompt
        """
        # Load from universal_agent.yaml roles section
        template_data = self.load("universal_agent")
        roles = template_data.get("roles", {})
        role_prompt = roles.get(role, {}).get("prompt", "")

        if not role_prompt:
            logger.warning("role_prompt_not_found", role=role)
            return ""

        try:
            template = self._env.from_string(role_prompt)
            return template.render(**context)
        except Exception as e:
            logger.error("role_prompt_render_error", role=role, error=str(e))
            return role_prompt.format(**context)


class FileSystemLoader(BaseLoader):
    """Custom Jinja2 file system loader."""

    def __init__(self, searchpath: str):
        self.searchpath = searchpath

    def get_source(self, environment: Environment, template: str) -> tuple[str, str, bool]:
        """Get template source from file system."""
        path = Path(self.searchpath) / template

        if not path.exists():
            raise TemplateNotFound(template)

        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        return source, str(path), lambda: True


# Global instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get global prompt loader instance."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader


def load_prompt(name: str, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Convenience function to load a prompt template.

    Args:
        name: Template name
        context: Optional context for rendering

    Returns:
        Prompt template data
    """
    loader = get_prompt_loader()
    data = loader.load(name)

    if context:
        # Pre-render if context provided
        data["rendered"] = loader.render(name, context)

    return data


def render_prompt(name: str, context: dict[str, Any]) -> str:
    """
    Convenience function to render a prompt template.

    Args:
        name: Template name
        context: Context variables

    Returns:
        Rendered prompt string
    """
    loader = get_prompt_loader()
    return loader.render(name, context)
