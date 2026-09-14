# Contributing

Thanks for considering a contribution. This is a small, GPL-3.0-only offline reference project; please keep changes focused, reproducible, and safe for users who may rely on it in disconnected or emergency settings.

## Setup and local checks

Requires Python 3.11+, SQLite FTS5, and `poppler-utils` (for PDF ingestion). Install test dependencies:

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

## What belongs in an issue

- A concise title and one clear problem or request.
- Version (`VERSION` file or release tag), OS, Python version, and how you installed (source, portable ZIP, or custom).
- Reproduction steps with synthetic fixtures where possible (`library/guides/example.txt` style). Do not attach real documents, account exports, home directories, device identifiers, or conversation archives.
- Expected vs. actual behavior, plus any relevant command output or log excerpts (redact paths/names if needed).
- Confirm you searched open and recently closed issues; duplicates slow review.

Use the issue templates (bug report or feature request) and include attachments only when they are synthetic fixtures or sanitized logs. Generated indexes, route JSON, print files, and model answers are excluded from git; do not commit them.

## Pull requests

Keep PRs small and single-purpose. Include:

- A clear scope statement.
- Tests for any new or changed behavior.
- Documentation updates if user-facing instructions change.
- No generated/private files (indexes, logs, print artifacts, download caches, or binaries).
- A brief note on behavior impact, security impact, and source/rights for any new dependency or copied material.

Use the pull-request template; the checklist exists to protect offline users who may not have easy network recovery paths. No contributor license agreement is required; contributions to this GPL-3.0-only repository are licensed under the same terms.

## Safety and reproducibility boundaries

- Never bundle credentials, telemetry, model weights, private library contents, or cloud monitoring data.
- Do not point the indexer at a home directory, account export, or workspace. Filename filtering is defense in depth, not authorization.
- Report defects with synthetic reproductions. Do not disclose vulnerabilities in public issues; see `SECURITY.md` for the private route.
- This is a bounded retrieval/reference tool, not a sandbox against malicious local processes. Treat all input sources cautiously.
- No claim is made that the system is safe for personalized medical decisions, emergency treatment, or navigation. Consult primary sources and qualified help.

## Voice and scope

Maintain the existing offline/product voice: concise, direct, no marketing, no runtime legalese. Do not add runtime user-interface legal disclaimers, a Code of Conduct (none is required by current policy), or additional licensing text beyond the existing GPL-3.0-only header and `NOTICE.md`/`LICENSE` references.
