#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Optional connectivity, DuckDuckGo search/cache and document intake.

No network work occurs on import or during ordinary offline bot commands.
Network workers have a parent-enforced deadline, including DNS and retries.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# Also supports the isolated (-I) worker launched by the parent.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from reference_helpers import clean, run_result

CAP = 16 * 1024 * 1024
CACHE_CAP = 65536
ENDPOINT = 'https://duckduckgo.com/'


def now():
    return datetime.now(timezone.utc).isoformat()


def url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        raise ValueError('Use a bounded HTTP(S) document URL')
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use an HTTP(S) URL without embedded credentials')
    _ = parsed.port
    return urllib.parse.urlunsplit(parsed._replace(fragment=''))


def worker(request):
    """Only this function performs network requests; inputs come from the CLI."""
    operation = request['operation']
    if operation == 'check':
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(ENDPOINT, timeout=5) as response:
                return {'status': 'reachable', 'endpoint': ENDPOINT, 'http_status': response.status,
                        'caveat': 'This endpoint responded; search/download availability may differ.'}
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            return {'status': 'reachable_restricted', 'endpoint': ENDPOINT, 'http_status': code,
                    'caveat': 'The endpoint responded but refused the request; not proof of no Internet.'}
    if operation == 'search':
        try:
            from ddgs import DDGS
        except ImportError:
            return {'status': 'unavailable', 'reason': 'Install requirements-online.txt to enable DuckDuckGo search'}
        rows = DDGS(timeout=8).text(request['query'], backend='duckduckgo', max_results=5)
        results = []
        for row in rows[:5]:
            try:
                target = url(row['href'])
            except (KeyError, ValueError, TypeError):
                continue
            results.append({'title': str(row.get('title', ''))[:300], 'url': target,
                            'snippet': str(row.get('body', ''))[:1500]})
        return {'status': 'online' if results else 'empty', 'provider': 'DuckDuckGo via ddgs',
                'query': request['query'], 'retrieved_at': now(), 'results': results,
                'caveat': 'Search snippets are not downloaded documents or verified answers.'}
    if operation == 'download':
        # Reuse publisher robots, pacing, Retry-After, and error cleanup.
        from download_manuals import Publisher
        publisher = Publisher(timeout=10, retries=1)
        target = url(request['url'])
        for _ in range(6):
            publisher.allowed(target)
            try:
                response = publisher.request(target)
            except urllib.error.HTTPError as exc:
                code, location = exc.code, exc.headers.get('Location')
                exc.close()
                if code not in {301, 302, 303, 307, 308} or not location:
                    raise
                next_url = url(urllib.parse.urljoin(target, location))
                if target.startswith('https:') and not next_url.startswith('https:'):
                    raise ValueError('Refused HTTPS-to-HTTP downgrade')
                target = next_url
                continue
            with response:
                if response.status != 200 or response.headers.get('Content-Encoding', 'identity') != 'identity':
                    raise ValueError('Unsupported document response')
                declared = response.headers.get('Content-Length')
                if declared is not None and not 0 < int(declared) <= CAP:
                    raise ValueError('Download exceeds the 16 MiB limit or is empty')
                body = response.read(CAP + 1)
                if not body or len(body) > CAP or (declared is not None and len(body) != int(declared)):
                    raise ValueError('Incomplete, empty or oversized download')
                return {'status': 'downloaded', 'source_url': request['url'], 'final_url': target,
                        'content_type': response.headers.get_content_type(),
                        'charset': response.headers.get_content_charset() or 'utf-8',
                        'retrieved_at': now(), 'body': base64.b64encode(body).decode('ascii')}
        raise ValueError('Too many document redirects')
    raise ValueError('Unknown online operation')


def isolated(request):
    seconds = {'check': 8, 'search': 30, 'download': 120}[request['operation']]
    cap = 24 * 1024 * 1024 if request['operation'] == 'download' else CACHE_CAP
    result = run_result([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                         '_worker', json.dumps(request)], seconds, cap)
    if not result.ok:
        return {'status': 'unavailable', 'reason': 'Network operation failed, timed out or exceeded its output limit'}
    try:
        data = json.loads(result.text)
        if not isinstance(data, dict) or not isinstance(data.get('status'), str):
            raise ValueError('Invalid worker result')
        return data
    except (ValueError, TypeError):
        return {'status': 'unavailable', 'reason': 'Invalid network response'}


def store_json(folder, name, value, replace=False):
    from download_manuals import directory, publish
    fd = directory(folder, create=True)
    temporary = '.online-' + os.urandom(12).hex() + '.part'
    try:
        child = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(child, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        else:
            publish(fd, temporary, name)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass
        os.close(fd)


def search(app, query, offline=False):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 400:
        raise ValueError('Search requires 1-400 characters')
    query = query.strip()
    name = hashlib.sha256(query.encode()).hexdigest() + '.json'
    folder = Path(app) / 'data/web-cache'
    cached = None
    try:
        from index_builder import read_bounded
        cached = json.loads(read_bounded(folder / name, CACHE_CAP)[0])
        if cached.get('query') != query or cached.get('status') != 'online' or not isinstance(cached.get('results'), list):
            cached = None
    except (OSError, ValueError, TypeError, AttributeError):
        cached = None
    result = {'status': 'unavailable', 'reason': 'Offline-only search; no cached result'} if offline else isolated({'operation': 'search', 'query': query})
    if result['status'] == 'online':
        try:
            store_json(folder, name, result, replace=True)
        except (OSError, ValueError):
            result['cache_warning'] = 'Results returned, but the cache could not be saved'
        result['cached'] = False
        return result
    if cached is not None:
        return {**cached, 'status': 'cached', 'cached': True,
                'reason': result.get('reason', 'No new search results'),
                'caveat': 'Saved search results, not current information; retrieval date is retained.'}
    return {**result, 'cached': False, 'results': result.get('results', [])}


def download(app, source_url, name, reindex=False):
    from download_manuals import directory, publish
    import library_access
    app = Path(app).absolute()
    source_url = url(source_url)
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}', name)
            or '..' in name or library_access.SECRET.search(name) or Path(name).suffix.lower() not in {'.txt', '.md', '.pdf'}):
        raise ValueError('Choose a plain .txt, .md or .pdf intake filename')
    # No writes or network request when the owner already has a file here.
    destination = app / 'data/intake' / name
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination exists; existing document preserved')
    result = isolated({'operation': 'download', 'url': source_url})
    if result['status'] != 'downloaded':
        return {**result, 'saved': False, 'published': False}
    raw = base64.b64decode(result.pop('body'), validate=True)
    if not raw or len(raw) > CAP:
        raise ValueError('Invalid downloaded document size')
    kind = result['content_type']
    suffix = Path(name).suffix.lower()
    if suffix == '.pdf':
        if kind not in {'application/pdf', 'application/octet-stream'} or not raw.startswith(b'%PDF-'):
            raise ValueError('Downloaded response is not a PDF')
        body = raw
    else:
        if kind not in {'text/plain', 'text/markdown', 'text/html', 'application/xhtml+xml'}:
            raise ValueError('Downloaded response is not text')
        text = raw.decode(result.get('charset', 'utf-8'), 'strict')
        if kind in {'text/html', 'application/xhtml+xml'}:
            text = clean(text)
        body = text.encode('utf-8')
        if not text.strip() or b'\0' in body or len(body) > 2 * 1024 * 1024 or body.startswith((b'#!', b'MZ', b'\x7fELF')):
            raise ValueError('Document is empty, binary, executable or exceeds the 2 MiB text intake limit')
    import shutil
    probe = app
    if not probe.is_dir():
        raise ValueError('Use an existing application directory')
    if shutil.disk_usage(probe).free < len(body) + 16 * 1024 * 1024:
        raise ValueError('Insufficient free space for the document')
    fd = directory(app / 'data/intake', create=True)
    part = '.download-' + os.urandom(12).hex() + '.part'
    try:
        child = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(child, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        publish(fd, part, name)
    finally:
        try:
            os.unlink(part, dir_fd=fd)
        except FileNotFoundError:
            pass
        os.close(fd)
    receipt = {**result, 'filename': name, 'source_sha256': hashlib.sha256(raw).hexdigest(),
               'stored_sha256': hashlib.sha256(body).hexdigest(), 'stored_bytes': len(body),
               'saved': True, 'published': False, 'rights': 'Publisher terms apply; no redistribution permission inferred'}
    try:
        store_json(app / 'data/downloads', name + '.json', receipt, replace=True)
        receipt['provenance_report'] = 'data/downloads/' + name + '.json'
    except (OSError, ValueError):
        receipt['provenance_warning'] = 'Document saved, but receipt could not be saved; retain this output'
    if reindex:
        for path in (app / 'data/generations', app / 'library/guides'):
            os.close(directory(path, create=True))
        import document_intake
        try:
            indexed = document_intake.reindex(app)
            receipt['reindex'] = indexed
            receipt['published'] = indexed['published']
        except (OSError, ValueError) as exc:
            receipt['reindex_error'] = type(exc).__name__ + ': document saved; index publication failed'
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=ROOT, help='Existing source/installation directory')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('check', help='Check an existing Internet connection; never join or configure a network')
    p = sub.add_parser('search', help='Try DuckDuckGo; use cached results when unavailable')
    p.add_argument('query')
    p.add_argument('--offline', action='store_true', help='Cache only; no network attempt')
    p = sub.add_parser('download', help='Download one document into intake; never execute it')
    p.add_argument('url')
    p.add_argument('--name', required=True)
    p.add_argument('--reindex', action='store_true', help='Publish a new offline generation after download')
    args = parser.parse_args(argv)
    try:
        if args.command == 'check':
            result = isolated({'operation': 'check'})
        elif args.command == 'search':
            result = search(args.app, args.query, args.offline)
        else:
            result = download(args.app, args.url, args.name, args.reindex)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result['status'] == 'unavailable' or (args.command == 'download' and args.reindex and not result.get('published')) else 0
    except (OSError, ValueError, KeyError, TypeError, LookupError) as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '_worker':
        try:
            output = worker(json.loads(sys.argv[2]))
        except Exception as exc:
            output = {'status': 'unavailable', 'reason': type(exc).__name__ + ': network/provider unavailable; local library unchanged'}
        print(json.dumps(output))
    else:
        raise SystemExit(main())
