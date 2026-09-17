# Source verification and integration status

## Current source inventory

The source allowlist contains 200 files; the checksum manifest covers the other
199 files. `tests/test_source_inventory.py` checks the exact Git-index,
release-allowlist and checksum-manifest membership, including the Windows USB regression files.
No inventory test or privacy rule was relaxed to accept an unlisted file.

## Stage 3: retrieval, network permission and update checking

[Retrieval](RETRIEVAL.md) expands the existing lexical aliases in FTS queries
without rewriting quoted evidence or requiring an index migration. Indexed
candidates are checked against Stage 2 source hashes or generation provenance.
Changed or missing candidates do not erase healthy results. Legacy indexes can
use bounded current-file reads instead of unchecked stale chunks. PDF fallback
keeps page references; missing/corrupt indexes and no matches have distinct
status information. Explicit document commands take priority over routing;
incidental words such as "drive" do not select a geographic tool, and unrelated
questions clear pending route state.

[Online operations](ONLINE.md) ask for interactive per-operation network approval,
default No, before public connection checks, DuckDuckGo searches, document
fetches, catalog downloads and current-bootstrap release requests. Decline, EOF,
Ctrl-C and non-interactive invocation do not grant approval. Offline cache reads
neither prompt nor connect. Localhost-only model calls remain separate.

The standard-library update checker obtains approval before requesting this
project's published GitHub release metadata. Numeric versions and release
channels are compared, dated cached results remain useful offline, and missing
information is reported as unknown. It does not download or install updates,
poll in the background, or identify unversioned branch changes. Use
`sh launch.sh updates` or `python3 update_checker.py`; `--offline` reads saved
metadata only. The published alpha.2 assets have not been replaced by this work.

The new regression suites are `tests/test_stage3_retrieval.py`,
`tests/test_stage3_dispatch.py` and `tests/test_stage3_network.py`.

## Concurrent main-branch integration

Main at `7d6d79e933f69346780fb88bb15da4a833f4f2fe` added Archify/Graft workflows and
agent-tool files while Stage 3 was being verified. Their bytes and licenses are
preserved here; both branches' ignore rules are combined. The release inventory
is the union of the existing feature files and those main additions. No owner
files were removed merely to make the inventory check pass.

These additions are development tooling, not bot runtime requirements. No agent
hook, maintenance workflow, release task or vendored tool was executed during
this reconciliation. Their independent network behavior is outside the bot
command permission mechanism and is not qualified by the Python tests. In
particular, the existing GitHub-hosted scheduled workflow is not a local bot
background update checker. Vendored development-tool license notices remain
with their files; this does not qualify a new bundled runtime distribution.

## Stage 2 and portable foundation retained

`index_builder.py` stages and validates an index before publication, preserving
zero-byte/recognized-empty stubs on failure and refusing populated or unrelated
SQLite databases. Actual file reads, discovery, input, output and subprocess
execution are bounded. Failed, timed-out, truncated or empty PDF extraction is
not successful indexing. Source hashes, sizes, mtimes and indexing times are
recorded and source bytes are rechecked before publication.

The immutable-generation reindex workflow shares the extraction helper,
preflights staging space, flushes files/directories and removes failed
publication temporaries. Post-commit flush warnings are distinct from failed
publication. Old and failed generations remain for deliberate owner cleanup;
back up the active publication and its generation before reclaiming space.
Power-loss guarantees require filesystem and hardware qualification.

Optional online preparation retains dated search caches, bounded selected-file
downloads, no-overwrite publication and hash-bound download receipts. Search
snippets are not automatically downloaded or promoted to indexed evidence.
Bot/database installation, workspace documents, compact model contexts and
confirmed log/network observations remain separate tested components.

## Verification gates and receipts

Run each candidate from an isolated checkout:

```sh
python -m unittest discover -s tests -v
python tools/verify_clean_install.py --source .
python tools/privacy_scan.py
sha256sum -c FILE_MANIFEST.sha256
python tools/build_release.py --output "$(mktemp -d)"
```

The strict privacy scanner checks the worktree, staged blobs and reachable
committed trees. A shallow CI checkout is not a full-history audit; unrelated
local refs also participate in a full-history scan. A passing heuristic scan is
not a guarantee that every private identifier is absent. The release builder
creates a validation artifact and does not publish a release.

Exact current commit SHAs and CI outcomes belong in PR #4 and GitHub Actions.
Do not treat historical records below as verification of a newer candidate:

- Stage 1 integrated contributor PR #6 and repaired missing USB regression-file
  inventory entries. Main's licensing and contributor documentation are retained.
- Stage 2 head `92cb3e9` passed 141 tests, clean-install verification, privacy,
  101 checksums and release building in Actions run `35177499912`.
- Initial Stage 3 head `4902344` ran 198 tests: 197 passed and one documentation
  count check failed because this page still reported 102/101 instead of 109/108.
- Repair `b8f0fa9` passed that count check. Its merge test against main `360d94d`
  again ran 198 tests, with the only failure identifying newly added Archify/Graft
  workflow files missing from the feature inventory. Later CI gates were skipped,
  not passed. This reconciliation also retains subsequent main agent additions.

## Qualification boundaries

Tests use synthetic providers, release listings, documents, network-call traps
and isolated temporary installation paths. The clean-install journey exercises
Bot/database modes, failed-rebuild preservation, moved-folder reading and
unchanged-data sentinels. Local sparse-harness checks are not a full clone test.

No live DuckDuckGo, publisher download or GitHub-checker compatibility is
established by fixture tests. Real Ollama, authenticated Open WebUI, native maps,
physical USB/FAT/exFAT power loss, native Windows, Raspberry Pi and phone inference
remain outside this stage's qualification. PowerShell tests on Linux do not
qualify Windows removable-drive behavior. CI dependency installation is separate
from offline bot use. See [online boundaries](ONLINE.md),
[retrieval limits](RETRIEVAL.md), [offline diagnostics](OFFLINE_DIAGNOSTICS.md),
[network observations](NETWORK_DIAGNOSTICS.md) and [the license audit](LICENSE_AUDIT.md).

## Windows static-reader qualification

`create-usb.ps1` is a native PowerShell copier for a new destination on an
already mounted drive. It validates the release allowlist and hashes, refuses
overwrites and unsafe Windows paths, and can include one explicitly selected,
previously generated `reference.html` file. The static page supports offline
excerpt search and printing; it does not run the Bot, index documents, invoke a
model or make the USB bootable. Synthetic PowerShell tests exercise the shipped
script. Native Windows, physical removable media and FAT/exFAT power-loss
behavior require separate release evidence before broader support claims.
