# Source release verification — 2026-09-12

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

## Portable flash feature qualification (source branch, 2026-09-13)

- 56 synthetic tests cover existing behavior and both install profiles, exact
  confirmation, dry-run including selected fetch, unsafe targets/media replacement,
  scoped document create/read/update/print, stale edits and symlink/hardlink/FIFO
  refusal. Explicit manual preparation is fixture-tested; no real publisher fetch
  or inference was performed for this feature.
- The reusable `tools/verify_clean_install.py` checks fresh temporary HOME/source/
  simulated-drive installs, exact `R1` / `guides/beacon.txt text page 1 offset 0`
  citations, browser export, unchanged existing-data sentinels, refused reinstall,
  moved-folder use and simulated source deletion. Its remote mode requires an exact
  expected branch SHA; the PR records the post-push fresh-GitHub-clone receipt.
- The same two-mode journey passed in disposable Linux user/mount/network
  namespaces: only loopback, zero external routes, TEST-NET connect returning
  ENETUNREACH, and noexec/nosuid/nodev tmpfs with direct execution returning EACCES.
  This is actual offline/noexec enforcement, not physical USB/FAT qualification.
- Sandboxed Chromium 151.0.7922.34, offline context: file-only browser search and
  source labels, no-match state, inert hostile source text, 1280px desktop and
  390px mobile without horizontal overflow, no HTTP requests/page errors, and
  synthetic document Print-to-PDF passed. Browser tooling is optional verification,
  not a runtime dependency.
- Source privacy, manifests and deterministic ZIP checks remain required. No real
  trial, USB library, service, Open WebUI database or user documents were changed.
  Hardware/model speed, physical media/power-loss behavior, native non-Linux hosts
  and live third-party downloads remain outside this feature qualification.
