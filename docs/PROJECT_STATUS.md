# Project status

## Current source state

The project is a Linux-first, offline reference assistant. It can index a bounded
local document library, produce cited retrieval results, and export a static
offline browser reader.

The current-source Windows addition is a **verified USB data-folder copier**:

- `create-usb.ps1` copies only release-allowlisted, SHA-256-verified files into
  a new folder on an already mounted drive.
- It does not format, partition, make boot media, download, install software,
  overwrite an existing destination, or copy an arbitrary document library.
- A Linux-generated `reference.html` can be explicitly included and opened in
  a Windows browser for offline reading, search, and printing.

## Current limitations

- The Bot runtime, indexing, document intake, and model/chat features remain
  Linux-only.
- Windows has no local-model integration and does not automatically scan the
  user's Windows Documents folder.
- The static `reference.html` is a snapshot. New or changed documents require
  reindexing and exporting on Linux before the reader is refreshed.
- The Windows copier and its safety checks are tested with PowerShell fixtures
  on Linux CI; native Windows-drive and browser acceptance remain future
  validation work.

## Next intended work

Add a clearly user-triggered Windows-to-WSL helper that reindexes only a
project-owned folder on the drive, writes a fresh static browser export, and
opens it. It must remain offline, avoid system/WSL setup, and never silently
scan files outside that bounded folder.
