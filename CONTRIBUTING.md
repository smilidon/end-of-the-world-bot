# Contributing

Thanks for considering a contribution. I'm the maintainer. This is a small,
GPL-3.0-only offline reference project — not a hosted service. I keep it
concise, direct, and safe for people who may rely on it in disconnected or
emergency settings. A focused fix or clarification is welcome; I review when
I can, with no guaranteed schedule and no paid support line.

## Setup and local checks

Requires Python 3.11+, SQLite FTS5, and `poppler-utils` (for PDF ingestion). Use an isolated virtual environment (recommended from the README setup):

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
```

Or install globally (not recommended for shared systems):

```sh
python -m pip install -r requirements-test.txt
```

Run the existing core checks before opening a PR:

```sh
python -m unittest discover -s tests -v
python tools/privacy_scan.py
sha256sum -c FILE_MANIFEST.sha256
```

The CI workflow (`.github/workflows/tests.yml`) runs the same commands on `push` and `pull_request`: synthetic tests, privacy scan, manifest verification, and release build. Reuse that; do not add paid SaaS, external scanners, or new CI providers.

## Welcome (plainspoken)

I'm a single maintainer. This is a bounded retrieval/reference tool, not a
sandbox. Treat all input cautiously. There is no guaranteed response schedule,
no paid support line, and no promise of future features. If something helps
you, a focused, reproducible contribution is welcome.

## What belongs in an issue

- A concise title and one clear problem or request.
- Version (`VERSION` file or release tag), OS, Python version, and how you installed (source, portable ZIP, or custom).
- Reproduction steps with synthetic fixtures where possible (`library/guides/example.txt` style). Do not attach real documents, account exports, home directories, device identifiers, or conversation archives.
- Expected vs. actual behavior, plus any relevant command output or log excerpts (redact paths/names if needed).
- Confirm you searched open and recently closed issues; duplicates slow review.

Use the issue templates (bug report or feature request) and include attachments only when they are synthetic fixtures or sanitized logs. Generated indexes, route JSON, print files, and model answers are excluded from git; do not commit them.

## Pull requests

Keep PRs small, single-purpose, and respectful of scope. Include a scope
statement, tests for changed behavior, doc updates if user-facing instructions
change, and no generated/private/binary files. Note behavior and security
impact. Source rights for any new dependency or copied material stay
gpl-3.0-only compatible; no contributor agreement needed.

## Safety and reproducibility boundaries

- Never bundle credentials, telemetry, model weights, private library contents, or cloud monitoring data.
- Do not point the indexer at a home directory, account export, or workspace. Filename filtering is defense in depth, not authorization.
- Report defects with synthetic reproductions. Do not disclose vulnerabilities in public issues; see `SECURITY.md` for the private route.
- This is a bounded retrieval/reference tool, not a sandbox against malicious local processes. Treat all input sources cautiously.
- No claim is made that the system is safe for personalized medical decisions, emergency treatment, or navigation. Consult primary sources and qualified help.

## Voice and scope

Maintain the existing offline/product voice: concise, direct, no marketing, no runtime legalese. Do not add runtime user-interface legal disclaimers, a Code of Conduct (none is required by current policy), or additional licensing text beyond the existing GPL-3.0-only header and `NOTICE.md`/`LICENSE` references.
