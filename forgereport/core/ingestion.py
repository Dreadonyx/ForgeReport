"""Input handling for files, directories, and stdin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SUPPORTED_EXTENSIONS = {".txt", ".log", ".json", ".xml", ".md"}


class EmptyInputError(ValueError):
    """Raised when no usable input content is available."""


class UnsupportedInputError(ValueError):
    """Raised when a single input file type is unsupported."""


@dataclass
class SkippedFile:
    path: Path
    reason: str


@dataclass
class InputBundle:
    content: str
    sources: list[Path] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)


ProgressCallback = Callable[[Path, int, int], None]


def is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def discover_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data:
        raise UnicodeDecodeError("utf-8", data, 0, 1, "binary data detected")
    return data.decode("utf-8")


def _format_source(path: Path, content: str) -> str:
    return f"\n\n--- SOURCE: {path} ---\n\n{content.strip()}\n"


def read_input(
    input_path: str | None = None,
    stdin_text: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> InputBundle:
    if input_path:
        path = Path(input_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Input path does not exist: {path}")
        if path.is_dir():
            return read_directory(path, progress_callback=progress_callback)
        return read_single_file(path)

    content = (stdin_text or "").strip()
    if not content:
        raise EmptyInputError(
            "No input received. Provide --input <file-or-dir> or pipe text into forgereport."
        )
    return InputBundle(content=content, sources=[Path("<stdin>")])


def read_single_file(path: Path) -> InputBundle:
    if not is_supported_file(path):
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedInputError(f"Unsupported file type: {path.suffix}. Supported: {supported}")
    try:
        content = _read_text_file(path).strip()
    except UnicodeDecodeError as exc:
        raise EmptyInputError(f"Input file appears corrupt or binary: {path}") from exc
    if not content:
        raise EmptyInputError(f"Input file is empty: {path}")
    return InputBundle(content=_format_source(path, content).strip(), sources=[path])


def read_directory(
    directory: Path,
    progress_callback: ProgressCallback | None = None,
) -> InputBundle:
    files = discover_files(directory)
    skipped: list[SkippedFile] = []
    sources: list[Path] = []
    chunks: list[str] = []

    total = len(files)
    for index, path in enumerate(files, start=1):
        if progress_callback:
            progress_callback(path, index, total)
        try:
            content = _read_text_file(path).strip()
        except UnicodeDecodeError:
            skipped.append(SkippedFile(path=path, reason="corrupt or binary"))
            continue
        if not content:
            skipped.append(SkippedFile(path=path, reason="empty"))
            continue
        sources.append(path)
        chunks.append(_format_source(path.relative_to(directory), content))

    merged = "\n".join(chunks).strip()
    if not merged:
        raise EmptyInputError(f"No readable supported files found in directory: {directory}")
    return InputBundle(content=merged, sources=sources, skipped=skipped)
