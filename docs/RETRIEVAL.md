# Retrieval accuracy and source revisions

This describes the current feature-branch source, not the historical alpha.2 release.

## Existing indexes remain readable

The SQLite FTS5 schema is unchanged. Query-time expansion searches both spellings
of the project's existing aliases: battery/batteries, crop/crops, garden/gardens,
medicine/medicines, photovoltaic/photovoltaics/PV, and microhydro/micro-hydro.
Evidence is not rewritten or stemmed. This is a small lexical alias set, not a
universal language stemmer, semantic search, or a guarantee of complete recall.

The query constructs quoted FTS5 alternatives rather than treating document text
as SQL. See SQLite's [FTS5 query syntax and synonym discussion](https://www.sqlite.org/fts5.html).

## Verify the revision before quoting indexed text

For Stage 2 indexes, candidate files are hashed against the `documents` table.
For immutable intake generations, the existing `provenance.json` supplies the
snapshot hash. A changed, missing, oversized, or unreadable candidate is skipped
individually; valid matches from other files remain usable. Same-size edits with
restored timestamps are detected by the content hash, not just mtime.

An old index without hash metadata is not treated as current evidence. Search
attempts a bounded scan of the current documents instead and displays a rebuild
notice. A missing or unreadable index also has a distinct status and can use that
fallback. No index is created, repaired, or deleted by a search.

Results retain `id`, `source`, `text` and `kind`, and add structured `file` and
`location` fields. Hashed document results also contain `sha256` and `freshness`.
`hash_verified_at_query` means the indexed source matched its recorded revision
when checked. `current_read` means the excerpt came from a checked current read.
Neither is a promise that a mutable file will stay unchanged after the query.
Immutable generation paths continue to refer to the saved generation, not to a
later revision of an original intake file. Source hashes do not establish factual
accuracy or publication date.

The standalone static HTML reader remains a saved snapshot; it does not check
filesystem freshness in a browser. Reload it after an explicit successful reindex.

## Bounds and unavailable formats

The existing two-reference output limit remains. The indexed search considers at
most 48 candidate chunks per AND/OR pass and hashes at most 32 MiB of input per
query. Current-file fallback checks up to 32 files within the shared three-second
search window, with at most 2 MiB per text input and 16 MiB per PDF input. Limits
and failed reads are reported; absence of a result never establishes that the
library has no relevant information. Time checks occur between file operations;
filesystem I/O is not a hard real-time guarantee.

PDF direct reads and fallback scans preserve PDF page numbering, including
uppercase extensions. PDF extraction uses a bounded temporary snapshot outside
the library, then removes it; retrieval never modifies library documents.
`Read: ... page 0` is rejected instead of reading an unintended text offset.

Archive ranking remains the existing bounded ZIM workflow. A missing archive
tool no longer discards good document results. Full ZIM source-hash verification,
real archive extraction, real maps and native rendering are not newly qualified
by this change.

## Dispatch

`Read:`, `Search:`, `Reference:`, `Files:` and `Calc:` retain deterministic priority
and do not require a model. Incidental words such as "hard drive", "route table"
and "where is the beacon stored" no longer imply geographic routing.
Use clear geographic intent, for example `Directions from Alpha to Beta` or
`Map: where is Exampleville in Ohio` (the latter still requires the optional map
runtime). Unrelated questions clear a pending route. Recognized local-region and
endpoint replies can still fill a pending routing slot.

HTTP reference replies include retrieval status and visible library notices. A
missing/unreadable/unverified index uses source-only fallback instead of trying
inference on unverified cached chunks. A model cannot trigger Internet searches
or program updates; those remain explicit terminal commands.
