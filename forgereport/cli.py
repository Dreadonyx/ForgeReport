"""Click-based CLI entry point for ForgeReport."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from forgereport import __tagline__, __version__
from forgereport.config import load_config
from forgereport.core.ingestion import EmptyInputError, UnsupportedInputError, read_input
from forgereport.core.llm import (
    NoProviderConfigured,
    ProvidersExhausted,
    generate_report_markdown,
    provider_statuses,
)
from forgereport.core.parser import build_partial_report, normalize_markdown, parse_report
from forgereport.core.prompt import build_user_prompt
from forgereport.exporters.docx import export_docx
from forgereport.exporters.markdown import export_markdown
from forgereport.exporters.pdf import export_pdf
from forgereport.utils import console, ensure_directory, print_setup_guide, slugify_title, today_compact


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--input", "input_path", type=click.Path(path_type=str), help="Input file or directory.")
@click.option("--mode", type=click.Choice(["ctf", "pentest", "recon"]), help="Report mode.")
@click.option("--title", type=str, help="Report title.")
@click.option("--output", "output_dir", type=click.Path(path_type=str), help="Output directory.")
@click.option("--provider", type=click.Choice(["groq", "openrouter", "mistral"]), help="Force a provider.")
@click.option("--model", "model_override", type=str, help="Override provider model.")
@click.option("--list-providers", is_flag=True, help="Show provider status and exit.")
@click.option("--preview", is_flag=True, help="Print markdown to terminal before saving.")
@click.option("--config", "config_path", type=click.Path(path_type=str), help="Config file path.")
@click.version_option(__version__, prog_name="ForgeReport")
def main(
    input_path: str | None,
    mode: str | None,
    title: str | None,
    output_dir: str | None,
    provider: str | None,
    model_override: str | None,
    list_providers: bool,
    preview: bool,
    config_path: str | None,
) -> None:
    """Raw input. Professional output."""

    try:
        config = load_config(config_path)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if list_providers:
        _print_provider_table(config)
        return

    selected_mode = mode or config.get("default_mode", "ctf")
    selected_output = output_dir or config.get("default_output", "./reports/")
    stdin_text = None if input_path or sys.stdin.isatty() else sys.stdin.read()

    try:
        bundle = _read_bundle(input_path=input_path, stdin_text=stdin_text)
    except (FileNotFoundError, EmptyInputError, UnsupportedInputError) as exc:
        raise click.ClickException(str(exc)) from exc

    for skipped in bundle.skipped:
        console.print(f"[yellow]Skipped {skipped.path}: {skipped.reason}[/yellow]")

    user_prompt = build_user_prompt(bundle.content, selected_mode, title=title)
    partial_only = False
    try:
        with console.status("[bold blue]Forging report...[/bold blue]", spinner="dots"):
            raw_markdown, used_provider = generate_report_markdown(
                user_prompt,
                config=config,
                forced_provider=provider,
                model_override=model_override,
            )
        markdown = normalize_markdown(raw_markdown, mode=selected_mode, title_hint=title)
        console.print(f"[green]Generated with {used_provider}.[/green]")
    except NoProviderConfigured as exc:
        print_setup_guide()
        raise click.exceptions.Exit(1) from exc
    except ProvidersExhausted as exc:
        console.print("[yellow]All configured providers failed. Saving partial markdown report.[/yellow]")
        for error in exc.errors:
            console.print(f"[dim]- {error}[/dim]")
        markdown = build_partial_report(bundle.content, mode=selected_mode, title=title)
        partial_only = True

    if preview:
        console.rule("Markdown Preview")
        console.print(markdown)
        console.rule()

    output_root = ensure_directory(selected_output)
    paths = _output_paths(output_root, markdown, title)

    try:
        md_path = export_markdown(markdown, paths["md"])
        console.print(f"[green][✓] MD[/green]  -> {md_path}")
        if partial_only:
            console.print("[yellow]DOCX and PDF were not produced because only a partial markdown report is available.[/yellow]")
            return
        docx_path = export_docx(markdown, paths["docx"])
        console.print(f"[green][✓] DOCX[/green] -> {docx_path}")
        pdf_path = export_pdf(markdown, paths["pdf"])
        console.print(f"[green][✓] PDF[/green]  -> {pdf_path}")
    except Exception as exc:
        raise click.ClickException(f"Export failed: {exc}") from exc


def _read_bundle(input_path: str | None, stdin_text: str | None):
    if input_path and Path(input_path).expanduser().is_dir():
        files_seen = {"total": 0}

        def progress_callback(_path: Path, _index: int, total: int) -> None:
            files_seen["total"] = total
            if total:
                task = getattr(progress_callback, "task", None)
                progress = getattr(progress_callback, "progress", None)
                if progress and task is not None:
                    progress.update(task, total=total, advance=1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Reading input files", total=1)
            progress_callback.progress = progress  # type: ignore[attr-defined]
            progress_callback.task = task  # type: ignore[attr-defined]
            return read_input(input_path=input_path, progress_callback=progress_callback)
    return read_input(input_path=input_path, stdin_text=stdin_text)


def _print_provider_table(config: dict) -> None:
    table = Table(title="ForgeReport Providers")
    table.add_column("Provider", style="bold")
    table.add_column("Model")
    table.add_column("API Key")
    table.add_column("Status")
    for status in provider_statuses(config):
        key_state = "[green]present[/green]" if status.api_key_present else "[red]missing[/red]"
        status_style = "green" if status.api_key_present else "yellow"
        table.add_row(status.name, status.model, key_state, f"[{status_style}]{status.status}[/{status_style}]")
    console.print(table)
    if not any(status.api_key_present for status in provider_statuses(config)):
        console.print()
        print_setup_guide()


def _output_paths(output_root: Path, markdown: str, title_hint: str | None) -> dict[str, Path]:
    parsed = parse_report(markdown)
    title = title_hint or parsed.title
    slug = slugify_title(title)
    stem = f"report_{slug}_{today_compact()}"
    return {
        "md": output_root / f"{stem}.md",
        "docx": output_root / f"{stem}.docx",
        "pdf": output_root / f"{stem}.pdf",
    }


if __name__ == "__main__":
    main()
