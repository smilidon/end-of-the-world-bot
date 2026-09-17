#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Plan by default; explicitly fetch pinned publisher PDFs for noncommercial use."""
import argparse
import ctypes
import datetime
import email.utils
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

UA = 'OfflineManualLibrary/0.1 (+https://github.com/smilidon/end-of-the-world-bot)'
CAP = 16 * 1024 * 1024


def load_catalog(path):
    with open(path, 'rb') as f:
        raw = f.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Catalog too large')
    data = json.loads(raw)
    if data.get('schema') != 1 or not isinstance(data.get('items'), list):
        raise ValueError('Invalid catalog schema')
    ids, names = set(), set()
    for x in data['items']:
        name = x['filename']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,179}', name) or '..' in name:
            raise ValueError('Unsafe filename')
        if x['id'] in ids or name in names:
            raise ValueError('Duplicate catalog entry')
        ids.add(x['id']); names.add(name)
        u = urllib.parse.urlsplit(x['source_url'])
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.port not in (None, 443):
            raise ValueError('Only credential-free original HTTPS URLs allowed')
        if x['download_status'] not in ('eligible', 'manual_action'):
            raise ValueError('Invalid eligibility')
        if x['download_status'] == 'eligible':
            if x['format'] != 'pdf' or not name.endswith('.pdf') or not re.fullmatch('[a-f0-9]{64}', x.get('sha256') or ''):
                raise ValueError('Eligible entries require a PDF and verified hash')
            if type(x['size_bytes']) is not int or not 0 < x['size_bytes'] <= CAP:
                raise ValueError('Eligible size exceeds limit')
    return data


def directory(path, create=False):
    """Walk using no-follow directory descriptors, including every ancestor."""
    path = os.path.abspath(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in Path(path).parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def valid_existing(fd, item):
    try:
        file_fd = os.open(item['filename'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return False
    import stat
    with os.fdopen(file_fd, 'rb') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != item['size_bytes']:
            raise ValueError('Existing destination differs; preserved')
        if hashlib.file_digest(f, 'sha256').hexdigest() != item['sha256']:
            raise ValueError('Existing destination differs; preserved')
    return True


def publish(fd, part, name):
    """Linux atomic no-replace rename works on ordinary and FAT-style filesystems."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(fd, os.fsencode(part), fd, os.fsencode(name), 1):
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Publisher:
    def __init__(self, timeout=20, retries=2, delay=1.0, opener=None, sleep=time.sleep):
        self.timeout, self.retries, self.delay = timeout, retries, delay
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.sleep = sleep
        self.robots = {}
        self.last = {}

    def request(self, url):
        origin = urllib.parse.urlsplit(url).netloc
        for attempt in range(self.retries + 1):
            self.sleep(max(0, self.delay - (time.monotonic() - self.last.get(origin, 0))))
            self.last[origin] = time.monotonic()
            try:
                return self.opener.open(urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'identity'}), timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                code, retry = exc.code, exc.headers.get('Retry-After')
                exc.close()
                if code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise
                seconds = 2 ** attempt
                if retry:
                    try:
                        seconds = max(seconds, float(retry))
                    except ValueError:
                        try:
                            seconds = max(seconds, (email.utils.parsedate_to_datetime(retry) - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
                        except (TypeError, ValueError):
                            raise ValueError('Invalid Retry-After; stopping') from None
                if seconds > 60:
                    raise ValueError('Retry-After exceeds bounded wait; retry later')
                self.sleep(seconds)
            except (urllib.error.URLError, TimeoutError):
                if attempt == self.retries:
                    raise
                self.sleep(2 ** attempt)

    def allowed(self, url):
        u = urllib.parse.urlsplit(url)
        origin = u.scheme + '://' + u.netloc
        if origin not in self.robots:
            try:
                with self.request(origin + '/robots.txt') as response:
                    if response.status != 200:
                        raise ValueError('Robots response not successful')
                    raw = response.read(256 * 1024 + 1)
                    if len(raw) > 256 * 1024 or b'<html' in raw[:1024].lower():
                        raise ValueError('Unusable robots response')
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(raw.decode('utf-8', 'replace').splitlines())
                self.robots[origin] = rp
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                if code not in (404, 410):
                    raise ValueError('Robots unavailable; no download') from None
                self.robots[origin] = None
        rp = self.robots[origin]
        if rp is not None:
            if not rp.can_fetch(UA, url):
                raise ValueError('Publisher robots disallows automated access')
            delay = rp.crawl_delay(UA) or rp.crawl_delay('*') or 0
            rate = rp.request_rate(UA) or rp.request_rate('*')
            if rate:
                delay = max(delay, rate.seconds / rate.requests)
            if delay > 60:
                raise ValueError('Publisher pacing exceeds bounded run; manual action')
            self.delay = max(self.delay, delay)

    def open_pdf(self, url):
        origin = urllib.parse.urlsplit(url).netloc
        for _ in range(6):
            self.allowed(url)
            try:
                response = self.request(url)
            except urllib.error.HTTPError as exc:
                code, location = exc.code, exc.headers.get('Location')
                exc.close()
                if code not in (301, 302, 303, 307, 308) or not location:
                    raise
                target = urllib.parse.urljoin(url, location)
                u = urllib.parse.urlsplit(target)
                if u.scheme != 'https' or u.netloc != origin or u.username or u.password or u.query or u.fragment:
                    raise ValueError('Unapproved redirect; manual publisher review required')
                url = target
                continue
            if response.status != 200 or response.headers.get_content_type() != 'application/pdf' or response.headers.get('Content-Encoding', 'identity') != 'identity':
                response.close()
                raise ValueError('Rejected non-PDF or non-200 response')
            return response
        raise ValueError('Too many redirects')


def fetch_one(fd, item, publisher):
    if valid_existing(fd, item):
        return 'already_verified'
    part = '.manual-' + os.urandom(12).hex() + '.part'
    created = False
    try:
        with publisher.open_pdf(item['source_url']) as response:
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != item['size_bytes']:
                raise ValueError('Publisher size changed; manifest update needed')
            file_fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            created = True
            with os.fdopen(file_fd, 'wb') as f:
                total, digest, start = 0, hashlib.sha256(), time.monotonic()
                while True:
                    chunk = response.read(min(65536, item['size_bytes'] - total + 1))
                    if not chunk:
                        break
                    if total == 0 and not chunk.startswith(b'%PDF-'):
                        raise ValueError('Rejected HTML/error or invalid PDF signature')
                    total += len(chunk)
                    if total > item['size_bytes'] or total > CAP or time.monotonic() - start > 120:
                        raise ValueError('Transfer byte/time cap exceeded')
                    digest.update(chunk); f.write(chunk)
                if total != item['size_bytes'] or digest.hexdigest() != item['sha256']:
                    raise ValueError('Size or checksum mismatch; original changed or incomplete')
                f.flush(); os.fsync(f.fileno())
        publish(fd, part, item['filename'])
        return 'downloaded_verified'
    finally:
        if created:
            try:
                os.unlink(part, dir_fd=fd)
            except FileNotFoundError:
                pass


def plan(data, ids, dest):
    known = {x['id'] for x in data['items']}
    if set(ids) - known:
        raise ValueError('Unknown selection ID')
    chosen = [x for x in data['items'] if not ids or x['id'] in ids]
    eligible = [x for x in chosen if x['download_status'] == 'eligible']
    probe = Path(os.path.abspath(dest))
    while not probe.exists():
        probe = probe.parent
    fd = directory(probe)
    os.close(fd)
    free = shutil.disk_usage(probe).free
    summary = {'selected': len(chosen), 'eligible': len(eligible), 'manual_action': len(chosen)-len(eligible), 'known_bytes': sum(x['size_bytes'] or 0 for x in chosen), 'unknown_sizes': sum(x['size_bytes'] is None for x in chosen), 'eligible_download_bytes':sum(x['size_bytes'] for x in eligible), 'disk_free_bytes':free}
    return chosen, eligible, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('manuals.json'))
    parser.add_argument('--dest', type=Path, default=Path('manual-library/guides'))
    parser.add_argument('--fetch', action='store_true', help='Actually download eligible originals for personal noncommercial use')
    parser.add_argument('--all', action='store_true', help='Explicitly select all catalog entries (only eligible PDFs fetched)')
    parser.add_argument('--id', action='append', default=[], help='Select catalog ID; repeat for several')
    args = parser.parse_args(argv)
    try:
        if not sys.platform.startswith('linux') or sys.version_info < (3, 11):
            raise ValueError('Linux with Python 3.11+ required; use a Linux/WSL terminal')
        if args.all and args.id:
            raise ValueError('Choose --all or --id, not both')
        if args.fetch and not (args.all or args.id):
            raise ValueError('Fetching requires --all or at least one --id')
        data = load_catalog(args.manifest)
        chosen, eligible, summary = plan(data, args.id, args.dest)
        print(json.dumps({'mode':'fetch' if args.fetch else 'dry_run', **summary}, indent=2))
        for x in chosen:
            print(f"{x['id']} [{x['download_status']}] {x['title']} — {x['size_bytes'] if x['size_bytes'] is not None else 'unknown'} bytes")
        if not args.fetch:
            return 0
        if summary['eligible_download_bytes'] + 16*1024*1024 > summary['disk_free_bytes']:
            raise ValueError('Insufficient disk space including safety margin')
        if not eligible:
            print('No eligible items to fetch')
            return 0
        # -I bootstrap invocation does not include the script directory on sys.path.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from network_permission import ask
        if not ask('fetch the selected catalog PDFs from their displayed publishers, including robots checks and retries.'):
            print('Cancelled; no manual downloads or destination writes.')
            return 0
        fd = directory(args.dest, create=True)
        results = []
        try:
            publisher = Publisher()
            for x in chosen:
                result = {'id':x['id'], 'filename':x['filename']}
                if x['download_status'] != 'eligible':
                    result.update(status='manual_action', reason=x['reason'])
                else:
                    try:
                        result['status'] = fetch_one(fd, x, publisher)
                    except (OSError, ValueError, AttributeError, http.client.HTTPException) as exc:
                        # Do not save redirects, headers, credentials or local user paths.
                        reason = str(exc) if isinstance(exc, ValueError) else ('HTTP ' + str(exc.code) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__ + ': access, incomplete transfer or destination failure')
                        result.update(status='failed', reason=reason)
                results.append(result)
                print(json.dumps(result), flush=True)
            report = 'download-results-' + os.urandom(8).hex() + '.json'
            report_fd = os.open(report, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(report_fd, 'w') as f:
                json.dump({'summary':summary, 'results':results, 'failures':[r for r in results if r['status']=='failed']}, f, indent=2)
            print('Failure/resume report: ' + report)
        finally:
            os.close(fd)
        return 1 if any(r['status']=='failed' for r in results) else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Preflight failed: ' + type(exc).__name__ + '. Check catalog, selection, destination and dependencies.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
