# Create a non-bootable USB data folder from Windows

This **current-source** PowerShell helper copies verified application files into a
**new folder** on an already mounted drive. It is not in the historical alpha.2
release. Use an extracted source/package containing `create-usb.ps1`,
`RELEASE_FILES.txt` and `FILE_MANIFEST.sha256`; do not run it inside a ZIP viewer.

**This does not make a bootable USB.** No Rufus, ISO writer, formatting,
partitioning, raw-device writes, administrator access or runtime installation is
needed. Rufus is for boot media and is not appropriate for this data-folder copy.
The script does not download anything or change execution policy/system settings.

## Copy the package

Use Windows PowerShell 5.1 or PowerShell 7. In File Explorer, check the USB drive
letter and its available space. In PowerShell opened in the extracted source
folder, replace `E:` with the drive you selected and choose a folder that **does
not exist**, even as an empty folder:

```powershell
# Verify the package and preview without writing anything:
.\create-usb.ps1 -Destination 'E:\EndOfWorldBot' -WhatIf

# Copy after reviewing the destination:
.\create-usb.ps1 -Destination 'E:\EndOfWorldBot'
```

The source defaults to the script's folder, not the current working directory.
You may explicitly select another extracted package with
`-Source 'C:\Downloads\EndOfWorldBot'`. A destination's parent must already exist;
use a normal absolute drive-letter path, not a network share or device path.
The script does not detect or prove that a drive is removable: **you select it**.
An ordinary local folder also works. If local policy blocks scripts, follow your
administrator's policy; this helper does not bypass it.

Only release-allowlisted, SHA-256-verified files are copied. Existing libraries,
indexes, configuration, models, `.git`, and unlisted private files are not copied.
Hashes detect corruption, not publisher identity; obtain the source from a
trusted location. Package symlinks/junctions, traversal, device names, alternate
data streams and duplicate/case-colliding filenames are refused.

Copying uses a new sibling `.end-of-world-copy-<random-id>` staging folder and
verifies copied hashes before moving it to your chosen destination. Existing
destinations are refused, including ones created before the final move. Do not
modify source/destination folders during copying. If copying fails, any partial
staging folder is retained and its location is printed; inspect/remove that
specific folder manually after fixing space/permissions, then retry with a new
destination. Existing drive files are not deleted or overwritten. Wait for
`Copy complete`, then safely eject the drive using Windows.

## Windows can read a prepared static page, not run Bot

**The Bot runtime is Linux-only:** Python 3.11+, SQLite FTS5 and POSIX `sh`;
PDF indexing additionally needs Poppler `pdftotext`. This helper does not install
WSL, Python, models or a native Windows Bot runtime. Prepared WSL is a separate
Linux environment, not native Windows support.

A normal source/package has **no `reference.html` or reference collection**. To
include a reader, prepare an export on Linux from your authorized documents:

```sh
# In a Linux app folder with documents already in library/guides:
sh launch.sh index
sh launch.sh browser --output /path/to/new/reference.html
```

Use a new export filename; for an already indexed/installed library, follow
[document intake](DOCUMENT_INTAKE.md) and [recovery](RECOVERY.md) rather than
rebuilding over existing data. Copy the trusted generated HTML to Windows, then
explicitly include it in a **new** USB copy:

```powershell
.\create-usb.ps1 -Destination 'E:\EndOfWorldBot-reader' `
  -ReferenceHtml 'C:\Prepared\reference.html'
```

The helper copies that file byte-for-byte as `reference.html`; it does not run,
sanitize, index or generate HTML. Only select a trusted export. Double-click the
copied `reference.html` on Windows to read/search/print static excerpts in a modern
browser, offline, without Python or a server. It is a snapshot, not a live index,
AI chat, diagnostics, routing, document editor or complete original-PDF library.
Source file/page labels remain; original PDFs are not embedded. The existing
export caps at 10,000 chunks / 16 MiB of excerpt text and displays at most 40 search
results. New documents and refreshed exports must be prepared on Linux.
Without `-ReferenceHtml`, the script explicitly reports that no Windows reference
reader/content was included. It never silently copies a nearby HTML file.

## Verification boundary

`tests/test_windows_usb.py` executes the shipped script using PowerShell on Linux
when `pwsh` is on PATH (or `PWSH` names its executable). It covers exact package
copying, explicit generated-HTML inclusion, preview/no writes, existing-file
preservation, checksum/path/link refusals, and permission failures. Packaging
membership/reproducibility tests run even without PowerShell; execution tests
then report skips. These are Linux filesystem fixtures, **not native Windows
PowerShell 5.1, Windows junction/drive, physical USB, or Windows browser acceptance**.

```sh
PWSH=/path/to/pwsh python3 -m unittest discover -s tests -p 'test_windows_usb.py' -v
```
