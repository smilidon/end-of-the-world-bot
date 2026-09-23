# SPDX-License-Identifier: GPL-3.0-only
"""Source-package allowlist and heuristic worktree/index/history privacy guard."""
from pathlib import Path
import hashlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'host_path': r'(?:(?<![A-Za-z0-9._/-])/(?:home|Users|run/media|media|mnt)/[^\s]+|[A-Z]:\\(?:Users|Documents and Settings)\\[^\s]+)',
    'secret': r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9_.-]{20,})',
    'signed_url': r'https?://[^\s]+[?&](?:X-Amz-[A-Za-z-]+|X-Goog-[A-Za-z-]+|access_token|token|signature|sig)=',
    'email': r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
    'url_credentials': r'https?://[^\s/]+:[^\s/]+@',
}
IGNORED = {'.git', '.venv', '__pycache__', '.pytest_cache', 'graft'}
# Binaries cannot be pattern-scanned, so each shipped one is pinned by exact
# SHA-256. Editing or swapping a file changes its digest and restores the
# 'binary' finding; unpinned binaries are still rejected.
BINARIES = {
    'eotwb-icon.ico': 'a0935c109ab33a1fa12bf7134bbf944c969333c97a8471534edadb5f9023b7a9',
    'eotwb-icon.png': 'f2289c37e27fdbdef2dd7d763643d06983705af7f67ab87c2e254cdb19d67485',
}


def inspect(name, body, allowed, check_allowlist=True):
    findings = []
    if check_allowlist and name not in allowed:
        findings.append((name, 'not in source allowlist'))
    try:
        text = body.decode('utf-8')
    except UnicodeError:
        if BINARIES.get(name) == hashlib.sha256(body).hexdigest():
            return findings
        return findings + [(name, 'binary')]
    for label, pattern in RULES.items():
        if re.search(pattern, text, re.I):
            findings.append((name, label))
    return findings


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.DEVNULL)


def main():
    allowed = set((ROOT / 'RELEASE_FILES.txt').read_text().splitlines())
    findings = []
    files = 0
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if any(part in IGNORED for part in relative.parts):
            continue
        if path.is_symlink():
            findings.append((str(relative), 'symlink'))
        elif path.is_file():
            files += 1
            findings.extend(inspect(relative.as_posix(), path.read_bytes(), allowed, check_allowlist=True))
    for name in sorted(allowed):
        if not (ROOT / name).is_file():
            findings.append((name, 'missing allowlisted file'))
    commits = 0
    # Source archives can be checked without Git; repositories must also pass index/history.
    if (ROOT / '.git').exists():
        for entry in git('ls-files', '--stage', '-z').split(b'\0'):
            if not entry:
                continue
            metadata, name = entry.split(b'\t', 1)
            mode, oid, stage = metadata.split()
            decoded = name.decode()
            if mode == b'120000' or stage != b'0':
                findings.append((decoded, 'index symlink or conflict'))
            findings.extend(inspect(decoded, git('cat-file', 'blob', oid.decode()), allowed, check_allowlist=True))
        try:
            revisions = git('rev-list', 'HEAD').decode().splitlines()
        except subprocess.CalledProcessError:
            revisions = []
        commits = len(revisions)
        seen = set()
        for revision in revisions:
            for entry in git('ls-tree', '-r', '-z', revision).split(b'\0'):
                if not entry:
                    continue
                metadata, name = entry.split(b'\t', 1)
                mode, kind, oid = metadata.split()
                if kind != b'blob' or mode == b'120000':
                    findings.append((name.decode(), 'history non-source entry'))
                elif (oid, name) not in seen:
                    seen.add((oid, name))
                    # History files: check for secrets/patterns AND allowlist membership
                    findings.extend(inspect(name.decode(), git('cat-file', 'blob', oid.decode()), allowed, check_allowlist=True))
    findings = sorted(set(findings))
    for name, label in findings:
        print(name + ': ' + label)
    print(f'Privacy scan: {"FAIL" if findings else "PASS"} ({len(findings)} findings; {files} files; {commits} commits; heuristic, not a privacy guarantee)')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())