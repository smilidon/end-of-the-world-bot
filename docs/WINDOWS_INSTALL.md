# Windows installation

## The short version

For a normal Windows 10 or Windows 11 PC, download:

**EndOfWorldBot-Windows-Setup-<version>.exe**

Double-click it and follow the installer. At the end, leave **Run the Windows/WSL setup assistant** checked.

The installer itself is per-user and does not need Administrator rights. The full Bot runs inside **Windows Subsystem for Linux (WSL)** because the project is still Linux-first. The assistant checks for WSL and tells you before anything needs Administrator approval, Internet access, or a Linux password.

## What to expect

1. Run the Windows Setup EXE.
2. The setup assistant checks whether WSL and a Linux distribution are ready.
3. If WSL/Ubuntu is missing, it offers to start Microsoft's normal `wsl --install -d Ubuntu` process. Windows may ask for Administrator approval or a restart.
4. Run **End of the World Bot Setup** from the Start menu again after Ubuntu finishes its first-run username/password setup.
5. If Linux prerequisites are missing, the assistant asks before using the Internet and before running `sudo apt-get`.
6. The verified release files are copied into your WSL home folder and `sh launch.sh doctor` is run as a self-check.

The application is installed inside WSL under:

`~/.local/share/end-of-world-bot/<version>`

A `current` symlink points to the active release.

## Add your documents

Inside Ubuntu/WSL, put files you are allowed to use in:

`~/.local/share/end-of-world-bot/current/library/guides`

Then run:

```sh
cd ~/.local/share/end-of-world-bot/current
sh launch.sh index
sh launch.sh search "your question"
```

PDF indexing needs Poppler (`pdftotext`). The setup assistant checks for it.

## Important Windows boundary

This is a **Windows installer for a WSL-backed Linux application**. It is not yet a native Windows rewrite. WSL is used so Windows users can install and run the existing tested Linux code without manually cloning Git repositories or assembling Python environments.

The setup assistant does not format disks, modify boot settings, or silently join networks. If WSL or Linux packages need installation, it asks first.

## SmartScreen

This project does not currently use a paid Windows code-signing certificate. Windows may therefore show an **Unknown publisher** / SmartScreen warning for a newly downloaded installer. Verify the release SHA-256 value from `SHA256SUMS` on the GitHub release page before running it.

## Uninstall

Use **Settings > Apps > Installed apps > End of the World Bot** to remove the Windows launcher/install files.

The WSL copy is deliberately separate so uninstalling the Windows launcher does not silently delete your Linux documents or indexes. To remove that copy later, delete:

`~/.local/share/end-of-world-bot`

from inside your WSL distribution after backing up anything you want to keep.
