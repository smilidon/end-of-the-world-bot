# Source verification and integration status

## Current source inventory

The source allowlist contains 102 files; the checksum manifest covers the other
101 files. `tests/test_source_inventory.py` checks those counts, exact Git-index
membership and inclusion of both first-run USB regression files. The inventory
count regression introduced by PR #6 now lives in that dedicated test module;
the portable installer behavior tests remain unchanged.

The original strict privacy scanner checks the worktree, staged blobs and all
reachable committed trees. No historical membership bypass or installer-binary
exception is used. New privacy regressions check unlisted worktree, staged and
deleted historical files, and binary installers. A passing heuristic scan is not
proof that every possible private identifier is absent.

## Stage 2 reliability and optional online preparation

`index_builder.py` replaces the destructive first-run rebuild with a staged,
validated index and final publication. It preserves zero-byte/recognized-empty
stubs on failure and refuses unrelated SQLite databases, including empty FTS
indexes with additional user tables. File reads, directory discovery, file
counts, total input, extraction output and subprocess execution are bounded.
PDF extractor exit status, timeout, truncation and empty output are distinct from
success. The live index is not created until all documents and source hashes pass.
Source hashes, sizes, mtimes and indexing times are stored alongside the index.
The CLI reports attempted/indexed/skipped/failed counts and publication status.

The generation workflow shares the stricter extraction helper, checks free space
before copying, flushes directory entries before publication, removes failed
publication temporaries and reports post-commit flush failures as durability
warnings rather than claiming the old generation is still active. It retains
old and failed generations rather than automatically deleting owner data. Back
up the active publication and referenced generation before manually reclaiming
space; only clearly unreferenced generations should be removed while the bot is
stopped. Power-loss guarantees still require filesystem/hardware qualification.

Optional [online preparation](ONLINE.md) adds an explicit connection check,
DuckDuckGo-only search through `ddgs`, dated offline result caching and bounded
owner-selected document downloads into intake. Download receipts are hash-bound
to generation provenance. No online dependency is added to offline runtime, and
search results are not automatically promoted to indexed evidence.

The new synthetic regression suites are `tests/test_stage2.py` and
`tests/test_online_library.py`. An isolated local harness passed 29 focused
checks using copied original path/publisher helpers; that was not the complete
repository suite. Actual full-suite and clean-install results must be read from
the current commit's Actions checks. Live provider requests and physical media
were not qualified by those fixture tests.

## Stage 1 integration

PR #6 contributes the contributor documentation, templates, security-contact
route and privacy regressions. PR #4 retains the existing portable installation,
immutable document generations, bounded diagnostics and compact-context work.
Main-branch licensing and attribution updates are preserved. PR #9 is the
dependent Windows static-reader copier, reviewed separately.

The original failure at `da8cc23c608b5748851787aafba33531aaee8527` was two tracked
synthetic tests missing from the release allowlist. Its unit-test and clean-install
steps passed, but privacy failed and checksums/build were skipped. Those skipped
steps must not be described as passed. The Windows branch inherited this omission
and also downloaded a binary installer into the source checkout.

Current candidate SHAs and actual CI receipts belong in the pull-request
verification sections and GitHub Actions checks. Historical results below are not
verification of a newer head. Every candidate must pass:

```sh
python -m unittest discover -s tests -v
python tools/verify_clean_install.py --source .
python tools/privacy_scan.py
sha256sum -c FILE_MANIFEST.sha256
python tools/build_release.py --output "$(mktemp -d)"
```

Run from an isolated, fully fetched branch when checking history: unrelated local
refs also participate in the strict scan. Do not suppress findings to make an
unreviewed branch pass. The release builder creates a local validation artifact;
it does not publish a release. The published alpha.2 remains separate from this
unreleased source branch.

## Historical verification records

- Initial September 12 source qualification: eight synthetic tests covered
  indexing/search/direct reading, path checks, ranking/HTML cleaning, street
  parsing/fallback, route geometry, PDF citations/printing and privacy. These used
  temporary fixtures, not the original library, model or live adapter.
- September 14 licensing hygiene on main recorded matching GNU GPLv3 license
  text, SPDX/provenance checks and source publication hygiene. Historical original
  source hashes and alpha.2 bootstrap pins remain historical evidence, not new
  release verification. See [the license audit](LICENSE_AUDIT.md),
  [attribution](../NOTICE.md) and [publication procedure](PUBLISH.md).
- Portable feature development recorded 56 initial synthetic tests, later
  expanded to document intake, diagnostics, compact contexts and network
  observations. Its earlier Linux namespace/noexec and Chromium browser checks
  are historical development receipts, not fresh Stage 1 executions. The PR
  retains commit-specific qualification records.
- At the pre-integration PR #4 head `da8cc23`, CI ran 102 tests successfully and
  passed the clean-install journey before the inventory failure stopped the job.
  At the pre-integration PR #9 head `8a3ee64`, CI ran 114 tests, including
  PowerShell copier tests on Ubuntu, before its privacy/inventory failure.

## Qualification boundaries

The install verifier uses isolated temporary HOME/source/simulated-drive paths,
synthetic source/page references and unchanged-data sentinels. It exercises both
Bot and database modes, dry-run, index/search/export, document changes, failed
rebuild preservation, no-model fallback and moved-folder reads. Log/network tests
use fixtures, not live host logs or a physical Wi-Fi scan.

Existing log and network-diagnostic consent boundaries remain unchanged; Stage 2
prioritizes indexing reliability and useful optional network preparation rather
than expanding the separate diagnostic review. See [offline diagnostics](OFFLINE_DIAGNOSTICS.md)
and [network observations](NETWORK_DIAGNOSTICS.md).

No fresh real-model inference, authenticated Open WebUI, real-map routing, native
rendering, physical FAT/exFAT USB/power-loss, native Windows runtime, Raspberry Pi
or phone-inference qualification is claimed here. PowerShell on Linux does not
qualify Windows removable-drive behavior. No real user installations, services,
models or documents were modified. CI test-environment dependency installation
is separate from offline runtime use.
