"""Parse and normalize markdown reports produced by the LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from forgereport.utils import today_iso

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

SECTION_ORDER = [
    "Executive Summary",
    "Target / Scope",
    "Methodology",
    "Reconnaissance",
    "Findings",
    "Exploitation / Proof of Concept",
    "Flags / Credentials Captured",
    "Remediation",
    "Key Takeaways",
    "References",
]


@dataclass
class Finding:
    name: str
    severity: str = ""
    cve: str = ""
    description: str = ""


@dataclass
class ParsedReport:
    metadata: dict[str, Any]
    body: str
    title: str
    findings: list[Finding] = field(default_factory=list)


def split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(markdown.strip())
    if not match:
        return {}, markdown.strip()
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
        if not isinstance(metadata, dict):
            metadata = {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, markdown[match.end() :].strip()


def extract_title(body: str, fallback: str = "Security Report") -> str:
    for match in HEADING_RE.finditer(body):
        if len(match.group(1)) == 1:
            return match.group(2).strip()
    return fallback


def parse_findings(body: str) -> list[Finding]:
    findings: list[Finding] = []
    matches = list(re.finditer(r"^###\s+(Finding\s+\d+\s+[-\u2014]\s+.+|.+)$", body, re.MULTILINE))
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        block = body[start:end]
        name = re.sub(r"^Finding\s+\d+\s+[-\u2014]\s+", "", heading, flags=re.I).strip()
        severity = _first_match(block, r"Severity:\s*([A-Za-z]+)")
        cve = _first_match(block, r"\b(CVE-\d{4}-\d{4,})\b")
        description = _description_from_block(block)
        findings.append(Finding(name=name, severity=severity, cve=cve, description=description))
    return findings


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.I)
    return match.group(1).strip() if match else ""


def _description_from_block(block: str) -> str:
    for line in block.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("```"):
            continue
        if clean.lower().startswith("- description"):
            return clean.lstrip("- ").strip()
        if clean.startswith("- ") and "severity:" not in clean.lower():
            return clean[2:].strip()
    return ""


def normalize_markdown(
    markdown: str,
    mode: str,
    title_hint: str | None = None,
    target_hint: str = "",
) -> str:
    metadata, body = split_frontmatter(markdown)
    title = str(metadata.get("title") or extract_title(body, title_hint or "Security Report"))
    normalized_meta = {
        "title": title,
        "target": str(metadata.get("target") or target_hint),
        "date": str(metadata.get("date") or today_iso()),
        "category": str(metadata.get("category") or "misc"),
        "difficulty": str(metadata.get("difficulty") or "medium"),
        "mode": mode,
        "tags": metadata.get("tags") if isinstance(metadata.get("tags"), list) else [],
    }

    body = _ensure_h1(body, title)
    body = _ensure_sections(body, mode)
    frontmatter = yaml.safe_dump(normalized_meta, sort_keys=False, allow_unicode=False).strip()
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n"


def parse_report(markdown: str) -> ParsedReport:
    metadata, body = split_frontmatter(markdown)
    title = str(metadata.get("title") or extract_title(body))
    return ParsedReport(metadata=metadata, body=body, title=title, findings=parse_findings(body))


def _ensure_h1(body: str, title: str) -> str:
    if re.search(r"^#\s+", body, flags=re.MULTILINE):
        return body.strip()
    return f"# {title}\n\n{body.strip()}"


def _ensure_sections(body: str, mode: str) -> str:
    present = {match.group(2).strip() for match in HEADING_RE.finditer(body) if len(match.group(1)) == 2}
    required = [section for section in SECTION_ORDER if _section_allowed(section, mode)]
    additions = [f"## {section}\n" for section in required if section not in present]
    if not additions:
        return body.strip()
    return body.rstrip() + "\n\n" + "\n".join(additions)


def _section_allowed(section: str, mode: str) -> bool:
    if section == "Flags / Credentials Captured":
        return mode == "ctf"
    if section == "Remediation":
        return mode in {"pentest", "recon"}
    return True


def build_partial_report(raw_input: str, mode: str, title: str | None = None) -> str:
    safe_title = title or "Partial Security Report"
    snippet = raw_input.strip()
    if len(snippet) > 12000:
        snippet = snippet[:12000].rstrip() + "\n\n[Input truncated in partial report.]"
    mode_specific = "## Flags / Credentials Captured\n\nNot generated because all configured LLM providers failed." if mode == "ctf" else "## Remediation\n\nNot generated because all configured LLM providers failed."
    markdown = f"""---
title: "{safe_title}"
target: ""
date: "{today_iso()}"
category: "misc"
difficulty: "medium"
mode: "{mode}"
tags: []
---

# {safe_title}

## Executive Summary

Partial report saved because all configured LLM providers were exhausted.

## Target / Scope

Not generated.

## Methodology

Not generated.

## Reconnaissance

```text
{snippet}
```

## Findings

No findings generated.

## Exploitation / Proof of Concept

Not generated.

{mode_specific}

## Key Takeaways

Not generated.

## References

Not generated.
"""
    return normalize_markdown(markdown, mode=mode, title_hint=safe_title)
