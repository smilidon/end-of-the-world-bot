# Publication handoff — publisher only

This repository contains public source history. Publication of a new release is a
separate action; these instructions are not evidence of a release or successful CI.

1. Review `git ls-files`, `git status --short`, all history and public author identity.
2. Run `python3 tools/privacy_scan.py`, `python3 -m unittest discover -s tests -v`,
   `sha256sum -c FILE_MANIFEST.sha256`, and `git diff --cached --check`.
3. Use the explicitly authorized destination and authenticated publisher identity.
   Inspect any existing repository before proceeding; do not guess a destination,
   overwrite a conflicting repository, or force-push. An unauthenticated 404 does
   not rule out a private repository.
4. If committing, use a verified public identity and this required message footer:

   ```sh
   git commit -m "Prepare audited offline reference source release" -m "— Thumbo"
   ```

5. Create/push only within the publisher's authorization. Inspect the resulting
   file tree and hosted CI before announcing publication. Do not publish `.git`
   internals, private handoffs, documents, model weights, maps or runtime artifacts.

The privacy guard scans all local refs. In a shared multi-worktree repository,
unrelated feature refs can have different allowlists; run release verification in
a fresh single-branch checkout of the exact publication commit. Do not expand the
release allowlist to include unrelated branch files or discard their refs.

`RELEASE_FILES.txt` is the explicit source-package allowlist. The SHA-256 manifest
covers those files except itself; `.git`, generated caches and runtime data are
excluded. The Linux portable ZIP adds a user-local installer and launcher to this source
snapshot; it is not a wheel, bundled runtime, or complete appliance.

## Reproducible Linux portable release

Run `python3 tools/build_release.py --output ../release-output` only after the
tests, privacy scan, and source hash checks above pass. The output must be outside
the repository and the archive must not already exist. The builder validates
manifest names, rejects symlinks/traversal and mismatched hashes, and includes
exactly the allowlisted source files. ZIP entries have fixed timestamps and plain
file permissions; launch scripts are invoked with `sh`, including on noexec media.

For a new release, update VERSION and the release-specific version/source pins in
bootstrap.py, then update the documented bootstrap hash and release links. Do not
retarget the existing alpha.2 pins or replace its published assets.
Use VERSION for a unique prerelease tag. Run hosted CI on the exact commit, merge
under existing policies, and verify the merged tree before building for upload.
Publish the ZIP, SHA256SUMS, START_HERE.md, LICENSE and NOTICE.md in a GitHub
prerelease targeting that tested commit. The archive itself contains complete
corresponding source. Download the published assets, verify their hashes, and
exercise the downloaded launcher and installation before announcing the release.
