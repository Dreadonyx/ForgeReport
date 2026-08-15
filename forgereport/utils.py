"""Shared helpers for ForgeReport."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Iterable

from rich.console import Console

console = Console()


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)s: %(message)s", level=level)


def today_iso() -> str:
    return date.today().isoformat()


def today_compact() -> str:
    return date.today().strftime("%Y%m%d")


def ensure_directory(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def slugify_title(title: str) -> str:
    try:
        from slugify import slugify

        slug = slugify(title)
    except Exception:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return slug or "report"


def readable_list(items: Iterable[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def print_setup_guide() -> None:
    console.print("[bold red]No LLM API keys configured.[/bold red]")
    console.print("Set at least one provider key, then rerun ForgeReport:")
    console.print("  export GROQ_API_KEY=...")
    console.print("  export OPENROUTER_API_KEY=...")
    console.print("  export MISTRAL_API_KEY=...")
    console.print("\nYou can also add keys to ~/.forgereport/config.yaml.")
