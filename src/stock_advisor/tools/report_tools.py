from __future__ import annotations
from pathlib import Path
from typing import Any, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator


class FilePathInput(BaseModel):
    """A single markdown file plus an optional CSS file."""
    path: str = Field(..., description="Path to a Markdown file to convert")
    css: Optional[str] = Field(
        default=None,
        description="Optional CSS file; if omitted, a default stylesheet is used",
    )

    @field_validator("path")
    def file_must_exist(cls, v: str) -> str:
        if not Path(v).is_file():
            raise FileNotFoundError(f"Markdown file not found: {v}")
        return v


class HTMLStringInput(BaseModel):
    """Raw HTML string and a target PDF filename."""
    html: str = Field(..., description="Already-rendered HTML to print to PDF")
    out: str = Field(..., description="Output PDF path (e.g. 'report.pdf')")


class ImageToPdfInput(BaseModel):
    img_path: str = Field(..., description="Path to a JPEG/PNG file")
    out: str = Field(..., description="Output PDF filename")


class MergeListInput(BaseModel):
    """List of PDFs to combine and a destination filename."""
    files: List[str] = Field(..., description="PDF paths in the order to merge")
    out: str = Field(..., description="Destination PDF (e.g. 'final_report.pdf')")

    @field_validator("files")
    def all_paths_exist(cls, v: List[str]) -> List[str]:
        missing = [f for f in v if not Path(f).is_file()]
        if missing:
            raise FileNotFoundError(f"Missing PDFs for merge: {', '.join(missing)}")
        return v


class FileReadToolSchema(BaseModel):
    file_path: str = Field(..., description="Full path to the file to read")
    start_line: Optional[int] = Field(1, description="Line to start reading from (1-indexed)")
    line_count: Optional[int] = Field(None, description="Number of lines to read; None = entire file")


# ---------------------------------------------------------------------------

class MarkdownRenderTool(BaseTool):
    """Convert Markdown to HTML."""
    name: str = "Markdown → HTML"
    description: str = "Convert a Markdown file to raw HTML (tables, fenced code, sane lists)."
    args_schema: Type[BaseModel] = FilePathInput

    def _run(self, path: str, css: Optional[str] = "report.css") -> str:
        import markdown
        txt = Path(path).read_text(encoding="utf-8")
        html = markdown.markdown(txt, extensions=["tables", "fenced_code", "sane_lists"])
        link = f"<link rel='stylesheet' href='{css}'>" if css else ""
        return f"{link}{html}"


class WeasyPrintTool(BaseTool):
    """Turn HTML (string) into a standalone PDF using WeasyPrint."""
    name: str = "HTML → PDF (WeasyPrint)"
    description: str = "Render an HTML string to a PDF file using WeasyPrint."
    args_schema: Type[BaseModel] = HTMLStringInput

    def _run(self, html: str, out: str) -> str:
        from weasyprint import HTML
        HTML(string=html, base_url=".").write_pdf(out)
        return out


class ImageToPdfTool(BaseTool):
    name: str = "Image → PDF"
    description: str = "Embed a single image in HTML and export as a one-page PDF."
    args_schema: Type[BaseModel] = ImageToPdfInput

    def _run(self, img_path: str, out: str) -> str:
        from weasyprint import HTML
        html = f"<img src='{img_path}' style='width:100%;'>"
        HTML(string=html, base_url=".").write_pdf(out)
        return out


class PdfMergeTool(BaseTool):
    """Merge multiple PDF files into one."""
    name: str = "Merge PDFs"
    description: str = "Concatenate multiple PDF files into a single document."
    args_schema: Type[BaseModel] = MergeListInput

    def _run(self, files: List[str], out: str) -> str:
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        for f in files:
            for page in PdfReader(f).pages:
                writer.add_page(page)
        writer.write(out)
        writer.close()
        return out


class FileReadTool(BaseTool):
    """Read the contents of a file, with optional line range."""
    name: str = "Read a file's content"
    description: str = (
        "Reads the content of a file. Provide 'file_path'; optionally 'start_line' "
        "and 'line_count' to read a specific range."
    )
    args_schema: Type[BaseModel] = FileReadToolSchema
    file_path: Optional[str] = None

    def __init__(self, file_path: Optional[str] = None, **kwargs: Any) -> None:
        if file_path is not None:
            kwargs["description"] = (
                f"Reads file content. Default file: {file_path}. "
                "Supply 'file_path' to override, and 'start_line'/'line_count' for partial reads."
            )
        super().__init__(**kwargs)
        self.file_path = file_path

    def _run(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path", self.file_path)
        start_line = kwargs.get("start_line", 1)
        line_count = kwargs.get("line_count", None)

        if file_path is None:
            return "Error: No file path provided."

        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                if start_line == 1 and line_count is None:
                    return fh.read()
                start_idx = max(start_line - 1, 0)
                selected = [
                    line
                    for i, line in enumerate(fh)
                    if i >= start_idx and (line_count is None or i < start_idx + line_count)
                ]
                if not selected and start_idx > 0:
                    return f"Error: start_line {start_line} exceeds the file length."
                return "".join(selected)
        except FileNotFoundError:
            return f"Error: File not found: {file_path}"
        except PermissionError:
            return f"Error: Permission denied: {file_path}"
        except Exception as e:
            return f"Error reading {file_path}: {e}"
