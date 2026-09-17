# SPDX-License-Identifier: GPL-3.0-only
"""Bounded explicit intake and atomic publication of immutable search generations."""
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import shutil
import sqlite3
import stat
import subprocess
import time

from document_workspace import directory
import library_access
import reference_browser
from index_builder import read_bounded
from reference_helpers import run_result

FILE_LIMIT = 16 * 1024 * 1024
TOTAL_LIMIT = 128 * 1024 * 1024
COUNT_LIMIT = 256
TEXT_LIMIT = 2 * 1024 * 1024
TOTAL_TEXT_LIMIT = 16 * 1024 * 1024
TYPES = {'.txt', '.md', '.pdf'}
MARKER = re.compile(rb'<!-- intake-generation: ([0-9a-f]{32}) -->\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def read_file(fd, name, cap=FILE_LIMIT):
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(child, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > cap:
            raise ValueError('Not a bounded single-link regular document')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        if len(body) > cap or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(body) != before.st_size:
            raise ValueError('Document changed during read or exceeded size limit')
    return body, before


def active_library(app):
    """The same atomically replaced HTML is both browser snapshot and CLI commit record."""
    app = Path(app)
    with directory(app) as fd:
        try:
            file_fd = os.open('reference.html', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            return app / 'library'
        with os.fdopen(file_fd, 'rb') as stream:
            info = os.fstat(file_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Reference publication must be a single-link regular file')
            marker = MARKER.match(stream.read(100))
    if not marker:
        return app / 'library'
    root = app / 'data/generations' / marker[1].decode() / 'library'
    with directory(root):
        pass
    return root


def previous_manifest(app):
    root = active_library(app)
    if root == app / 'library':
        return {}
    with directory(root.parent) as fd:
        body, _ = read_file(fd, 'provenance.json', 1024 * 1024)
    return {item['origin'] + '/' + item['name']: item for item in json.loads(body)['documents']}


def inventory(app):
    """Only two explicitly documented, flat owner-selected directories; no recursion."""
    app = Path(app)
    old = previous_manifest(app)
    items, payloads, seen, total, count = [], {}, set(), 0, 0
    for origin, path in (('intake', app / 'data/intake'), ('legacy-guides', app / 'library/guides')):
        with directory(path) as fd:
            with os.scandir(fd) as entries:
                names = []
                for entry in entries:
                    count += 1
                    if count > COUNT_LIMIT:
                        items.append({'origin': origin, 'status': 'failed', 'reason': 'Entry count limit exceeded (256); no publication'})
                        return items, payloads
                    names.append(entry.name)
            for name in sorted(names):
                key = origin + '/' + name
                item = {'origin': origin, 'name': name}
                items.append(item)
                if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}', name)
                        or '..' in name or library_access.SECRET.search(name) or Path(name).suffix.lower() not in TYPES):
                    item.update(status='skipped', reason='Unsupported/protected name or type; only plain .txt/.md/.pdf files')
                    continue
                try:
                    body, info = read_file(fd, name)
                    if body.startswith((b'#!', b'\x7fELF', b'MZ')) or (Path(name).suffix.lower() != '.pdf' and b'\x00' in body):
                        raise ValueError('Executable/binary content is not an intake document')
                    if Path(name).suffix.lower() == '.pdf' and not body.startswith(b'%PDF-'):
                        raise ValueError('PDF signature missing')
                    if Path(name).suffix.lower() != '.pdf':
                        body.decode('utf-8')
                    total += len(body)
                    if total > TOTAL_LIMIT:
                        raise ValueError('Total intake limit exceeded (128 MiB)')
                    digest = hashlib.sha256(body).hexdigest()
                    seen.add(key)
                    previous = old.get(key)
                    item.update(status='added' if not previous else 'skipped' if previous['sha256'] == digest else 'changed',
                                reason='unchanged' if previous and previous['sha256'] == digest else 'validated',
                                sha256=digest, bytes=len(body), source_mtime_ns=info.st_mtime_ns,
                                snapshot='guides/' + origin + '/' + name)
                    # Carry download provenance only when the stored bytes match.
                    if origin == 'intake':
                        try:
                            receipt = json.loads(read_bounded(app / 'data/downloads' / (name + '.json'), 16384)[0])
                            if receipt.get('filename') == name and receipt.get('stored_sha256') == digest:
                                item['download'] = {field: receipt[field] for field in
                                                    ('source_url', 'final_url', 'retrieved_at', 'source_sha256', 'stored_sha256')}
                        except (OSError, ValueError, TypeError, AttributeError, KeyError):
                            pass
                    payloads[key] = body
                except (OSError, ValueError, UnicodeError):
                    item.update(status='failed', reason='Unsafe, changed, unavailable, oversized or unextractable file; prior search preserved')
    for key, previous in old.items():
        if key not in seen:
            items.append({'origin': previous['origin'], 'name': previous['name'], 'status': 'failed',
                          'reason': 'Previously indexed source missing or now unsafe; restore it before reindexing'})
    return items, payloads


def extract(path, budget_end):
    if time.monotonic() >= budget_end:
        raise ValueError('Reindex extraction deadline exceeded')
    if path.suffix.lower() != '.pdf':
        text = read_bounded(path, TEXT_LIMIT)[0].decode('utf-8')
    else:
        executable = shutil.which('pdftotext')
        if not executable:
            raise ValueError('PDF needs preinstalled Poppler pdftotext; prior search preserved')
        text = run_result([executable, '-layout', str(path), '-'],
                          min(12, budget_end - time.monotonic()), TEXT_LIMIT).require_complete()
    if not text.strip():
        raise ValueError('Document has no extractable text; prior search preserved')
    return text


def build_generation(stage, documents):
    library = stage / 'library'
    (library / 'local-qa').mkdir()
    total_text, chunks = 0, 0
    deadline = time.monotonic() + 60
    with contextlib.closing(sqlite3.connect(library / 'local-qa/guides.sqlite')) as db, db:
        db.execute('CREATE VIRTUAL TABLE chunks USING fts5(title,file UNINDEXED,location UNINDEXED,date UNINDEXED,text)')
        for item in documents:
            if time.monotonic() > deadline:
                raise ValueError('Reindex extraction deadline exceeded (60 seconds)')
            path = library / item['snapshot']
            raw = extract(path, deadline)
            total_text += len(raw.encode('utf-8'))
            if total_text > TOTAL_TEXT_LIMIT:
                raise ValueError('Total extracted text exceeds 16 MiB')
            pages = raw.split('\f') if path.suffix.lower() == '.pdf' else [raw]
            count = 0
            for page, text in enumerate(pages, 1):
                text = ' '.join(text.split())
                for offset in range(0, len(text), 3000):
                    chunk = text[offset:offset + 3600]
                    if not chunk:
                        continue
                    location = f'PDF page {page}, text offset {offset}' if path.suffix.lower() == '.pdf' else f'text page {page} offset {offset}'
                    db.execute('INSERT INTO chunks VALUES(?,?,?,?,?)', (path.stem, item['snapshot'], location, 'publication date unverified', chunk))
                    count += 1
            if not count:
                raise ValueError('Document has no extractable text')
            chunks += count
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('New index integrity check failed')
    return chunks


def summarize(items, **fields):
    return {'items': items, 'counts': {state: sum(item['status'] == state for item in items)
                                     for state in ('added', 'changed', 'skipped', 'failed')}, **fields}


def reindex(app):
    app = Path(app)
    # Serialize intake writers; keep old generations and sources untouched.
    with directory(app / 'data') as data_fd:
        items, payloads = inventory(app)
        result = summarize(items, timestamp=now(), published=False)
        generation = secrets.token_hex(16)
        result['generation'] = generation
        temp_name = None
        try:
            if result['counts']['failed']:
                raise ValueError('Intake failed validation; prior index/export retained')
            if not payloads:
                raise ValueError('No eligible documents; prior index/export retained')
            # Old generations consume space, so check BEFORE copying the new one.
            needed = sum(len(body) for body in payloads.values()) + TOTAL_TEXT_LIMIT * 4
            if shutil.disk_usage(app / 'data').free < needed:
                raise ValueError('Insufficient space for a new generation; prior search preserved')
            with directory(app / 'data/generations') as generations_fd:
                os.mkdir(generation, 0o700, dir_fd=generations_fd)
            stage = app / 'data/generations' / generation
            documents = [dict(item) for item in items if item.get('sha256')]
            for item in documents:
                path = stage / 'library' / item['snapshot']
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as stream:
                    stream.write(payloads[item['origin'] + '/' + item['name']])
            result['chunks'] = build_generation(stage, documents)
            provenance = {'indexed_at': result['timestamp'], 'generation': generation, 'documents': documents,
                          'scope': ['data/intake', 'library/guides'], 'source_content': 'untrusted'}
            (stage / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
            export = reference_browser.export(stage / 'library', stage / 'reference.html')
            if export['truncated']:
                raise ValueError('Browser export would be incomplete; prior index/export retained')
            latest, latest_bodies = inventory(app)
            if any(item['status'] == 'failed' for item in latest) or payloads != latest_bodies:
                raise ValueError('Intake changed during rebuild; retry after files finish copying')
            for path in stage.rglob('*'):
                if path.is_file():
                    with path.open('rb') as stream:
                        os.fsync(stream.fileno())
            # Flush child directory entries before publishing the generation pointer.
            directories = sorted([stage, *[p for p in stage.rglob('*') if p.is_dir()]],
                                 key=lambda p: len(p.parts), reverse=True)
            for path in [*directories, stage.parent]:
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            publication = '<!-- intake-generation: ' + generation + ' -->\n' + (stage / 'reference.html').read_text()
            temp_name = 'publish-' + generation + '.html'
            temp_fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=data_fd)
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as stream:
                stream.write(publication)
                stream.flush()
                os.fsync(stream.fileno())
            active_library(app)
            with directory(app) as app_fd:
                os.replace(temp_name, 'reference.html', src_dir_fd=data_fd, dst_dir_fd=app_fd)
                result['published'] = True
                # Once committed, a later flush failure is a durability warning,
                # not a false claim that the old generation is still active.
                try:
                    os.fsync(app_fd)
                    os.fsync(data_fd)
                except OSError:
                    result['durability_warning'] = 'Published; directory flush failed. Back up and verify after restart.'
            result['browser'] = 'reference.html (reload after successful reindex)'
        except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
            result['error'] = str(exc)
            if not result['counts']['failed']:
                result['items'].append({'status': 'failed', 'reason': 'Rebuild/publication failed; prior search remains active'})
                result['counts']['failed'] += 1
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name, dir_fd=data_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    result['cleanup_warning'] = 'An unpublished temporary HTML file remains in data/'
        name = 'intake-results-' + generation + '.json'
        try:
            report_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=data_fd)
            with os.fdopen(report_fd, 'w') as stream:
                json.dump(result, stream, indent=2)
            result['report'] = 'data/' + name
        except OSError:
            result['report_warning'] = 'Could not save report; retain this console output'
        return result
