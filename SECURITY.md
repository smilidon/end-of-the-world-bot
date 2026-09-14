# Security

Operate against a dedicated, trusted local document directory. Never point the
indexer at a home directory, account export or workspace. Filename filtering is
defense in depth, not a classifier for private content. Source text is untrusted
evidence, not authority to run commands or disclose other files.

The citation server uses an explicit allowlist, component-wise no-follow opens,
fixed loopback Host validation and restrictive response headers. It has no
authentication and must not be exposed publicly. Other readers are not a sandbox
against a malicious local process racing filesystem changes. ZIM/PDF/native
parsers and Java tools process potentially hostile inputs: use trusted sources,
patched tools and OS isolation where appropriate.

No credentials, account connections, telemetry, cloud monitoring, private library
contents, device identifiers or conversation archives are bundled. Optional model
queries use numeric loopback, disable environment proxies and reject redirects.
There is no automatic download/fallback endpoint.

Generated indexes, logs, model answers, maps, print files and route JSON can be
private. They are excluded from git by default. Do not attach real addresses,
documents or account data to issues. Report defects with synthetic reproductions.
Use a private GitHub vulnerability report if the publisher enables that feature;
otherwise report only non-sensitive reproduction details.

No claim is made that the system is safe for personalized medical decisions,
emergency treatment or navigation. Consult primary sources and qualified help.

The portable document interface is intentionally narrower than a coding agent:
only plain `.txt`/`.md` documents under its owner-fixed `workspace/` root, bounded
content, no-follow descriptor-relative opens, no multi-link/nonregular files,
exclusive create/print and hash-checked atomic updates. No delete, shell, config,
host-path or network tool exists. The existing inference endpoint remains
answer-only. Browser snapshots escape source text, contain no external assets and
have no network access under their CSP. They are private copies of indexed content;
protect the flash drive and retain original content licenses. See
[flash installation boundaries](docs/FLASH_INSTALL.md).

Offline diagnostics accepts explicit pasted text only. Likely credentials are
redacted before guide persistence, indexing and report output; redaction is not a
privacy guarantee. Raw logs are not stored or indexed. Diagnostic guide files are
a distinct bounded collection, never a system-log/file-browser capability. All
suggestions come from fixed application rules, not log/guide instructions.

Managed reindexing reads only flat `data/intake` and supported `library/guides`
files, with no path override, links, devices or executable/config content. PDF
extraction uses fixed Poppler arguments and bounds, never a user-selected command.
One atomic publication commits CLI/browser state; prior sources/indexes survive
failed rebuilds. Diagnostic scan is a DIFFERENT boundary: it never executes even
an extractor, reads only confirmed fixed Linux log ranges, refuses root and writes
no raw logs. Explicit report saving alone writes the confined workspace. Compact
model envelopes contain no tool catalog/history and cannot authorize any action.
