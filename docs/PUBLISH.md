# Publication handoff — publisher only

This source candidate has no inherited history. Publication is a separate action;
these instructions are not evidence of a commit, push, or successful hosted CI.

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

`RELEASE_FILES.txt` is the explicit source-package allowlist. The SHA-256 manifest
covers those files except itself; `.git`, generated caches and runtime data are
excluded. This is a source snapshot, not a wheel or bundled appliance installer.
