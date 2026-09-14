# SPDX-License-Identifier: GPL-3.0-only
"""Explicit Linux network observations, not connectivity tests or repairs.

Owner-invoked CLI only, not a model tool. Paths/binary are fixed platform policy,
never supplied by documents/logs. Plans inspect metadata, not file contents.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import time

from offline_diagnostics import redact
from document_workspace import Workspace

SYS = Path('/sys/class/net')
DEVICES = Path('/sys/devices')
ROUTE = Path('/proc/net/route')
RESOLVER = Path('/etc/resolv.conf')
RESOLVER_TARGETS = {'/etc/resolv.conf', '/run/systemd/resolve/stub-resolv.conf',
                    '/run/systemd/resolve/resolv.conf', '/run/NetworkManager/resolv.conf'}
IW = '/usr/sbin/iw'
CAP = 32768
MAX_ADAPTERS = 64
META_CAP = 128
WIFI_SECONDS = 10
ADAPTER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,14}\Z')
STATES = {'up', 'down', 'unknown', 'dormant', 'lowerlayerdown', 'notpresent', 'testing'}


def adapters():
    """Bounded metadata-only discovery of kernel-owned adapter links."""
    found = []
    with os.scandir(SYS) as entries:
        for entry in entries:
            if len(found) >= MAX_ADAPTERS:
                raise ValueError('Too many adapters; bounded discovery refused')
            if not ADAPTER.fullmatch(entry.name):
                raise ValueError('Unrecognized adapter name; discovery refused')
            target = Path(entry.path).resolve(strict=True)
            if not target.is_relative_to(DEVICES):
                raise ValueError('Unapproved adapter source; discovery refused')
            found.append({'name': entry.name, 'path': str(target),
                          'wireless': (target / 'wireless').is_dir()})
    return sorted(found, key=lambda item: item['name'])


def plan(wifi=None):
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise ValueError('Linux, non-root only; no elevation supported')
    if wifi is not None and (not isinstance(wifi, str) or not ADAPTER.fullmatch(wifi)):
        raise ValueError('Invalid adapter name')
    found = adapters()
    if wifi is not None:
        selected = next((item for item in found if item['name'] == wifi and item['wireless']), None)
        if selected is None:
            raise ValueError('Choose a listed wireless adapter')
        sources = [{'command': [IW, 'dev', wifi, 'scan'], 'max_bytes': CAP}]
        found = [selected]
    else:
        sources = [{'path': item['path'] + '/' + field, 'max_bytes': META_CAP}
                   for item in found for field in ('type', 'operstate')]
        sources.append({'path': str(ROUTE), 'max_bytes': CAP})
        # Resolver symlinks are common; resolve only to an explicit platform allowlist.
        target = RESOLVER.resolve()
        if str(target) in RESOLVER_TARGETS:
            sources.append({'path': str(target), 'max_bytes': CAP})
    return {'kind': 'wifi' if wifi is not None else 'local', 'adapter': wifi,
            'adapters': found, 'sources': sources, 'created': int(time.time()),
            'consent_valid_seconds': 300, 'observation_window': 'current configuration at confirmed read, not history',
            'max_total_bytes': sum(item['max_bytes'] for item in sources),
            'wifi_timeout_seconds': WIFI_SECONDS if wifi is not None else None,
            'privacy': 'Preview lists interface names. Reports omit names, addresses, SSIDs, MACs and raw output. Wi-Fi scan emits radio probes; no joining. Local reads make no network requests.'}


def confirmation(scope):
    return 'SCAN ' + hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()[:16]


def bounded(path, cap):
    """No-follow every path component; reject devices, FIFOs and linked files."""
    path = Path(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
        metadata = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError('Source is not a single-link regular file')
        leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(leaf, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                    (info.st_dev, info.st_ino) != (metadata.st_dev, metadata.st_ino)):
                raise ValueError('Source is not a single-link regular file')
            raw = stream.read(cap + 1)
    finally:
        os.close(fd)
    if len(raw) > cap:
        raise ValueError('Source exceeds byte bound')
    return raw.decode('utf-8', 'replace')


def wifi_scan(adapter):
    # Fixed binary/argv, no shell/PATH lookup, no credentials, bounded streaming.
    # Called only AFTER scan validates consent and current adapter metadata.
    with subprocess.Popen([IW, 'dev', adapter, 'scan'], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                          env={'LC_ALL': 'C'}, start_new_session=True) as child:
        data = bytearray()
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(child.stdout, selectors.EVENT_READ)
                deadline = time.monotonic() + WIFI_SECONDS
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not sel.select(remaining):
                        raise ValueError('Wi-Fi scan timed out; no elevation attempted')
                    chunk = os.read(child.stdout.fileno(), min(4096, CAP + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > CAP:
                        raise ValueError('Wi-Fi scan exceeds byte bound')
            if child.wait(timeout=max(.1, deadline - time.monotonic())):
                raise ValueError('Wi-Fi scan unavailable/permission denied; no elevation attempted')
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    # Discard all identifying output, including prompt-like SSID strings.
    return {'visible_access_points': len(re.findall(rb'^BSS ', data, re.M)),
            'caveat': 'Count only, not an Internet test. Hidden networks, permissions and radio state can limit results.'}


def scan(scope, consent):
    if not isinstance(scope, dict) or type(scope.get('created')) is not int:
        raise ValueError('Plan required')
    if not 0 <= time.time() - scope['created'] < 300 or consent != confirmation(scope):
        raise ValueError('Exact fresh scope confirmation required')
    expected = plan(scope.get('adapter'))
    expected['created'] = scope['created']
    if scope != expected:
        raise ValueError('Scope changed or invalid; preview and confirm again')
    result = {'confidence': 'observations only; insufficient evidence for a root cause',
              'observed_at': int(time.time()), 'evidence': [], 'caveats': [],
              'possible_causes': ['Local adapter or routing configuration', 'Upstream network or DNS service'],
              'safe_checks': ['Check the cable and router indicator lights.', 'Compare the symptom in another already-configured application; do not change settings yet.'],
              'model_called': False, 'writes_performed': False}
    if scope['kind'] == 'wifi':
        try:
            result['evidence'].append(wifi_scan(scope['adapter']))
        except (OSError, ValueError, subprocess.SubprocessError):
            result['caveats'].append('Wi-Fi scan unavailable, denied, timed out or oversized. No elevation/retry attempted; absence of results does not imply no networks.')
        return result
    content = {}
    for source in scope['sources']:
        try:
            content[source['path']] = bounded(source['path'], source['max_bytes'])
        except (OSError, ValueError):
            # No raw errors/paths are persisted in reports.
            result['caveats'].append('An approved source was unavailable or unsafe; observation omitted.')
    for i, item in enumerate(scope['adapters']):
        state = content.get(item['path'] + '/operstate', '').strip()
        kind = content.get(item['path'] + '/type', '').strip()
        result['evidence'].append({'adapter': 'adapter-' + str(i + 1),
                                   'state': state if state in STATES else 'unavailable/unrecognized',
                                   'loopback': kind == '772' if kind.isdecimal() else None})
    try:
        lines = content[str(ROUTE)].splitlines()
        if not lines or lines[0].split()[:4] != ['Iface', 'Destination', 'Gateway', 'Flags']:
            raise ValueError('Unrecognized route header')
        rows = [line.split() for line in lines[1:] if line.strip()]
        if any(len(row) < 4 or not re.fullmatch('[0-9A-Fa-f]{8}', row[1]) or not re.fullmatch('[0-9A-Fa-f]{1,8}', row[3]) for row in rows):
            raise ValueError('Unrecognized route row')
        defaults = [r for r in rows if len(r) >= 4 and r[1] == '00000000']
        result['evidence'].append({'ipv4_default_route_present': any(int(r[3], 16) & 1 != 0 for r in defaults)})
    except (KeyError, ValueError):
        result['caveats'].append('IPv4 default route observation unavailable')
    resolver = next((s['path'] for s in scope['sources'] if s['path'] in RESOLVER_TARGETS), None)
    if resolver in content:
        count = sum(bool(re.match(r'^\s*nameserver\s+\S+', line)) for line in content[resolver].splitlines())
        result['evidence'].append({'configured_resolvers': count})
    else:
        result['caveats'].append('Resolver data unavailable or outside approved scope')
    result['caveats'].append('No DNS query or connectivity probe. IPv6 routes, VPN policy and actual Internet reachability are not established. Configuration can change during reads.')
    return result


def save_report(app, name, result):
    text = '# Network observations\n\n' + redact(json.dumps(result, indent=2))
    return Workspace(app / 'workspace').dispatch({'action': 'create', 'name': name, 'text': text})


def interactive(app):
    scope = plan()
    print(json.dumps(scope, indent=2))
    print('Network details can be private. Type ' + confirmation(scope) + ' to read, or Enter to cancel:')
    consent = input()
    if consent != confirmation(scope):
        print('Cancelled; no source contents read.')
        return
    result = scan(scope, consent)
    print(json.dumps(result, indent=2))
    wireless = [item['name'] for item in scope['adapters'] if item['wireless']]
    if wireless:
        print('Optional Wi-Fi adapters: ' + ', '.join(wireless))
        print('Adapter name (blank skips). Scan sends radio probes; never joins a network:')
        adapter = input().strip()
        if adapter:
            extra = plan(adapter)
            print(json.dumps(extra, indent=2))
            print('Second consent: type ' + confirmation(extra) + ' or Enter to skip:')
            approval = input()
            if approval == confirmation(extra):
                result['wifi'] = scan(extra, approval)
                print(json.dumps(result['wifi'], indent=2))
            else:
                print('Wi-Fi scan skipped.')
    else:
        print('No wireless adapters discovered; Wi-Fi scan not offered.')
    print('Optional new workspace .md report name (blank means no writes). Use document print for printable HTML:')
    name = input().strip()
    if name:
        print(save_report(app, name, result))
