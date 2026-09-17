# SPDX-License-Identifier: GPL-3.0-only
"""Transactional legacy-index construction. Publication is the final operation."""
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import time

import library_access
from reference_helpers import clean, run_result

TEXT_LIMIT = 5_000_000
FILE_LIMIT = 16 * 1024 * 1024
TOTAL_LIMIT = 128 * 1024 * 1024
TOTAL_TEXT_LIMIT = 16 * 1024 * 1024
FILE_COUNT_LIMIT = 256
ENTRY_LIMIT = 4096
BUILD_SECONDS = 60
FORMATS = {'.pdf', '.html', '.htm', '.txt', '.md', '.mdx'}


class IndexBuildError(ValueError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def stamp(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_bounded(path, cap):
    """No full-file read before the limit; reject changes during the read."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > cap:
            raise ValueError('Document is not a regular file within the input limit')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    if len(body) > cap or len(body) != before.st_size or stamp(before) != stamp(after):
        raise ValueError('Document changed during read or exceeded the input limit')
    return body, before


def inventory(root, deadline):
    """Reuse document/path rules, but bound directory discovery itself too."""
    files, pending, entries = [], [root], 0
    while pending:
        with os.scandir(pending.pop()) as children:
            for child in children:
                entries += 1
                if entries > ENTRY_LIMIT or time.monotonic() >= deadline:
                    raise ValueError('Library discovery limit exceeded')
                if library_access.SECRET.search(child.name) or child.is_symlink():
                    continue
                if child.is_dir(follow_symlinks=False):
                    pending.append(Path(child.path))
                elif Path(child.name).suffix.lower() in FORMATS:
                    path = library_access.safe(root, child.path)
                    files.append(str(path.relative_to(root)))
                    if len(files) > FILE_COUNT_LIMIT:
                        raise ValueError('Index document limit exceeded (256)')
    return sorted(files)


def target_state(target):
    """Only an absent file, a zero-byte stub, or the exact empty FTS schema.

    In particular, a SQLite database without a chunks table is NOT an empty
    installer stub. It may contain unrelated user data and must be preserved.
    """
    if target.is_symlink():
        raise ValueError('Index is a symlink; preserve it')
    if not target.exists():
        return None
    info = target.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Index is not a regular file')
    if info.st_size == 0:
        return stamp(info)
    try:
        with contextlib.closing(sqlite3.connect(target.as_uri() + '?mode=ro', uri=True)) as db:
            row = db.execute("SELECT sql FROM sqlite_master WHERE name='chunks' AND type='table'").fetchone()
            if row is None or 'using fts5' not in ' '.join(row[0].lower().split()):
                raise ValueError('Unrecognized existing database; preserved')
            if db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]:
                raise ValueError('Index exists with data; use the atomic reindex workflow')
            names = {r[0] for r in db.execute('SELECT name FROM sqlite_master')}
            expected = {'chunks', 'chunks_data', 'chunks_idx', 'chunks_content', 'chunks_docsize', 'chunks_config'}
            columns = [r[1] for r in db.execute('PRAGMA table_info(chunks)')]
            if names != expected or columns != ['title', 'file', 'location', 'date', 'text']:
                raise ValueError('Unrecognized existing database; preserved')
    except sqlite3.Error as exc:
        raise ValueError('Index exists and is unreadable; preserved') from exc
    return stamp(info)


def extract(snapshot, deadline):
    if snapshot.suffix.lower() == '.pdf':
        remaining = min(12, deadline - time.monotonic())
        raw = run_result(['pdftotext', '-layout', snapshot, '-'], remaining, TEXT_LIMIT).require_complete()
    else:
        raw = read_bounded(snapshot, TEXT_LIMIT)[0].decode('utf-8', 'replace')
        if snapshot.suffix.lower() in {'.html', '.htm'}:
            raw = clean(raw)
    if not raw.strip():
        raise ValueError('Document contains no extractable text')
    return raw


def build(root):
    root = Path(root).absolute()
    report = {'attempted_files': 0, 'indexed_files': 0, 'skipped_files': 0,
              'failed_files': 0, 'chunks': 0, 'published': False, 'documents': []}
    stage = None
    try:
        if not root.is_dir():
            raise ValueError('Create a dedicated library directory first')
        directory = root / 'local-qa'
        if directory.is_symlink():
            raise ValueError('Index directory must not be a symlink')
        directory.mkdir(exist_ok=True)
        target = directory / 'guides.sqlite'
        # Serialize cooperating index builders, without touching the live index.
        lock_fd = os.open(directory / '.index.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            original = target_state(target)
            deadline = time.monotonic() + BUILD_SECONDS
            names = inventory(root, deadline)
            if not names:
                raise ValueError('No guides present; any empty index is preserved')
            # Reserve room for bounded FTS expansion and one input snapshot.
            if shutil.disk_usage(directory).free < TOTAL_TEXT_LIMIT * 4 + FILE_LIMIT:
                raise ValueError('Insufficient free space to stage the index')
            stage = Path(tempfile.mkdtemp(prefix='.index-build-', dir=directory))
            pending = stage / 'guides.sqlite'
            source_hashes, total, total_text = {}, 0, 0
            indexed_at = datetime.now(timezone.utc).isoformat()
            with contextlib.closing(sqlite3.connect(pending)) as db, db:
                db.execute('CREATE VIRTUAL TABLE chunks USING fts5(title,file UNINDEXED,location UNINDEXED,date UNINDEXED,text)')
                db.execute('CREATE TABLE documents(file TEXT PRIMARY KEY, sha256 TEXT, source_bytes INTEGER, source_mtime_ns INTEGER, extracted_bytes INTEGER, indexed_at TEXT)')
                for name in names:
                    item = {'file': name, 'status': 'attempted'}
                    report['documents'].append(item)
                    report['attempted_files'] += 1
                    try:
                        if time.monotonic() >= deadline:
                            raise ValueError('Index build deadline exceeded')
                        path = library_access.safe(root, name)
                        cap = FILE_LIMIT if path.suffix.lower() == '.pdf' else TEXT_LIMIT
                        body, info = read_bounded(path, cap)
                        total += len(body)
                        if total > TOTAL_LIMIT:
                            raise ValueError('Total input limit exceeded')
                        digest = hashlib.sha256(body).hexdigest()
                        source_hashes[name] = digest
                        snapshot = stage / ('source' + path.suffix.lower())
                        snapshot.write_bytes(body)
                        raw = extract(snapshot, deadline)
                        snapshot.unlink()
                        extracted_bytes = len(raw.encode('utf-8'))
                        total_text += extracted_bytes
                        if total_text > TOTAL_TEXT_LIMIT:
                            raise ValueError('Total extracted text limit exceeded')
                        pages = raw.split('\f') if path.suffix.lower() == '.pdf' else [raw]
                        count = 0
                        for page, text in enumerate(pages, 1):
                            text = ' '.join(text.split())
                            for offset in range(0, len(text), 3000):
                                chunk = text[offset:offset + 3600]
                                if not chunk:
                                    continue
                                location = (f'PDF page {page}, text offset {offset}' if path.suffix.lower() == '.pdf'
                                            else f'text page {page} offset {offset}')
                                db.execute('INSERT INTO chunks VALUES(?,?,?,?,?)', (path.stem, name, location, 'publication date unverified', chunk))
                                count += 1
                        if not count:
                            raise ValueError('Document contains no searchable chunks')
                        db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',
                                   (name, digest, len(body), info.st_mtime_ns, extracted_bytes, indexed_at))
                        item.update(status='indexed', sha256=digest, chunks=count)
                        report['indexed_files'] += 1
                        report['chunks'] += count
                    except (OSError, ValueError, sqlite3.Error):
                        item['status'] = 'failed'
                        report['failed_files'] += 1
                        raise
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('New index integrity check failed')
            # Do not publish evidence for a different source revision.
            if inventory(root, deadline) != names:
                raise ValueError('Library changed during indexing')
            for name, digest in source_hashes.items():
                if time.monotonic() >= deadline:
                    raise ValueError('Index verification deadline exceeded')
                cap = FILE_LIMIT if Path(name).suffix.lower() == '.pdf' else TEXT_LIMIT
                if hashlib.sha256(read_bounded(library_access.safe(root, name), cap)[0]).hexdigest() != digest:
                    raise ValueError('Source changed during indexing')
            if target_state(target) != original:
                raise ValueError('Index destination changed during indexing; preserved')
            with pending.open('rb') as stream:
                os.fsync(stream.fileno())
            if original is None:
                # Existing Linux no-replace publisher also works across sibling directories.
                from download_manuals import publish
                fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    publish(fd, str(pending.relative_to(directory)), target.name)
                finally:
                    os.close(fd)
            else:
                os.replace(pending, target)
            report['published'] = True
            report['empty_index_replaced'] = original is not None
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                try:
                    os.fsync(fd)
                except OSError:
                    report['durability_warning'] = 'Published; directory flush unavailable on this filesystem'
            finally:
                os.close(fd)
        return report
    except (OSError, ValueError, sqlite3.Error) as exc:
        report['error'] = str(exc)
        report['failed_files'] = max(1, report['failed_files'])
        raise IndexBuildError(str(exc), report) from exc
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
