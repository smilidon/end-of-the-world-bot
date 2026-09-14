# Source release verification

## Licensing audit — 2026-09-13

- All 42 existing synthetic tests passed on Linux with Python 3.14.7, including
  deterministic ZIP packaging, synthetic installation, Pipe/resource cleanup,
  retrieval/citations and manual-download transport fixtures. No real installation
  or publisher download was exercised in this audit.
- LICENSE matched the GNU-published GPLv3 text byte-for-byte. All 37 Python/Java/
  shell files carry GPL-3.0-only SPDX headers; adding the Pipe's missing comment
  leaves its parsed Python AST unchanged. All 21 staged provenance hashes match.
- The source allowlist contains 64 files; the checksum manifest covers the other
  63 files. Original source hashes and existing alpha.2 bootstrap pins remain
  historical evidence, not new provenance or release verification.
- Shared-worktree privacy scanning also traverses unrelated feature refs; use the
  single-branch procedure in [PUBLISH.md](PUBLISH.md) to qualify this branch's
  worktree, index and history without changing another branch or its allowlist.
- No live inference, authenticated Open WebUI, native routing/rendering, additional
  hardware platform or published-release qualification is claimed.

## Historical initial-snapshot checks — 2026-09-12

The record below describes the initial pre-publication snapshot, not current
file/test counts or GitHub state. Subsequent merged changes are summarized in
[CHANGELOG.md](../CHANGELOG.md); current license scope is in
[LICENSE_AUDIT.md](LICENSE_AUDIT.md).

- Linux: eight synthetic unit tests passed (six retained application tests and two
  privacy-guard regressions). Application coverage: offline indexing/search/direct
  reading, no-result handling, protected paths/symlinks, lexical ranking/HTML cleaning,
  street parsing and fallback, engine geometry/projection, PDF ingestion/page citations
  and route printing. Privacy regressions check sensitive patterns, source allowlisting
  and detection of sensitive content deleted from the current tree but retained in Git.
- Retrieval/PDF tests prohibit socket connections. Tests use temporary synthetic
  fixtures, not the original documents, maps, model or live adapter.
- Python compilation passed. All 16 staged SOURCE_MANIFEST hashes match. Fourteen
  copied original module hashes were independently rechecked and match; the two
  extracted helper entries retain previously recorded original ask.py provenance,
  not independently revalidated in this audit.
- The privacy guard checks worktree files, staged blobs and all reachable committed
  trees against RELEASE_FILES.txt and heuristic sensitive-content patterns. Review
  commit metadata separately for public identity suitability. Heuristics do not prove
  absence of every private address, identifier or secret. No original runtime/test
  data or history was imported. The candidate has no commits or remote.
- Fresh local synthetic Git clone validation: all eight tests, privacy scan and
  manifest verification, plus the README index/search/direct-read quickstart. The
  temporary snapshot uses synthetic commit identity; no candidate commit is implied.
- FILE_MANIFEST.sha256 covers the 40 other allowlisted source/docs/config files,
  excluding itself, .git and generated caches. No downloaded datasets or binaries.
- Validation dependencies are the existing installed ReportLab 5.0.0, Pillow 12.3.0
  and system pdftotext. Fresh network dependency installation was not tested.
- No actual model inference, ZIM extraction, real-map routing, native rendering,
  authenticated chat acceptance, Windows/macOS run or hosted CI run is claimed.
  Chat integration requires separate setup; not verified in clean release. See
  ARCHITECTURE.md for the original adapter, Guide: and legacy Map: omissions.

This qualifies a limited source snapshot, not the complete original chat appliance.
Publication remains a separate publisher-owned action.
