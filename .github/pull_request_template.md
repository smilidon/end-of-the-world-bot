## What does this PR change?

One-line scope: docs/config, bug fix, feature, or refactor. Keep it
single-purpose and respectful of the existing offline/reference boundary. I'm
the only regular maintainer — a focused PR with passing checks is the
quickest path to review.

## Related issue

Link or describe why this change is needed.

## Checklist

- [ ] Scope is focused; no unrelated changes.
- [ ] Existing `core` CI checks pass (`python -m unittest discover -s tests -v`, `python tools/privacy_scan.py`, `sha256sum -c FILE_MANIFEST.sha256`).
- [ ] Tests added or updated for new/changed behavior.
- [ ] Documentation (`README.md`, `START_HERE.md`, `docs/*.md`) updated if user-facing instructions change.
- [ ] No generated/private files (indexes, logs, print artifacts, caches, binaries, download artifacts) included.
- [ ] No new paid SaaS, external scanners, or additional CI providers added; existing `.github/workflows/tests.yml` reused.
- [ ] Behavior impact noted (offline use, portable install, citation server, routing, privacy guard, etc.).
- [ ] Security impact noted; no secrets, telemetry, private library contents, or device identifiers added.
- [ ] Source/rights noted for any new dependency, copied material, or derived asset; compatible with GPL-3.0-only.

## Security and privacy

Confirm no vulnerability disclosure is embedded in public PR text. Use
`SECURITY.md` for private reporting — open a minimal request (no exploit
details, no secrets, no sensitive paths) if no verified private contact is
available; wait for the maintainer to direct you.

## Source rights

License of any new/copied material and attribution. This repository is GPL-3.0-only; no contributor license agreement is required.
