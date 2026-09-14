# SPDX-License-Identifier: GPL-3.0-only
"""Linux-only, explicitly confirmed, bounded read-only log intake. Never commands."""
import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

LOG_ROOT = Path('/var/log')  # Trusted platform constant, never a request parameter.
ALLOWLIST = {
    'storage': ('syslog', 'messages', 'kern.log'),
    'permission': ('syslog', 'messages'),
    'dependency': ('dpkg.log', 'apt/term.log', 'dnf.log'),
    'connection': ('ollama/ollama.log', 'syslog', 'messages'),
    'index': ('syslog', 'messages'),
}
PER_FILE = 16 * 1024
TOTAL = 48 * 1024
WINDOW_SECONDS = 24 * 60 * 60
EXPIRY_SECONDS = 10 * 60
FILTERS = {
    'storage': r'\b(?:ENOSPC|EIO)\b|no space left|disk full|I/O error',
    'permission': r'\b(?:EACCES|EPERM)\b|permission denied',
    'dependency': r'python|pdftotext|sqlite|error|failed',
    'connection': r'ollama|ECONNREFUSED|connection refused',
    'index': r'sqlite|chunks|database|index',
}


def supported():
    if not sys.platform.startswith('linux'):
        raise ValueError('Log discovery supports Linux only; use explicit pasted text on other platforms')
    if os.geteuid() == 0:
        raise ValueError('Diagnostic discovery/scan refuses root; run as an ordinary user, never elevate')


@contextlib.contextmanager
def parent(name):
    # Names come from the fixed platform allowlist, not arbitrary user paths.
    parts = (LOG_ROOT / name).absolute().parts
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[1:-1]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
        yield fd, parts[-1]
    finally:
        os.close(fd)


def timestamp():
    return datetime.now(timezone.utc).timestamp()


def token(scope):
    return 'READ ' + hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]


def discover(category):
    supported()
    if not isinstance(category, str) or category not in ALLOWLIST:
        raise ValueError('Choose storage, permission, dependency, connection or index')
    end = int(timestamp())
    scope = {'platform': 'linux', 'category': category, 'created': end, 'since': end - WINDOW_SECONDS,
             'until': end, 'expires': end + EXPIRY_SECONDS, 'max_total_bytes': TOTAL, 'sources': []}
    unavailable = []
    for name in ALLOWLIST[category]:
        try:
            with parent(name) as (fd, leaf):
                info = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Not a single-link regular log')
            if info.st_mtime < scope['since']:
                unavailable.append({'path': str(LOG_ROOT / name), 'reason': 'Last modified before requested 24-hour window'})
                continue
            length = min(PER_FILE, info.st_size)
            scope['sources'].append({'name': name, 'path': str(LOG_ROOT / name), 'device': info.st_dev,
                                     'inode': info.st_ino, 'size': info.st_size, 'mtime_ns': info.st_mtime_ns,
                                     'start': info.st_size - length, 'bytes': length})
        except (OSError, ValueError):
            unavailable.append({'path': str(LOG_ROOT / name), 'reason': 'Missing, protected, unreadable or unsafe; no elevation attempted'})
    return {'scope': scope, 'confirm': token(scope), 'unavailable': unavailable, 'content_read': False,
            'window_utc': {'since': datetime.fromtimestamp(scope['since'], timezone.utc).isoformat(),
                           'until': datetime.fromtimestamp(scope['until'], timezone.utc).isoformat()},
            'warning': 'Preview only: metadata checked, no log content read. Review exact sources/byte ranges and repeat confirm with this scope to authorize reading. Logs may contain private data.',
            'exclusions': ['home documents', 'browser profiles', 'auth/security logs', 'credentials', 'binary journal files'],
            'caveats': ['File-only allowlist; journal-only services may have no supported readable logs.',
                        'ISO timestamps or yearless syslog timestamps only; unsupported/undated lines are not analyzed.']}


def validate(scope, confirmation):
    supported()
    if not isinstance(scope, dict) or set(scope) != {'platform', 'category', 'created', 'since', 'until', 'expires', 'max_total_bytes', 'sources'}:
        raise ValueError('Exact discovery scope required')
    category = scope.get('category')
    if not isinstance(category, str) or category not in ALLOWLIST or scope['platform'] != 'linux':
        raise ValueError('Unsupported scope category/platform')
    for key in ('created', 'since', 'until', 'expires', 'max_total_bytes'):
        if type(scope[key]) is not int:
            raise ValueError('Invalid time/byte scope')
    if (not 0 <= timestamp() - scope['created'] <= EXPIRY_SECONDS or scope['until'] != scope['created']
            or scope['since'] != scope['until'] - WINDOW_SECONDS or scope['expires'] != scope['created'] + EXPIRY_SECONDS
            or scope['max_total_bytes'] != TOTAL or confirmation != token(scope)):
        raise ValueError('Explicit confirmation missing, changed or expired; preview again')
    if not isinstance(scope['sources'], list) or len(scope['sources']) > 3:
        raise ValueError('Invalid source count')
    names = set()
    for source in scope['sources']:
        if not isinstance(source, dict) or set(source) != {'name', 'path', 'device', 'inode', 'size', 'mtime_ns', 'start', 'bytes'}:
            raise ValueError('Invalid source description')
        name = source['name']
        if not isinstance(name, str) or name not in ALLOWLIST[category] or name in names or source['path'] != str(LOG_ROOT / name):
            raise ValueError('Source is not on the fixed platform allowlist')
        names.add(name)
        if any(type(source[k]) is not int or source[k] < 0 for k in ('device', 'inode', 'size', 'mtime_ns', 'start', 'bytes')):
            raise ValueError('Invalid source bounds')
        if source['bytes'] != min(PER_FILE, source['size']) or source['start'] != source['size'] - source['bytes']:
            raise ValueError('Only the proposed bounded tail may be read')
    if sum(source['bytes'] for source in scope['sources']) > TOTAL:
        raise ValueError('Total read bound exceeded')


def line_time(line, end):
    """Never invent timestamps: disclose local-zone/year inference for syslog."""
    local_zone = datetime.now().astimezone().tzinfo
    match = re.match(r'\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)', line)
    if match:
        try:
            parsed = datetime.fromisoformat(match[1].replace('Z', '+00:00'))
            inferred = parsed.tzinfo is None
            return parsed.replace(tzinfo=local_zone).timestamp() if inferred else parsed.timestamp(), 'host-local timezone assumed' if inferred else 'explicit timezone'
        except ValueError:
            return None, 'invalid timestamp'
    match = re.match(r'\s*([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})', line)
    if match:
        year = datetime.fromtimestamp(end, local_zone).year
        try:
            parsed = datetime.strptime(str(year) + ' ' + match[1], '%Y %b %d %H:%M:%S').replace(tzinfo=local_zone)
            if parsed.timestamp() > end + 86400:
                parsed = parsed.replace(year=year - 1)
            return parsed.timestamp(), 'syslog year and host-local timezone assumed; verify'
        except ValueError:
            pass
    return None, 'unrecognized/missing timestamp'


def scan(scope, confirmation):
    validate(scope, confirmation)  # Before any content open/read.
    from offline_diagnostics import redact
    selected, provenance, reports = [], [], []
    for source in scope['sources']:
        report = {'source': source['path'], 'bytes_read': 0, 'selected_lines': 0, 'skipped_lines': 0}
        reports.append(report)
        try:
            with parent(source['name']) as (fd, leaf):
                file_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(file_fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                        (info.st_dev, info.st_ino) != (source['device'], source['inode']) or info.st_size < source['size']):
                    raise ValueError('Log rotated/truncated or became unsafe; preview again')
                stream.seek(source['start'])
                body = stream.read(source['bytes'])
                if len(body) != source['bytes']:
                    raise ValueError('Log changed during bounded read; preview again')
            report['bytes_read'] = len(body)
            lines = body.decode('utf-8', 'replace').splitlines()
            if source['start'] and lines:
                lines = lines[1:]  # Do not analyze a possibly partial first line.
                report['skipped_lines'] += 1
            for number, line in enumerate(lines, 1):
                instant, basis = line_time(line, scope['until'])
                if instant is None or not scope['since'] <= instant <= scope['until'] or not re.search(FILTERS[scope['category']], line, re.I):
                    report['skipped_lines'] += 1
                    continue
                selected.append(redact(line))
                provenance.append({'source': source['path'], 'tail_line': number, 'timestamp_utc': datetime.fromtimestamp(instant, timezone.utc).isoformat(), 'time_basis': basis})
                report['selected_lines'] += 1
        except (OSError, ValueError):
            report['error'] = 'Unreadable, rotated, truncated or unsafe source; no diagnosis from this file. Preview again.'
    return {'text': '\n'.join(selected), 'provenance': provenance, 'sources': reports,
            'scope': scope, 'raw_logs_saved': False, 'writes_performed': False,
            'caveats': ['Only approved byte ranges and timestamped category-matching lines were analyzed.',
                        'Missing/unsupported logs or skipped lines can hide the cause. No match is not proof of health.',
                        'Logs are untrusted claims; timestamp/host identity and causes are not independently verified.']}
