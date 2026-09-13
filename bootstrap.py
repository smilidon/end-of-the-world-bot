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

VERSION = '0.1.0-alpha.2'
BASE = 'https://github.com/smilidon/end-of-the-world-bot/releases/download/v' + VERSION + '/'
PINNED = {'AddressProbe.java': '898580e38c1f79202d353d08e3a9fed53daa9f29cd1831440e009c14ab9959eb', 'CorridorProbe.java': '890d9e23785eef0e0739a7448c00ecbc8260ac53414b18b1fbdb3bfe5b30d3c1', 'MultiRouteGeometry.java': 'cb7ed7cb4b897dafa5b23eec15eef58bd17a657007275601f656d951c4024a05', 'NamedPlaces.java': 'b18cd60b58c47b296733c5887e9a1d400c6c45adbe31b653209505419ee5be43', 'VERSION': 'd6786e528559282abdc85379c00255d2bce04358365e10cc74d08162440e006c', 'bot.py': '01ce5f61d5abfd64deb0b6718fd5277968775b980759f26eb699f48901912595', 'citation_links.py': '2a4cae1a3e052541ad3e061be713e5ad1e29451155020045818b20c62c40744b', 'corridor_routing.py': 'f950769cdc376350e319519169bb14c7280c5062958d58b458ce99a890f1f444', 'download_manuals.py': 'cc1d85cc53afc881e950d17a9d53d7524a6fc65bc9fe727c8f1df8aaf91595c3', 'http_adapter.py': '558530cea5a9df3f02224d0b7fc1e59bb9d4a4069af2b1a8bf3d5a8999ccb075', 'install.sh': 'fc68e23c63874a125e0966fdf648c2076a354e5b80e179b50c66f2faa3fc1275', 'launch.sh': '313a89c0b87ff42c8afd1febe7f4e4fdb7bbee491fcf602e44dc65fb5682f499', 'library_access.py': '76245a94cafbf2c0ae41550d46d20d38facbfef9cc9c0a200361fdfc071898fa', 'local_visuals/NativeMap.java': '3b15a87561cbb44b44651e5776d250ad2ae7440b34d0cd4f91a78bfdf55fe2be', 'local_visuals/RouteGeometry.java': '619b89a808d2bf7e5d4146fdfbed40ef7fc92181f3bc2a029a9f7026410c0ece', 'local_visuals/__init__.py': '005968a953091e26becb75148418187a7737a57731485eec99d23fc07a6677b9', 'local_visuals/artifact_config.py': 'f746ad64989c31cd53c135ad5890b8109e7910a0726c2349248266a9d914f303', 'local_visuals/export.py': '9b7d60b461a2520fc65e9d6a7f787289c10682b4b3fabeb9cee27bf0da399b62', 'local_visuals/print_route_formatter.py': '7b04cd59685542ec02747cee570f4a9b7b6aa42ba9ecd81526a5174264ecd5b1', 'local_visuals/print_routes.py': '36012dd660316860383031fcf11db80599a44d2142743ae87a4b2e3a71d0da6c', 'local_visuals/route_map.py': '47fbc8cb1d89efe63ee39491ee40210d9802eef23be9f890421c74a4ebda8ca3', 'local_visuals/units.py': '03cc3f113bb8e49b42044ff0a393b2ccb3cd71e29fab8f53485c375a62d6eb25', 'manuals.json': '43896fc4d120f6eb51495da2e333c7deaa86e5bee380be15b61506585a83d3bb', 'model_query.py': 'a30409dc4154cd5aca6b477a1e94cb1c0585cd5b5daa5949e96637e9b306ee82', 'multistate_routing.py': '773b68e22d7fae8e626fdd3cc69a802267e21b9fe507953f0448f5e2550cd83a', 'named_routing.py': '0790e7356995e58a5222bb104a9b8c7a333ca939b212442587f557aa6b77416a', 'openwebui_pipe.py': '27a260d03a9c769324366fcb6e47aeba6fb29f224178334e660856fbb9162e98', 'portable.py': 'f9ee495ebe3b4320f85a624e9b10ec2a05c08f8ada8280769ce2f4a1dc87cbc8', 'reference_helpers.py': '4210750ff4fb0256ea3e45c91fe461663018ddd4718f22aac0e6aeedcb4ed782', 'route_adapter.py': '61a518ca4ef27dcfb959d916d7bb049d366c29bd5deb811d81ec8403e4d4cba0', 'tests/test_chat.py': '6481a8fadfb6d7d0146eff890d8eb7d2e686e2400e558b7c267fb1beb3a006a8', 'tests/test_core.py': '9cfdd334ca49c60693a5061a890dd371e2bbeef644e0e449f9117366d6238c6a', 'tests/test_manuals.py': 'f69fcdca9fe1701c679be3152df6f27cb31dc139ef0931898cf1af30d24fa9f8', 'tests/test_portable.py': '5fc1322ded042774af43da8971dc8cf54e3fbff6eecd97087b3dbd94b0c7169a', 'tests/test_privacy.py': '5f67a944653427924a35260006acb5166e0ff8a0ba336bc48da4ecd08b0dd5d2', 'tests/test_resource_cleanup.py': '89923947760c85349459eede3d5a2713f66f34f4c45f9a584f847cce17c570eb', 'tools/build_release.py': '58b2cc2fac8ba264d9bbb41b274e07168ed370d0079b3df959ce6ec66572186c', 'tools/privacy_scan.py': '350eaf7beff59debeb3dcfd3d8679c1cc9eca3d269def9c8493d9c7fd07919eb'}


def get(name, cap):
    with urllib.request.urlopen(BASE + name, timeout=30) as r:
        data = r.read(cap + 1)
    if len(data) > cap:
        raise ValueError('Release asset too large')
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dest', type=Path, required=True, help='New user-owned install folder')
    p.add_argument('--fetch', action='store_true', help='Download all eligible personal noncommercial manuals after install')
    a = p.parse_args()
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
            code = {n for n in bodies if n.endswith(('.py','.sh','.java')) and n != 'bootstrap.py'}
            if code != {n for n in PINNED if n.endswith(('.py','.sh','.java'))}:
                raise ValueError('Unexpected executable source membership')
            for n, digest in PINNED.items():
                if hashlib.sha256(bodies[n]).hexdigest() != digest:
                    raise ValueError('Pinned source/catalog verification failed')
            # Only after ZIP membership and executable-source pins pass, extract.
            z.extractall(root)
        app = root / name[:-4]
        subprocess.run([sys.executable,'-I','-B',str(app/'portable.py'),'_install','--dest',str(dest)],check=True)
    command = [sys.executable,'-I','-B',str(dest/'download_manuals.py'),'--dest',str(dest/'library/guides'),'--all']
    if a.fetch:
        command.append('--fetch')
    result = subprocess.run(command)
    print('Installed. Read INSTALL_AND_DOWNLOAD.md in the destination for indexing, references and any missing downloads.')
    if not shutil.which('pdftotext'):
        print('PDF indexing still needs Poppler pdftotext; no system packages installed.')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
