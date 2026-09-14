# Air-gapped document intake and atomic reindexing

Both Bot and database-only installations have **`data/intake/`** for documents
explicitly chosen by the owner. Copy approved `.txt`, `.md` or extractable `.pdf`
files there, then run these commands inside the installation:

```sh
sh launch.sh intake-scan
sh launch.sh reindex
sh launch.sh search 'your reference question'
```

Scan is read-only and shows added/changed/skipped/failed entries. Reindex explicitly
reads the same two flat directories: `data/intake/` and the existing
`library/guides/` (so supported manually downloaded originals are retained).
Neither command accepts arbitrary root/path overrides or recurses into folders.
Content remains untrusted evidence, never code/instructions. There is no download
or model call. PDF extraction alone invokes the fixed preinstalled Poppler
`pdftotext` program, with no shell, bounded output and a deadline.

Limits: 256 total directory entries, 16 MiB per input file, 128 MiB combined raw
input; 2 MiB extracted text/file and 16 MiB total; 12 seconds/PDF and 60 seconds
extraction per rebuild. Text must be UTF-8. Symlinks, hardlinks, devices/FIFOs,
traversal/hidden/protected names, config files and unsupported types are excluded.
Executable extensions, shebang/ELF/PE signatures and binary text are rejected;
executable permission bits alone are not trusted on FAT-like portable storage.
PDFs must have a PDF signature and successfully extract nonempty text. Unsupported
legacy HTML/ZIM/maps are not migrated by this narrow intake path: keep using the
original library explicitly with `--library` for those optional formats.

## Publication and failure handling

A rebuild copies validated bytes into a NEW `data/generations/<id>/library/`,
builds its FTS5 index, validates it, generates its static reference page and verifies
that the inputs did not change. `provenance.json` records the source directory/name,
SHA-256, bytes, source mtime and index timestamp. Each run reports visible counts
and saves `data/intake-results-<id>.json` when storage is available.

A **single atomic replacement of top-level `reference.html`** commits the new
browser snapshot and the generation selected by the CLI. Its first-line generation
marker points only to a validated, fixed-name local generation. CLI readers select
one generation; old readers keep their old immutable documents/index. The browser
uses the same snapshot after reload. No two-file pointer/index switch is required.
`launch.sh browser` can additionally export the active generation to a NEW file.

Missing previously indexed sources, unsafe input, missing PDF tools, extraction/
index/export failure, changed input and failed publication all leave the prior
valid search/page intact. Restore a missing source rather than deleting the old
index. Source removal is deliberately not an implicit deletion feature. Reports
identify the failure; fix the input and retry. Failed/new generations are retained
for owner inspection, never automatically erased. Main `library/` originals and
its old index are never overwritten by this workflow.

Budget storage for inputs plus at least one copied generation, index, HTML snapshot
and a backup. Multiple generations accumulate; the owner should back up and manage
old ones deliberately, never remove the active generation. This is atomic process-
failure publication, not a physical-USB or power-loss durability certification.
No background watcher scans personal folders. Existing external-library workflows
remain available with explicit `--library`; intake always stays installation-local.
