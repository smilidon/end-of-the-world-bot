#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build a deterministic installable ZIP from the audited source allowlist."""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from portable import package_files


def build(root, output):
    bodies = package_files(root)
    version = bodies['VERSION'].decode().strip()
    # Pre-release channels only; a bare X.Y.Z is still refused as a stable claim.
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-(?:alpha|beta|rc)\.[0-9]+', version):
        raise ValueError('Invalid release version')
    output = output.resolve()
    if output == root.resolve() or root.resolve() in output.parents:
        raise ValueError('Build output must be outside the source tree')
    output.mkdir(parents=True, exist_ok=True)
    stem = 'end-of-the-world-bot-' + version + '-linux-python'
    archive = output / (stem + '.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, body in sorted(bodies.items()):
            info = zipfile.ZipInfo(stem + '/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            # Scripts are deliberately runnable with sh on FAT/noexec media.
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, body)
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    archive = build(ROOT, args.output)
    print(archive.name)
    print(hashlib.sha256(archive.read_bytes()).hexdigest())
