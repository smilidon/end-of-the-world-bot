# Known limits and qualification boundaries

- This is a working CLI snapshot plus optional experimental routing source, not
  a complete portable chat appliance installer.
- Linux was exercised. Windows/macOS are untested. fcntl, resource, POSIX process
  groups, O_NOFOLLOW/dirfd and /proc-based ZIM citation extraction are nonportable.
- Text/PDF FTS5 indexing and direct text reads are tested. ZIM CLI availability,
  output formats and current real archive behavior are not qualified here.
- Index/search extraction is bounded and can silently truncate long files.
  Scanned PDFs have no OCR pipeline. A stale index can disagree with changed files.
- Source IDs identify excerpts; model-generated citations/answers are not fact
  verification. The optional 4K/64-output-token model configuration is short-form.
  Its HTTP timeout is not a guaranteed process-wide inference cancellation.
- Citation server is explicitly allowlisted, loopback-only and unauthenticated.
  Do not proxy it onto a LAN or internet. Browser rendering and WebUI integration
  are separate from Python serving tests.
- Chat integration requires separate setup; not verified in clean release.
  The original optional Function/Pipe adapter is not bundled.
- Optional OsmAnd bridge APIs depend on the original unpinned master snapshot;
  no fresh portable binary build, native render, route/fuel access test, model
  inference or GitHub Actions run is claimed.
- No medical, treatment, emergency, navigational or hardware performance guarantee.
  Documents may be stale, incomplete or contradictory.
