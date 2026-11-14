"""Markdown + PDF export for finalized reports."""

from __future__ import annotations

from pathlib import Path

from src.state.persistence import run_dir, write_markdown_report
from src.state.research_state import ResearchState


def export_markdown(state: ResearchState) -> Path:
    return write_markdown_report(state)


def export_pdf(state: ResearchState) -> Path:
    """Generate a simple PDF using ReportLab from the markdown report content."""
    assert state.draft_report is not None
    md_path = write_markdown_report(state)
    out = run_dir(state.run_id) / "report.pdf"
    text = md_path.read_text(encoding="utf-8")

    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as e:
        raise RuntimeError(
            "reportlab is required for PDF export. Install with: pip install reportlab"
        ) from e

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out), pagesize=LETTER)
    story = []
    for line in text.splitlines():
        safe = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        if safe.startswith("# "):
            story.append(Paragraph(safe[2:], styles["Title"]))
        elif safe.startswith("## "):
            story.append(Paragraph(safe[3:], styles["Heading2"]))
        elif safe.startswith("- "):
            story.append(Paragraph("• " + safe[2:], styles["Normal"]))
        elif safe.strip():
            story.append(Paragraph(safe, styles["Normal"]))
        else:
            story.append(Spacer(1, 8))
    doc.build(story)
    return out
