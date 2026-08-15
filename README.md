# ForgeReport

Raw input. Professional output.

ForgeReport is a production-ready Python CLI that turns raw penetration testing output, CTF notes, and recon logs into structured reports in Markdown, DOCX, and PDF.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

The editable install exposes the global command:

```bash
forgereport --help
```

## Provider Setup

ForgeReport uses an automatic LLM fallback chain:

1. Groq: `GROQ_API_KEY`
2. OpenRouter: `OPENROUTER_API_KEY`
3. Mistral: `MISTRAL_API_KEY`

Set at least one key:

```bash
export GROQ_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
export MISTRAL_API_KEY="your-key"
```

Or place keys in `~/.forgereport/config.yaml`:

```yaml
default_mode: ctf
default_output: ./reports/
providers:
  groq:
    api_key: ""
    model: llama-3.3-70b-versatile
  openrouter:
    api_key: ""
    model: mistralai/mistral-7b-instruct:free
  mistral:
    api_key: ""
    model: mistral-small-latest
```

Check provider status:

```bash
forgereport --list-providers
```

## Usage

Single file:

```bash
forgereport --input scan.txt --mode ctf --title "RootMe PHP Upload"
```

Directory input:

```bash
forgereport --input ./logs/ --mode pentest --title "Client Webapp Audit" --output ./reports/
```

Piped recon output:

```bash
cat nmap.txt | forgereport --mode recon --title "Recon Summary"
```

Preview markdown before saving:

```bash
forgereport --input scan.txt --preview
```

Force a provider or model:

```bash
forgereport --input scan.txt --provider groq --model llama-3.3-70b-versatile
```

Use a custom config:

```bash
forgereport --config ~/.forgereport/config.yaml --input scan.txt
```

## Inputs

Supported sources:

- stdin
- single file via `--input`
- directory via `--input ./logs/`
- piped tool output

Supported extensions:

- `.txt`
- `.log`
- `.json`
- `.xml`
- `.md`

Directory ingestion recursively merges supported files. Empty, corrupt, or binary files are skipped with a warning.

## Outputs

Each successful run writes three files to `./reports/` by default:

- `report_<slug-title>_<YYYYMMDD>.md`
- `report_<slug-title>_<YYYYMMDD>.docx`
- `report_<slug-title>_<YYYYMMDD>.pdf`

Use `--output <dir>` to override the destination.

If every configured provider fails after retries, ForgeReport saves a partial Markdown report and warns that DOCX/PDF were not produced.

## Report Modes

`--mode ctf`

CTF writeup focused on attack path, proof of concept, flags, and credentials. This is the default.

`--mode pentest`

Professional penetration test report focused on impact, evidence, and remediation.

`--mode recon`

Recon-only summary for quick intelligence digestion.

## Report Structure

ForgeReport prompts the model to return only Markdown using this structure:

```markdown
---
title: ""
target: ""
date: ""
category: ""
difficulty: ""
mode: ""
tags: []
---

# <Title>

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
## Flags / Credentials Captured
## Remediation
## Key Takeaways
## References
```

CTF reports omit remediation. Pentest and recon reports omit the CTF-only flags section unless credentials are explicitly part of the report content.
