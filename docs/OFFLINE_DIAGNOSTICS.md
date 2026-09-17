# Bounded offline diagnostic observations (Bot profile)

The pasted-text mode analyzes **only explicitly supplied text**, not the computer.
The additional confirmed Linux scan below can read a fixed log allowlist; neither
mode inspects arbitrary files, environment variables, endpoints or running processes. It never runs commands, modifies host
configuration or calls a model. No Reddit/current-online knowledge is promised.

**Logs can contain private data.** Review and minimize them before pasting. Likely
passwords, key/token assignments, authorization/cookie headers, common token/JWT/
private-key formats, signed URL credentials, email addresses and user-directory
names are redacted before extraction, indexing or persistence. This is a heuristic,
not a guarantee: unidentified credentials, addresses and other private information
can remain. Inspect the result before sharing. Raw pasted logs are never stored
or indexed. Console output and explicitly saved reports can still be private.

## Analyze text and optionally create a printable report

Inside a newly installed Bot folder:

```sh
printf '%s\n' '{"action":"analyze","text":"2026-09-13T12:34:56Z Linux Ollama ECONNREFUSED connection refused","report_name":"Connection observations.md"}' | sh launch.sh diagnose
printf '%s\n' '{"action":"print","name":"Connection observations.md"}' | sh launch.sh document
```

Open `workspace/Connection observations.md.print.html` and use Print / Save as PDF.
Omit `report_name` for an entirely in-memory analysis. Existing documents are never
overwritten. Only plain `.txt`/`.md` names in the fixed document workspace are
accepted. There is no log-filename/path parameter: a pasted path is analyzed as
text, not opened. Paste only a small excerpt that you explicitly choose.

Output separates observed OS/application/service names, error codes and ISO-style
timestamps from five supported error categories: permissions, storage, missing
optional dependencies, refused connections and reference-index errors. It provides
the matched text and input line number, qualitative confidence, at least two
plausible causes for each match, and fixed safe/reversible suggested checks.
It always says **insufficient evidence to establish a root cause**. An error-name
match does not verify an actual event or host state. Unsupported symptoms yield
no findings rather than invented causes. No proposed check executes automatically.

## Separate Markdown reference intake and air-gapped reindexing

Four compact first-party guides ship in `diagnostic_guides/`, under the project's
software/documentation license. No third-party guides or logs are redistributed.
Additional owner-selected Markdown text goes into `diagnostics/guides/`, separate
from `library/`, after the same redaction and bounded safe intake:

```sh
printf '%s\n' '{"action":"import-guide","name":"Device notes.md","text":"# Storage observations\nInspect the selected volume properties; preserve existing files."}' | sh launch.sh diagnose
printf '%s\n' '{"action":"read-guide","name":"Device notes.md"}' | sh launch.sh diagnose
printf '%s\n' '{"action":"reindex"}' | sh launch.sh diagnose
```

Import creates a new file. To update it, submit `import-guide` with replacement
`text` and `expected_sha256` from import/read. A stale hash refuses the edit.
Obtain guides from a separately reviewed offline source, retain their attribution
and rights in the Markdown, and paste their text through this intake. Do not copy
raw logs into the reference collection. Even files placed there manually are
redacted in memory before indexing, but the tool cannot retroactively erase private
bytes someone manually stored outside its intake.

The tool builds a **dedicated in-memory SQLite FTS5 index on every request** from
these guides. `reindex` validates/rebuilds it and reports the guide count; there is
no disk index to delete, migrate or overwrite, and no main-library index changes.
Imported guides are immediately available to the next analysis, including while
air-gapped. Matching guide excerpts are explicitly labeled untrusted reference
text, never executed or promoted to suggested checks. Suggestions come only from
reviewed application rules; prompt-like log/guide content cannot create new rules.

## Limits and extension point

- Pasted logs: 64 KiB; imported Markdown: 32 guides, 32 KiB each (at most 1 MiB).
  The four bundled guides total only a few KiB. Temporary FTS memory overhead is
  expected to be a few MiB for a full collection, not a benchmark guarantee.
- No persistent diagnostic database or raw-log archive; each report uses the
  existing 256 KiB workspace limit. Old reports remain until the owner manages them.
- Flat safe guide names, no symlinks/hardlinks/nonregular files, no arbitrary root
  override. Updates use the existing workspace's hash checks and atomic replacement.
- Database-only profile remains a static reader and does not expose this Bot tool.
- `offline_diagnostics.Diagnostics(owner_fixed_install_root).dispatch(request)` is
  the trusted embedding API. A future file-picker UI must pass explicitly selected,
  bounded text through this same intake, not grant filesystem or command tools.
  Add supported error rules with evidence-bound tests; do not treat guide prose,
  log messages or model-generated instructions as executable diagnostic policy.

## Linux-first confirmed log discovery (additional explicit intake option)

For the interactive menu, run **`sh launch.sh diagnose-scan`**: select a numbered
symptom, review the exact scope, type its READ phrase, and optionally name a new
workspace report. Blank confirmation cancels without reading logs.

The text-only interface above remains available. Linux API users may instead choose a
symptom and preview a **limited metadata-only** scope:

```sh
printf '%s\n' '{"action":"plan","category":"storage"}' | sh launch.sh diagnose
```

Choose `storage`, `permission`, `dependency`, `connection` or `index`. The preview
shows exact source paths, inode identity, byte offsets/counts, UTC time window,
unavailable sources and a `READ ...` confirmation phrase. No log content has been
read. Review the entire scope; then submit one JSON object containing
`action: "scan"`, the exact returned `scope`, and the exact `confirm` phrase.
Add `report_name: "Diagnostic scan.md"` only if you explicitly want a redacted
workspace report. Otherwise scanning writes nothing. Print a saved report through
the existing `launch.sh document` print action.

Fixed Linux allowlist by category:

| Category | Candidate files below `/var/log` |
| --- | --- |
| Storage | `syslog`, `messages`, `kern.log` |
| Permission | `syslog`, `messages` |
| Dependency | `dpkg.log`, `apt/term.log`, `dnf.log` |
| Connection | `ollama/ollama.log`, `syslog`, `messages` |
| Reference index | `syslog`, `messages` |

Missing sources are normal across Linux distributions. No automatic fallback to
arbitrary paths or `journalctl` occurs. Journal-only services may require the owner
to paste a separately selected/exported excerpt. Home documents, browser profiles,
credentials, authentication/security logs and binary journals are not candidates.
Windows/macOS discovery are future extensions, not supported/qualified scans.

The fixed window is the prior **24 hours**, maximum **16 KiB per file / 48 KiB total**,
and confirmation expires after **10 minutes**. Only approved offsets are read:
appended data beyond the preview is not included. Rotation, truncation, symlink or
nonregular-file changes refuse that source. Only timestamped lines matching the
chosen category are analyzed. ISO timestamps with offsets are preferred; naive
ISO and yearless syslog timestamps explicitly disclose host-timezone/year
assumptions. Undated/unsupported/old/future lines are skipped and counted. This can
miss evidence, so no result proves health or establishes a certain root cause.

Discovery/scan refuses root and never elevates, executes a command, changes
configuration, starts/restarts services, uses a model or sends network requests.
It reads only the fixed allowlist after confirmation. Likely secrets are redacted
before evidence/report processing; raw log content is not persisted. Reports cite
the approved source and parsed timestamp, show assumptions and plausible causes,
and retain the warning that redaction cannot guarantee privacy. A saved printable
report is an explicit workspace write, not an incidental effect of scanning.

## Separate network observation workflow

The no-command/no-network guarantees above describe log diagnosis. The distinct
`network-diagnose` command provides confirmed Linux configuration reads and an
optional second-consent Wi-Fi scan. It does not extend the log API or model tools.
See [exact network scope and command exception](NETWORK_DIAGNOSTICS.md).
