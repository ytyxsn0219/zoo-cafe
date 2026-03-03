"""Markdown output generator."""

from datetime import datetime
from typing import Any, Optional


class MarkdownGenerator:
    """Generate Markdown formatted PRD output."""

    def __init__(self):
        """Initialize markdown generator."""
        pass

    def generate_prd(
        self,
        title: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Generate full PRD in Markdown format.

        Args:
            title: PRD title
            content: PRD content
            metadata: Optional metadata

        Returns:
            Markdown formatted PRD
        """
        meta = metadata or {}
        version = meta.get("version", "1.0.0")
        authors = meta.get("authors", ["System"])
        date = meta.get("date", datetime.now().strftime("%Y-%m-%d"))

        # Build header
        header = f"""---
title: {title}
version: {version}
date: {date}
authors: {", ".join(authors)}
---

# {title}

"""

        # Build table of contents
        toc = self._generate_toc(content)

        # Build full document
        return header + toc + content

    def _generate_toc(self, content: str) -> str:
        """Generate table of contents from content."""
        lines = content.split("\n")
        toc_lines = ["## 目录\n"]

        for line in lines:
            line = line.strip()
            if line.startswith("## "):
                # H2 - main section
                title = line[3:].strip()
                anchor = title.lower().replace(" ", "-")
                toc_lines.append(f"- [{title}](#{anchor})")
            elif line.startswith("### "):
                # H3 - subsection
                title = line[4:].strip()
                anchor = title.lower().replace(" ", "-")
                toc_lines.append(f"  - [{title}](#{anchor})")

        return "\n".join(toc_lines) + "\n\n"

    def generate_section(
        self,
        title: str,
        content: str,
        level: int = 2,
    ) -> str:
        """
        Generate a markdown section.

        Args:
            title: Section title
            content: Section content
            level: Heading level (2 or 3)

        Returns:
            Markdown section
        """
        prefix = "#" * level
        return f"{prefix} {title}\n\n{content}\n\n"

    def generate_table(
        self,
        headers: list[str],
        rows: list[list[str]],
    ) -> str:
        """
        Generate a markdown table.

        Args:
            headers: Table headers
            rows: Table rows

        Returns:
            Markdown table
        """
        lines = []

        # Header row
        lines.append("| " + " | ".join(headers) + " |")

        # Separator row
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Data rows
        for row in rows:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

        return "\n".join(lines) + "\n"

    def generate_list(
        self,
        items: list[str],
        ordered: bool = False,
    ) -> str:
        """
        Generate a markdown list.

        Args:
            items: List items
            ordered: Whether to use ordered list

        Returns:
            Markdown list
        """
        lines = []

        for i, item in enumerate(items, 1):
            prefix = f"{i}." if ordered else "-"
            lines.append(f"{prefix} {item}")

        return "\n".join(lines) + "\n"

    def generate_code_block(
        self,
        code: str,
        language: str = "",
    ) -> str:
        """
        Generate a markdown code block.

        Args:
            code: Code content
            language: Programming language

        Returns:
            Markdown code block
        """
        return f"```{language}\n{code}\n```\n"


# Global instance
_generator: Optional[MarkdownGenerator] = None


def get_markdown_generator() -> MarkdownGenerator:
    """Get global markdown generator instance."""
    global _generator
    if _generator is None:
        _generator = MarkdownGenerator()
    return _generator


def generate_prd_markdown(
    title: str,
    content: str,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """
    Convenience function to generate PRD markdown.

    Args:
        title: PRD title
        content: PRD content
        metadata: Optional metadata

    Returns:
        Markdown formatted PRD
    """
    generator = get_markdown_generator()
    return generator.generate_prd(title, content, metadata)
