"""PDF output generator."""

from io import BytesIO
from typing import Any, Optional

from ..utils.logger import get_logger

logger = get_logger("pdf_generator")

try:
    from weasyprint import HTML
except ImportError:
    HTML = None


class PDFGenerator:
    """Generate PDF from Markdown/HTML content."""

    def __init__(self):
        """Initialize PDF generator."""
        if HTML is None:
            logger.warning("weasyprint not installed, PDF generation unavailable")

    def generate_pdf(
        self,
        markdown_content: str,
        title: str = "PRD Document",
    ) -> bytes:
        """
        Generate PDF from markdown content.

        Args:
            markdown_content: Markdown content
            title: Document title

        Returns:
            PDF bytes

        Raises:
            ImportError: If weasyprint is not installed
        """
        if HTML is None:
            raise ImportError("weasyprint is required for PDF generation")

        # Convert markdown to HTML
        html_content = self._markdown_to_html(markdown_content, title)

        # Generate PDF
        pdf_bytes = HTML(string=html_content).write_pdf()

        return pdf_bytes

    def generate_pdf_stream(
        self,
        markdown_content: str,
        title: str = "PRD Document",
    ) -> BytesIO:
        """
        Generate PDF as a stream.

        Args:
            markdown_content: Markdown content
            title: Document title

        Returns:
            BytesIO stream containing PDF
        """
        pdf_bytes = self.generate_pdf(markdown_content, title)
        return BytesIO(pdf_bytes)

    def _markdown_to_html(self, markdown: str, title: str) -> str:
        """
        Convert markdown to HTML with styling.

        Args:
            markdown: Markdown content
            title: Document title

        Returns:
            HTML string
        """
        # Simple markdown to HTML conversion
        # In production, use a proper markdown library like mistune

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{title}</title>",
            "<style>",
            self._get_styles(),
            "</style>",
            "</head>",
            "<body>",
            "<div class='document'>",
        ]

        # Process markdown lines
        lines = markdown.split("\n")
        in_code_block = False
        in_list = False

        for line in lines:
            line = line.strip()

            if not line:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                continue

            # Code blocks
            if line.startswith("```"):
                if in_code_block:
                    html_parts.append("</code></pre>")
                    in_code_block = False
                else:
                    lang = line[3:].strip()
                    html_parts.append(f"<pre><code class='language-{lang}'>")
                    in_code_block = True
                continue

            if in_code_block:
                html_parts.append(line)
                continue

            # Headers
            if line.startswith("# "):
                html_parts.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_parts.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_parts.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("#### "):
                html_parts.append(f"<h4>{line[5:]}</h4>")

            # List items
            elif line.startswith("- ") or line.startswith("* "):
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(f"<li>{line[2:]}</li>")

            # Numbered list
            elif line[0].isdigit() and ". " in line:
                if not in_list:
                    html_parts.append("<ol>")
                    in_list = True
                parts = line.split(". ", 1)
                html_parts.append(f"<li>{parts[1]}</li>")

            # Tables (simplified)
            elif line.startswith("|"):
                html_parts.append(f"<p>{line}</p>")

            # Regular paragraphs
            else:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                # Simple formatting
                text = line
                text = text.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
                text = text.replace("*", "<em>").replace("*", "</em>")
                text = text.replace("`", "")
                html_parts.append(f"<p>{text}</p>")

        if in_list:
            html_parts.append("</ul>")

        html_parts.extend([
            "</div>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html_parts)

    @staticmethod
    def _get_styles() -> str:
        """Get CSS styles for the document."""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        .document {
            background: white;
        }
        h1 {
            font-size: 28px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
            margin-top: 30px;
        }
        h2 {
            font-size: 22px;
            margin-top: 25px;
            color: #444;
        }
        h3 {
            font-size: 18px;
            margin-top: 20px;
            color: #555;
        }
        p {
            margin: 12px 0;
        }
        ul, ol {
            margin: 10px 0;
            padding-left: 25px;
        }
        li {
            margin: 5px 0;
        }
        pre {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }
        code {
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 14px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background: #f5f5f5;
        }
        """


# Global instance
_pdf_generator: Optional[PDFGenerator] = None


def get_pdf_generator() -> PDFGenerator:
    """Get global PDF generator instance."""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFGenerator()
    return _pdf_generator


def generate_pdf(
    markdown_content: str,
    title: str = "PRD Document",
) -> bytes:
    """
    Convenience function to generate PDF.

    Args:
        markdown_content: Markdown content
        title: Document title

    Returns:
        PDF bytes
    """
    generator = get_pdf_generator()
    return generator.generate_pdf(markdown_content, title)
