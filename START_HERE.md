# End of the World Bot — Linux portable alpha

## New: interactive flash installation from current source

## Windows users

> **Windows SmartScreen note:** the Windows installer may show **Unknown publisher**. This is expected because End of the World Bot is a free, open-source project and we currently do not have the resources to fund a commercial Windows code-signing certificate. Verify the installer against `SHA256SUMS` from the official GitHub release before choosing **More info → Run anyway**. See [the Windows install guide](docs/WINDOWS_INSTALL.md).


Use the release asset `EndOfWorldBot-Windows-Setup-<version>.exe` and follow the guided setup assistant. It installs the verified files per-user and helps set up the existing Linux application through Windows Subsystem for Linux (WSL). The Bot runtime is still Linux-based; this is not a native Windows rewrite. See [WINDOWS_INSTALL.md](docs/WINDOWS_INSTALL.md).

Clone/download this repository and run **`sh install.sh`** for interactive drive
selection. **Bot is the default**; browser/database-only mode generates a static
offline reference page without inference. Models are optional and normally stay
on the host. Preview with `sh install.sh --interactive --dry-run`.
See [the complete flash installation guide](docs/FLASH_INSTALL.md) for confirmation,
manual-content choices, confined documents/printing, USB model limits and clean-room
verification. Existing files/services are preserved. No models or manuals are bundled.
The release commands below still target alpha.3, not this new flow.

**Preparing a USB from Windows?** Follow the [PowerShell copy guide](docs/WINDOWS_USB.md).
It creates a new non-bootable data folder, not a Windows Bot installation. Only
a separately prepared `reference.html` can be read/searched/printed on Windows;
Bot runtime and content indexing remain Linux-only.

Version **0.1.0-beta.1**. A local document search tool with source excerpts and
file/page citations. This download includes a working installer, portable launcher,
and complete GPL-3.0-only application source. It is **not a bootable operating
system, bundled AI appliance, or universal installer**. No Python runtime, pip
packages, models, maps, or document collection are included.

## Prepare the computer before going offline

- Linux with a POSIX shell (`sh`) and **Python 3.11+ with SQLite FTS5**. The package
  contains no native binaries; Linux x86_64 is the release-tested host. Other Linux
  architectures are unqualified; Windows and macOS are not supported by this release.
- For **PDFs only**, Poppler's `pdftotext` must be on PATH. Text/Markdown/HTML
  indexing needs no pip packages. ZIM, maps, AI, and chat need separate setup.
- A writable folder or flash drive with room for your own documents and index.
  Safely eject it after commands finish. No drive formatting or boot-image flashing is required.

If prerequisites are missing, arrange them through your Linux distribution's
package manager while online. Debian/Ubuntu package names are `python3` and
`poppler-utils`; Fedora uses `python3` and `poppler-utils`. Some older distributions
need a newer Python. The installer never downloads runtimes/models, runs sudo, changes
host packages, or modifies shell settings. Current-source installation offers
manual downloads only after explicit selection. To choose an already-installed Python,
use `PYTHON=/path/to/python3 sh launch.sh doctor` (quote a path containing spaces).

## Open the download

Download the versioned `linux-python.zip` and `SHA256SUMS` from the
[GitHub release](https://github.com/smilidon/end-of-the-world-bot/releases/tag/v0.1.0-beta.1).
Verify the ZIP before extraction from the folder containing both files:

```sh
sha256sum --ignore-missing -c SHA256SUMS
```

Ensure the ZIP itself reports `OK`. Extract with your file manager or
`python3 -m zipfile -e end-of-the-world-bot-0.1.0-beta.1-linux-python.zip .`.
Open a terminal inside the extracted folder. These instructions always use `sh`
so executable permission bits are unnecessary on FAT or a `noexec` flash drive:

```sh
sh launch.sh doctor
```

A Python installed on the computer runs the files. Do not place that interpreter
on `noexec` media. Checksums detect corruption, not a compromised publisher.

## Option A: carry the folder on a flash drive

Copy the **whole extracted folder** to your flash drive, then run the commands
below there. Application paths are determined at launch time. Its `library/`
folder moves with it; no computer-specific path is saved. Paths containing spaces
are supported. Use `sh "/path with spaces/to/launch.sh" doctor` from another folder.
Do not make symlinks for application or library directories.

## Option B: install a local copy without the flash wizard

```sh
sh install.sh --dest "$HOME/.local/share/end-of-world-bot/0.1.0-beta.1"
```

This copies the verified application into
`~/.local/share/end-of-world-bot/0.1.0-beta.1` and creates an empty `library/guides/`.
Open a terminal in that folder and use `sh launch.sh ...` there. For a different
**new** folder (including a flash-drive folder), use:

```sh
sh install.sh --dest "../My Offline Bot"
```

An existing destination is always refused, including an empty one. No existing
application, library, config, or index is overwritten. The installer copies only
allowlisted release files, not a library you may have added to the source folder.
If disk space or permissions interrupt installation, the new partial destination
is retained; choose another new folder after correcting the problem.

## Managed offline updates (current source)

Copy approved `.txt`, `.md` or extractable PDFs to installed `data/intake/`, run
`sh launch.sh intake-scan` then `sh launch.sh reindex`, and reload `reference.html`.
Both profiles use the new snapshot; failures preserve the old search and page. See
[bounded intake and recovery](docs/DOCUMENT_INTAKE.md). The examples below also
remain valid for the legacy manually managed library.

## Try a synthetic document, with no model or internet

Inside your portable or installed folder:

```sh
mkdir -p library/guides
printf '%s\n' 'SYNTHETIC: The amber beacon batteries belong in the blue cabinet. This is a software fixture, not real advice.' > library/guides/example.txt
sh launch.sh index
sh launch.sh search 'Where are the beacon batteries?'
sh launch.sh search 'Read: guides/example.txt'
```

Expect JSON containing source ID `R1`, `guides/example.txt`, and the blue cabinet
excerpt. These are retrieved source excerpts, not AI-generated answers. Replace
this fixture with documents you have the right to use. Add PDFs to `library/guides/`
after preparing Poppler; results cite their PDF page. Documents and extracted text
remain in the library; nothing is uploaded by these core commands.

The index is deliberately never overwritten. Before indexing changed documents,
move `library/local-qa/guides.sqlite` to a backup folder **outside the library**,
then run `sh launch.sh index` again. See [recovery](docs/RECOVERY.md). Use only a
purpose-built library, never your whole personal folder. An external library can
be selected explicitly: `sh launch.sh --library "../My Library" search 'beacon'`.
Relative external library paths are relative to your current terminal directory.

To open PDF citation links, follow the explicit file allowlist example in
[README.md](README.md) and use `sh launch.sh serve --allowlist documents.json`.
The citation server is loopback-only. AI (`ask --model ...`), Open WebUI, ZIM and
maps remain optional and separate: [chat](docs/CHAT.md), [routing](docs/ROUTING.md).
The basic CLI is not a complete chat interface.

## Updating, backups, and uninstalling

Install each new version in a **new folder**. Keep the old folder as your backup;
copy your `library/` and any configuration files to the new version deliberately,
or select the existing external library with `--library`. Do not run concurrent
indexers against one library. A repeated install never modifies user data.

There is no system-wide registration, background service, PATH edit, or separate
uninstaller. To stop using this version, move its entire folder to a backup
location. Before deleting any application folder yourself, save its `library/`,
indexes, `workspace/` documents/prints, reference HTML snapshots, optional `models/`,
and any config files you created outside that folder. A portable folder
contains your data: deleting it without a backup deletes that data too. Removing
the original ZIP has no effect on an extracted or installed copy.

## Source and licensing

[LICENSE](LICENSE) is GPL-3.0-only; keep [NOTICE.md](NOTICE.md). All corresponding
application source, tests, manifests, and build scripts are inside this archive.
No third-party runtime or libraries are redistributed, so their preparation and
licenses remain separate; see [license audit](docs/LICENSE_AUDIT.md).
This alpha retains the bounded-search and source limitations in [README.md](README.md).

## Optional recovered manual downloads

See [INSTALL_AND_DOWNLOAD.md](INSTALL_AND_DOWNLOAD.md) for a dry-run-first downloader, complete rights-aware inventory and reusable terminal-agent prompt. No manuals are bundled.

## Optional Linux network observations (Bot only)

Run `sh launch.sh network-diagnose` to preview a limited read-only scope before
confirming. Wi-Fi scanning requires a separate second confirmation and optional
preinstalled `iw`; no joining, credentials, repairs or elevation. Reports can be
saved/printed within `workspace/`. See [network boundaries](docs/NETWORK_DIAGNOSTICS.md).
