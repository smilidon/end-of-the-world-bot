# SPDX-License-Identifier: GPL-3.0-only
"""Checked user-local installation and portable Linux entry point (no downloads)."""
import argparse
import contextlib
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent


def check_runtime():
    if not sys.platform.startswith('linux') or sys.version_info < (3, 11):
        raise ValueError('Requires Linux and Python 3.11+. See START_HERE.md.')
    try:
        import sqlite3
        with contextlib.closing(sqlite3.connect(':memory:')) as db:
            db.execute('CREATE VIRTUAL TABLE probe USING fts5(text)')
    except Exception as exc:
        raise ValueError('Python needs SQLite with FTS5. See START_HERE.md.') from exc


def regular_path(root, name):
    """Reject ambiguous manifest names and symlinks, including parent components."""
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or p.as_posix() != name or
            any(part in {'.', '..'} for part in p.parts) or
            '\\' in name or any(ord(c) < 32 for c in name)):
        raise ValueError('Unsafe package path')
    target = root / name
    for path in [target, *target.parents]:
        if path.is_symlink():
            raise ValueError('Symlinks are not supported in package/install paths')
        if path == root:
            break
    if not target.is_file():
        raise ValueError('Package file missing: ' + name)
    return target


def package_files(root):
    """Validate the complete allowlist and hashes before copying or archiving."""
    names = regular_path(root, 'RELEASE_FILES.txt').read_text().splitlines()
    if len(names) != len(set(names)) or 'FILE_MANIFEST.sha256' not in names:
        raise ValueError('Invalid package allowlist')
    bodies = {name: regular_path(root, name).read_bytes() for name in names}
    hashes = {}
    for line in bodies['FILE_MANIFEST.sha256'].decode().splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch('[0-9a-f]{64}', digest) or name in hashes:
            raise ValueError('Invalid checksum manifest')
        hashes[name] = digest
    if set(hashes) != set(names) - {'FILE_MANIFEST.sha256'}:
        raise ValueError('Checksum manifest does not match allowlist')
    for name, digest in hashes.items():
        if hashlib.sha256(bodies[name]).hexdigest() != digest:
            raise ValueError('Package checksum mismatch: ' + name)
    return bodies


def install(destination):
    bodies = package_files(ROOT)
    target = Path(os.path.abspath(destination.expanduser()))
    for path in [target, *target.parents]:
        if path.is_symlink():
            raise ValueError('Symlink install paths are not supported')
    if target.exists():
        raise ValueError('Destination already exists; nothing overwritten. Choose a new folder or back up and move the old one.')
    # Reserve a new destination exclusively. No overwrites, renames, or removals.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    try:
        for name, body in bodies.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(body)
        (target / 'library' / 'guides').mkdir(parents=True)
    except OSError as exc:
        raise ValueError('Install incomplete in the new destination; original files were not changed. Check free space and permissions, then use a new folder.') from exc
    print('Installed to: ' + str(target))
    print('Open a terminal there and run: sh launch.sh doctor')
    print('Application and library stay in that folder; no system settings changed.')


def launch(arguments):
    parser = argparse.ArgumentParser(description='Portable offline reference CLI; see START_HERE.md')
    parser.add_argument('--library', type=Path, default=ROOT / 'library',
                        help='Dedicated document folder (default: library beside launch.sh)')
    parser.add_argument('command', choices=('doctor', 'index', 'search', 'ask', 'serve'))
    args, remainder = parser.parse_known_args(arguments)
    if args.command == 'doctor':
        if remainder:
            parser.error('doctor accepts no extra arguments')
        print('Linux / Python 3.11+ / SQLite FTS5: OK')
        print('PDF extraction: ' + ('available' if shutil.which('pdftotext') else
              "optional, missing; install Poppler using your distribution's package manager before indexing PDFs"))
        print('No runtime, model, maps, or document collection bundled. No network used.')
        return
    root = args.library.absolute()
    for path in [root, *root.parents]:
        if path.is_symlink():
            raise ValueError('Library path must not contain symlinks')
    if args.command == 'index':
        if remainder:
            parser.error('index accepts no extra arguments')
        if root == ROOT / 'library':
            (root / 'guides').mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError('Create a dedicated library with a guides folder first.')
        sys.path.insert(0, str(ROOT))
        import library_access
        if not shutil.which('pdftotext') and any(
                Path(name).suffix.lower() == '.pdf' for name in library_access.catalog(root)):
            raise ValueError("PDFs need pdftotext (Poppler). Install it using your distribution's package manager before indexing; no index was created.")
    if not root.is_dir():
        raise ValueError('Library unavailable. Put documents in library/guides and run: sh launch.sh index')
    sys.path.insert(0, str(ROOT))
    import bot
    sys.argv = ['bot.py', '--root', str(root), args.command, *remainder]
    bot.main()


def main():
    try:
        check_runtime()
        if len(sys.argv) > 1 and sys.argv[1] == '_install':
            parser = argparse.ArgumentParser(description='Install into a NEW user-owned folder; never overwrite')
            version = (ROOT / 'VERSION').read_text().strip()
            if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+', version):
                raise ValueError('Invalid release version')
            parser.add_argument('--dest', type=Path,
                                default=Path.home() / '.local/share/end-of-world-bot' / version)
            args = parser.parse_args(sys.argv[2:])
            install(args.dest)
        else:
            launch(sys.argv[1:] or ['--help'])
    except (ValueError, OSError) as exc:
        print('End of the World Bot: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
