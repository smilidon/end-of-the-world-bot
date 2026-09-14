---
name: Bug report
about: Report a defect or unexpected behavior with reproduction steps
title: "[bug] "
labels: bug
assignees: ''
---

## Description

Concise summary of the defect and where it appears (indexing, search, citation server, PDF ingestion, portable install, routing, privacy guard, etc.).

## Version and environment

- Project version / `VERSION` value or release tag:
- OS and architecture:
- Python version:
- Installation method (source / portable ZIP / custom):
- Dependency versions if changed (`requirements-test.txt` or installed packages):

## Reproduction steps

Steps with a synthetic fixture or minimal command sequence. Example:

```sh
mkdir -p library/guides
printf '%s\n' 'SYNTHETIC: test entry.' > library/guides/example.txt
python3 bot.py --root library index
python3 bot.py --root library search 'test entry.'
```

## Expected vs. actual behavior

- Expected:
- Actual:

## Logs / attachments

If attaching logs or output: use synthetic fixtures or redacted excerpts only. Do not attach real documents, account exports, home directories, device identifiers, conversation archives, or generated indexes/route JSON. Attachments are public; treat them as untrusted evidence, not authorization to disclose private content.

## Search first

Confirm this is not a duplicate by searching open and recently closed issues. If the same symptom appears with a different root cause, open a new issue and reference the related one.
