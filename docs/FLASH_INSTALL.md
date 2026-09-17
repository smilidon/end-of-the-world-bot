# Install from a clone/download onto a flash drive

For Windows **folder copying only**, see the [PowerShell USB copy guide](WINDOWS_USB.md).
It does not make bootable media or provide a native Windows Bot runtime. The Linux
preparation workflow below is separate; Windows can read a prepared static HTML export.

This flow uses the **source you downloaded**, not the old pinned alpha.2 release.
Linux, POSIX sh, Python 3.11+ and SQLite FTS5 are required to install/prepare either
mode. It is not a bootable OS and does not bundle Python, Ollama, models or manuals.
No pip packages are required for installation, text retrieval, documents or the
static browser. Existing Ollama/Open WebUI/services are never reconfigured.

```sh
git clone https://github.com/smilidon/end-of-the-world-bot.git
cd end-of-the-world-bot
sh install.sh
```

For a downloaded source ZIP, extract and run the same `sh install.sh`. Mount your
flash drive through your desktop first. The installer lists only mounted,
writable devices marked removable or attached over USB by Linux `lsblk`.
An external USB SSD can also appear: verify the displayed device and mount path.
It never formats, partitions, mounts, erases or writes a raw device. If detection
fails, stop and check the mount/permissions; there is no force-removable override.

## Interactive choices

1. Select a drive, or explicitly type `local` for a user-local install.
2. **Bot is the default.** It installs the full existing local CLI, optional AI and
   optional chat/routing source plus the confined document workspace. Runtime
   dependencies for optional chat/routing remain separate; no complete AI appliance
   is promised. Retrieval works without a model. See [chat](CHAT.md).
3. **Browser/database only** prepares `reference.html`: open it directly in a
   browser, with no inference, Python server, account or network connection.
   Python is needed only to install, index new content and regenerate the page.
   `launch.sh ask` and `launch.sh document` are disabled in this profile.
   Source remains included for GPL compliance; this is not an OS-level prohibition
   on the owner manually running other code.
4. Models are optional and remain **on the host** by default for performance.
   After the USB speed/latency warning, Bot users may choose an empty `models/`
   directory on the selected drive. This records a relative placement plan only.
   **No model is downloaded, copied, loaded or selected automatically.**
5. Optionally fetch the existing catalog's eligible original manuals for personal
   noncommercial use. The default is no. The catalog preview is always shown,
   including manual-action items; nothing is bundled or relicensed. Actual fetching
   reuses the checksum-pinned, rights-aware downloader. Failed downloads remain in
   its report; rerun the downloader to resume. PDF indexing needs Poppler.
6. Review the plan and type the **exact absolute new destination** to confirm.
   The destination must be a new folder directly within the selected drive.
   Even an existing empty folder is refused. A partial new install is retained on
   failure; fix the cause and resume optional preparation or use a new destination.

No manual download means an **empty reference library**, not an emergency-content
collection. The generated browser explains this. To prepare content later:

```sh
# Run inside the installed folder; preview, then explicitly choose downloads.
python3 -I -B download_manuals.py --dest library/guides --all
python3 -I -B download_manuals.py --dest library/guides --all --fetch
sh launch.sh index
sh launch.sh browser
```

Alternatively put your own authorized `.txt`, `.md`, `.html` or `.pdf` documents in
`library/guides/`. Never use your whole home directory. The new export is
`reference-updated.html`; use `browser --output another-new-name.html` for subsequent
exports. Existing indexes/exports are not overwritten: preserve the old index
outside the library before explicit rebuilding, per [recovery](RECOVERY.md).
The static snapshot contains source excerpts and file/page labels, not embedded
original PDFs or live citation URLs. Copy originals and their rights notices
separately if needed. It uses deterministic lexical matching, returns at most
40 excerpts per search and caps export at 10,000 chunks / 16 MiB of excerpt text.
A visible limit notice tells you to use CLI search for larger libraries.
Untrusted content is displayed as text, not interpreted as HTML or instructions.

## Dry-run and repeatable automation

```sh
# Supply the actual mount path reported by your desktop/lsblk.
sh install.sh --drive "$USB_MOUNT" --mode bot --dry-run
# Use precisely the target printed by the dry-run:
sh install.sh --drive "$USB_MOUNT" --confirm-target "$USB_MOUNT/EndOfWorldBot"
# Explicit local installation (legacy --dest remains supported):
sh install.sh --dest "$PWD/../My Offline Bot" --mode database --dry-run
sh install.sh --local --dry-run
```

`--dry-run` validates dependencies, target, free space and package hashes, and
prints the catalog, but makes no directories, downloads or other changes, even
with `--fetch-manuals`. `--dest` alone is an explicit local-install choice and
confirmation of that path; removable safeguards apply when using `--drive`.
No-argument installation prompts; unattended input must use explicit options.
A local target must be separate from the source checkout and outside protected
system directories. Symlinks are rejected. No installed data is copied back into
source, and no existing library, trial, service or Open WebUI database is touched.

`bootstrap.py --from-source .` runs this same current-source flow without fetching
the historical release. Options such as `--dry-run`, `--drive`, `--mode` and
`--confirm-target` pass through. Without `--from-source`, bootstrap retains its
historical alpha.2 verification pins and release behavior; that release does not
contain this new feature. Never replace historical hashes with branch hashes.

## Scoped Bot documents and printing

The owner-provisioned root is **`workspace/` beside the installed launcher**. The
JSON tool interface accepts only `create`, `read`, `update` and `print`, with plain
`.txt` or `.md` names, no folders or absolute paths, and a 256 KiB text limit.
Updates require the current content SHA-256 returned by create/read. Conflicting
edits are refused. Print creates a new escaped `.print.html` file; open that file
and use the browser's Print / Save as PDF. No PDF package is required.

```sh
printf '%s\n' '{"action":"create","name":"Directions.md","text":"Draft directions. Verify source citations before use."}' | sh launch.sh document
printf '%s\n' '{"action":"read","name":"Directions.md"}' | sh launch.sh document
# For update, use the sha256 returned above as expected_sha256.
printf '%s\n' '{"action":"print","name":"Directions.md"}' | sh launch.sh document
```

An embedding application calls `document_workspace.Workspace(owner_fixed_root)`
and `.dispatch(request)`. **Do not expose the constructor/root or a shell to the
model.** This PR provides the restricted tool API and CLI, not an autonomous
model-tool execution loop. The existing model remains answer-only. A user or
trusted caller explicitly submits document operations after reviewing generated
text; retrieved documents and model responses cannot invoke tools on their own.

Component-wise no-follow directory/file opens prevent symlink traversal; regular
single-link files only, exclusive creation and atomic update replacement prevent
hardlink truncation. A root-directory lock serializes cooperating writers.
No deletion, arbitrary host read/write, command execution, service/config edit,
network operation or general file-browser API is available through this interface.
It is not a sandbox against an owner/malicious local process changing mounts or
moving directories with OS privileges. Linux filesystem support for these calls is
required. Test your selected filesystem; no physical FAT/exFAT drive was qualified.

## Optional bounded offline diagnostic observations

Bot also provides `sh launch.sh diagnose` for explicitly pasted log text. It does
not inspect the host or run commands. Redacted observations use separate compact
Markdown references and can become a printable workspace document. See
[offline diagnostics, privacy limits and air-gapped guide intake](OFFLINE_DIAGNOSTICS.md).

## Optional model on USB

Choose `--models usb` only with `--drive` (or a temporary simulation). This creates
an empty `models/` with instructions and records `model_location: "models"`, so the
installation still moves between hosts. It does **not** change an existing Ollama
service, shell configuration, environment or model cache. If you later choose to
use it, consult Ollama's `OLLAMA_MODELS` documentation and set that variable only
for a separately managed process you explicitly start, using the current absolute
path to this directory. Do not start a second process on an occupied port.
Choose/download a model separately and explicitly, review its license and size,
and test it before going offline. Use an existing installed model by exact name:

```sh
sh launch.sh ask 'Your reference question' --model YOUR_INSTALLED_MODEL
```

CPU-only inference is supported by the existing code; slow machines may exceed
the bounded request timeout. Retrieval/browser mode remains useful when inference
is too slow. USB 2 flash can take minutes to load weights; host SSD storage is the
recommended default. No automatic model fallback or download exists.

## Portable use, backup and verification

Use `sh launch.sh`, including on media without Unix executable bits; Python stays
on the host. No hardcoded drive path is saved. Stop running commands, back up
`library/`, `workspace/`, your reference snapshots and any selected `models/`, then
safely eject. Install upgrades side by side and copy your data deliberately.
Never delete a real installation to test recovery.

```sh
python3 tools/verify_clean_install.py --source .
# After publishing a branch, verify exactly the pushed commit via a NEW clone:
python3 tools/verify_clean_install.py --repo https://github.com/smilidon/end-of-the-world-bot.git --ref BRANCH --expect-sha FULL_COMMIT_SHA
```

The verifier uses fresh temporary source, HOME, simulated-drive and sentinel data;
checks both modes, dry-run, exact citations, document editing/printing, reinstall
refusal and movement after hiding only its disposable source copy. It never
writes to a real removable drive. `--simulate-drive` accepts only a dedicated
existing directory on the host temporary filesystem, not a mounted drive.
Source-copy proof, fresh-GitHub-clone proof, physical USB, actual disconnected/
noexec-mount tests and real model inference are separate claims.

## Offline updates and compact operation

Use `data/intake/`, `sh launch.sh intake-scan` and `sh launch.sh reindex` for
[atomic document updates](DOCUMENT_INTAKE.md) in either profile. The old manual
index-move procedure remains for legacy external libraries, not this managed intake.
Bot additionally supports [confirmed Linux log discovery](OFFLINE_DIAGNOSTICS.md)
and [tiny/standard compact prompts](COMPACT_CONTEXT.md). None of these changes
automatically downloads models or touches another installation.

Bot mode also includes [optional confirmed network observations](NETWORK_DIAGNOSTICS.md).
They require no model. Database-only mode does not expose diagnostic commands.
