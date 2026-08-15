"""Markdown exporter."""

from __future__ import annotations

from pathlib import Path


def export_markdown(markdown: str, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.write_text(markdown, encoding="utf-8")
    return path
