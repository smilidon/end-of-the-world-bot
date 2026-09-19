#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Pinned Linux setup. Installs to a NEW folder, plans manuals unless --fetch."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

VERSION = '0.1.0-alpha.3'
BASE = 'https://github.com/smilidon/end-of-the-world-bot/releases/download/v' + VERSION + '/'


def ask_network(description):
    """Standalone bootstrap equivalent of network_permission.ask()."""
    try:
        if not sys.stdin.isatty():
            print('Network access not approved: run interactively to answer the prompt.', file=sys.stderr)
            return False
        print(description, file=sys.stderr)
        print('Allow network access for this operation? [y/N] ', end='', flush=True, file=sys.stderr)
        return input().strip().casefold() in {'y', 'yes'}
    except (EOFError, OSError, AttributeError, KeyboardInterrupt):
        return False


def get(name, cap):
    with urllib.request.urlopen(BASE + name, timeout=30) as r:
        data = r.read(cap + 1)
    if len(data) > cap:
        raise ValueError('Release asset too large')
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-source', type=Path, help='Use a trusted local clone/download and its current installer; no release network fetch')
    p.add_argument('--dest', type=Path, help='New user-owned install folder (required for pinned release)')
    p.add_argument('--fetch', action='store_true', help='Download all eligible personal noncommercial manuals after install')
    a, extra = p.parse_known_args()
    if a.from_source:
        source = a.from_source.expanduser().resolve()
        command = [sys.executable, '-I', '-B', str(source / 'portable.py'), '_install', *extra]
        if a.dest:
            command.extend(['--dest', str(a.dest)])
        if a.fetch:
            command.append('--fetch-manuals')
        return subprocess.run(command).returncode
    if extra or not a.dest:
        p.error('Pinned release requires --dest; flash/mode/dry-run options require --from-source PATH')
    if not sys.platform.startswith('linux') or sys.version_info < (3, 11):
        p.error('Linux Python 3.11+ required. Windows: use a prepared WSL Linux terminal. Native Windows/macOS unqualified.')
    dest = Path(os.path.abspath(a.dest.expanduser()))
    if dest.exists() or any(x.is_symlink() for x in [dest, *dest.parents]):
        p.error('Destination exists or contains symlinks; choose a new folder')
    ancestor = dest.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < 100*1024*1024:
        p.error('At least 100 MiB free space required for setup and eligible manuals')
    import sqlite3
    db = sqlite3.connect(':memory:')
    try:
        db.execute('CREATE VIRTUAL TABLE probe USING fts5(text)')
    finally:
        db.close()
    if not ask_network('Download the pinned program release from GitHub and its release storage, using the existing connection. No network settings changed.'):
        print('Cancelled; no release download or installation.')
        return 0
    name = 'end-of-the-world-bot-' + VERSION + '-linux-python.zip'
    checks = dict((line.split('  ',1)[1],line.split('  ',1)[0]) for line in get('SHA256SUMS',65536).decode().splitlines())
    archive = get(name,4*1024*1024)
    if hashlib.sha256(archive).hexdigest() != checks[name]:
        raise ValueError('Release ZIP checksum failed')
    with tempfile.TemporaryDirectory(prefix='offline-bot-setup-') as td:
        root = Path(td)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            names = set()
            for info in z.infolist():
                path = PurePosixPath(info.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in info.filename or path.as_posix()!=info.filename or len(path.parts)<2 or path.parts[0]!=name[:-4] or info.filename in names or stat.S_ISLNK(info.external_attr >> 16) or info.file_size > 2*1024*1024):
                    raise ValueError('Unsafe archive member')
                names.add(info.filename)
            if sum(i.file_size for i in z.infolist()) > 16*1024*1024:
                raise ValueError('Expanded release too large')
            bodies = {str(PurePosixPath(i.filename).relative_to(name[:-4])):z.read(i) for i in z.infolist()}
            release_files = bodies.get('RELEASE_FILES.txt', b'').decode().splitlines()
            if not release_files or len(release_files) != len(set(release_files)):
                raise ValueError('Invalid release allowlist')
            if set(release_files) != set(bodies):
                raise ValueError('Release archive membership does not match allowlist')
            manifest_lines = bodies.get('FILE_MANIFEST.sha256', b'').decode().splitlines()
            manifest = {}
            for line in manifest_lines:
                digest, sep, member = line.partition('  ')
                if (not sep or len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest)
                        or not member or member in manifest):
                    raise ValueError('Invalid internal checksum manifest')
                manifest[member] = digest
            if set(manifest) != set(release_files) - {'FILE_MANIFEST.sha256'}:
                raise ValueError('Internal checksum manifest does not match release allowlist')
            for member, digest in manifest.items():
                if hashlib.sha256(bodies[member]).hexdigest() != digest:
                    raise ValueError('Internal release checksum failed: ' + member)
            # Only after archive membership and internal hashes pass, extract.
            z.extractall(root)
        app = root / name[:-4]
        subprocess.run([sys.executable,'-I','-B',str(app/'portable.py'),'_install','--dest',str(dest)],check=True)
    command = [sys.executable,'-I','-B',str(dest/'download_manuals.py'),'--dest',str(dest/'library/guides'),'--all']
    if a.fetch:
        if not ask_network('Fetch the selected pinned catalog manuals from their publishers, including robots checks and retries. The program is already installed.'):
            print('Installed; manual downloads cancelled.')
            return 0
        command.append('--fetch')
    result = subprocess.run(command)
    print('Installed. Read INSTALL_AND_DOWNLOAD.md in the destination for indexing, references and any missing downloads.')
    if not shutil.which('pdftotext'):
        print('PDF indexing still needs Poppler pdftotext; no system packages installed.')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
