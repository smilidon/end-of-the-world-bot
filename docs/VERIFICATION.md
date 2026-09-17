# Source verification and integration status

## Current source inventory

The source allowlist contains 101 files; the checksum manifest covers the other
100 files. `tests/test_source_inventory.py` checks those counts, exact Git-index
membership and inclusion of both first-run USB regression files. The inventory
count regression introduced by PR #6 now lives in that dedicated test module;
the portable installer behavior tests remain unchanged.

The original strict privacy scanner checks the worktree, staged blobs and all
reachable committed trees. No historical membership bypass or installer-binary
exception is used. New privacy regressions check unlisted worktree, staged and
deleted historical files, and binary installers. A passing heuristic scan is not
proof that every possible private identifier is absent.

## Stage 1 integration

PR #6 contributes the contributor documentation, templates, security-contact
route and privacy regressions. PR #4 retains the existing portable installation,
immutable document generations, bounded diagnostics and compact-context work;
this integration changes its inventory/tests/documentation, not those runtime
implementations. Main-branch licensing and attribution updates are preserved.
PR #9 is the dependent Windows static-reader copier, reviewed separately.

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

## Qualification boundaries and separate diagnostic review

The install verifier uses isolated temporary HOME/source/simulated-drive paths,
synthetic source/page references and unchanged-data sentinels. It exercises both
Bot and database modes, dry-run, index/search/export, document changes, failed
rebuild preservation, no-model fallback and moved-folder reads. Log/network tests
use fixtures, not live host logs or a physical Wi-Fi scan.

Log discovery, redaction and optional network/Wi-Fi observations remain a
separate privacy-sensitive review area. Their presence in the branch does not
establish a root cause or authorize a scan; existing explicit consent and
bounded-source rules remain in force. See [offline diagnostics](OFFLINE_DIAGNOSTICS.md)
and [network observations](NETWORK_DIAGNOSTICS.md). Green synthetic tests are not
a substitute for that review or for the later indexing/retrieval reliability work.

No fresh real-model inference, authenticated Open WebUI, real-map routing, native
rendering, physical FAT/exFAT USB/power-loss, native Windows runtime, Raspberry Pi
or phone-inference qualification is claimed here. PowerShell on Linux does not
qualify Windows removable-drive behavior. No real user installations, services, models or documents were modified. CI
test-environment dependency installation is separate from offline runtime use.

## Windows CI workspace regression

The PowerShell repository installer is downloaded into a fresh directory beneath
RUNNER_TEMP, not the checkout, and removed on success or failure. Two shell-fixture
regressions execute the actual workflow block with fake wget/sudo/pwsh tools; they
assert that the checkout sentinel is unchanged and staging is cleaned. These tests
perform no downloads, privileged operations, or PowerShell installation. The
separate copier suite executes real PowerShell on Ubuntu CI, not native Windows.
