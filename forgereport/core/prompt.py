"""Prompt construction for ForgeReport."""

from __future__ import annotations

from forgereport.utils import today_iso

SYSTEM_PROMPT = """You are ForgeReport, an elite security report writer.
Convert the raw input into a structured, professional security report.
Follow the exact markdown structure provided.
Auto-detect: category (recon/web/crypto/pwn/forensics/osint/misc),
difficulty (easy/medium/hard) from content.
Use technical language. Format tool output as fenced code blocks.
Never hallucinate findings not present in the input.
Return only the markdown report, no preamble or explanation."""

REPORT_TEMPLATE = """---
title: "{title}"
target: ""
date: "{date}"
category: ""
difficulty: ""
mode: "{mode}"
tags: []
---

# {title}

## Executive Summary
## Target / Scope
## Methodology
## Reconnaissance
## Findings
### Finding 1 — <Name>
- Severity: Critical/High/Medium/Low
- Description
- Evidence (tool output block)
- CVE (if applicable)
## Exploitation / Proof of Concept
{mode_section}
## Key Takeaways
## References"""


def mode_section(mode: str) -> str:
    if mode == "pentest":
        return "## Remediation"
    if mode == "ctf":
        return "## Flags / Credentials Captured"
    return "## Remediation"


def build_user_prompt(raw_input: str, mode: str, title: str | None = None) -> str:
    report_title = title or "Security Report"
    template = REPORT_TEMPLATE.format(
        title=report_title,
        date=today_iso(),
        mode=mode,
        mode_section=mode_section(mode),
    )
    if mode == "ctf":
        mode_guidance = "CTF mode: focus on attack path, proof of concept, flags, and credentials. Do not include remediation."
    elif mode == "pentest":
        mode_guidance = "Pentest mode: focus on business impact, evidence, and actionable remediation. Do not include flags unless explicitly present as credentials."
    else:
        mode_guidance = "Recon mode: produce a concise intelligence digest. Keep findings evidence-backed and avoid exploitation steps unless present in the input."

    return f"""Mode: {mode}
Title hint: {report_title}

Required markdown structure:
{template}

Additional mode rules:
{mode_guidance}

Raw input:
```text
{raw_input}
```"""
