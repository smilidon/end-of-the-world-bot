# SPDX-License-Identifier: GPL-3.0-only
"""Source-package allowlist and heuristic worktree/index/history privacy guard."""
from pathlib import Path
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
IGNORED = {'.git', '.venv', '__pycache__'}


def inspect(name, body, allowed):
    findings = []
    if name not in allowed:
        findings.append((name, 'not in source allowlist'))
    try:
        text = body.decode('utf-8')
    except UnicodeError:
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
            findings.extend(inspect(relative.as_posix(), path.read_bytes(), allowed))
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
            findings.extend(inspect(decoded, git('cat-file', 'blob', oid.decode()), allowed))
        revisions = git('rev-list', '--all').decode().splitlines()
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
                    findings.extend(inspect(name.decode(), git('cat-file', 'blob', oid.decode()), allowed))
    findings = sorted(set(findings))
    for name, label in findings:
        print(name + ': ' + label)
    print(f'Privacy scan: {"FAIL" if findings else "PASS"} ({len(findings)} findings; {files} files; {commits} commits; heuristic, not a privacy guarantee)')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())