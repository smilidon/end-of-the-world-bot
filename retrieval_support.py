# SPDX-License-Identifier: GPL-3.0-only
"""Compatibility helpers for lexical queries, source freshness, and route intent.

Existing FTS5 tables and verbatim evidence are retained. No model or network.
"""
import contextlib
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import time

MAX_CANDIDATES = 48
HASH_BUDGET = 32 * 1024 * 1024
INPUT_CAP = 16 * 1024 * 1024


def fts_query(keys, join=' AND '):
    """Expand both spellings of the existing aliases; never stem quoted evidence."""
    import library_access as library
    if join not in {' AND ', ' OR '}:
        raise ValueError('Invalid query operator')
    groups = []
    for key in keys[:16]:
        if not re.fullmatch('[a-z0-9]+', key):
            raise ValueError('Invalid lexical key')
        variants = {key, *(word for word, canonical in library.ALIASES.items() if canonical == key)}
        if key == 'microhydro':
            variants.add('micro hydro')
        groups.append('(' + ' OR '.join('"' + word + '"' for word in sorted(variants)) + ')')
    return join.join(groups)


def route_intent(question):
    """Require geographic phrasing, not incidental drive/route/where-is words."""
    q = question.strip()
    if re.match(r'(?i)^(?:read|search|reference|files|calc)\s*:', q):
        return False
    return bool(re.search(
        r'(?i)^(?:map|route|directions|navigate|coordinates)\s*:|'
        r'\b(?:directions?|route|navigate|drive|driving|walk|walking)\s+(?:from|to|between)\b|'
        r'\bhow (?:do|can) i get (?:from|to)\b|'
        r'\b(?:find|show|locate)\b.+\bon (?:a |the )?map\b', q))


def route_reply(question, pending, nav):
    """Only a recognized pending slot can keep a route conversation active."""
    if not pending or not isinstance(pending, dict):
        return False
    q = question.strip().rstrip('.!')
    if re.search(r'(?i)[?:]|^(?:how|what|where|why|when|explain|describe|search|read)\b', q):
        return False
    if pending.get('awaiting') == 'region':
        import named_routing
        try:
            known = {name for name, _ in named_routing.maps(nav)}
            normalized = named_routing.normalize(q)
            if normalized in {'mi', 'm i'}:
                normalized = 'michigan'
            return normalized in known
        except (OSError, ValueError, KeyError):
            return False
    if pending.get('awaiting') in {'endpoints', 'trip'}:
        return bool(re.fullmatch(r"(?i)(?:from )?[\w .,'’-]{1,100}\s+(?:to|and)\s+[\w .,'’-]{1,100}", q))
    return False


def source_metadata(db, root):
    """Read Stage 2 metadata, or the existing immutable-generation provenance."""
    from index_builder import read_bounded
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents'").fetchone():
        rows = db.execute('SELECT file,sha256,source_bytes FROM documents LIMIT 4097').fetchall()
        if len(rows) > 4096:
            raise ValueError('Source metadata exceeds limit')
        return {name: (digest, size) for name, digest, size in rows}
    if root.name == 'library' and re.fullmatch('[0-9a-f]{32}', root.parent.name):
        import library_access as library
        path = library.safe(root.parent, 'provenance.json')
        data = json.loads(read_bounded(path, 1024 * 1024)[0])
        if not isinstance(data, dict) or not isinstance(data.get('documents'), list) or len(data['documents']) > 256:
            raise ValueError('Invalid generation provenance')
        return {item['snapshot']: (item['sha256'], item['bytes']) for item in data['documents']}
    return {}


def indexed_sources(root, keys, status, deadline):
    """Skip stale/missing candidates independently; do not discard good matches."""
    import library_access as library
    from index_builder import read_bounded
    root = Path(root).absolute()
    status.update(index_status='missing', guide_index_files=0, stale_sources=[], unverified_sources=[])
    indexed, sources, checked, used = set(), [], {}, 0
    target = root / 'local-qa/guides.sqlite'
    if not target.exists() and not target.is_symlink():
        return sources, indexed
    try:
        target = library.safe(root, 'local-qa/guides.sqlite')
        with contextlib.closing(sqlite3.connect(target.as_uri() + '?mode=ro', uri=True, timeout=.25)) as db:
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            names = db.execute('SELECT DISTINCT file FROM chunks LIMIT 4097').fetchall()
            if len(names) > 4096:
                raise ValueError('Index inventory exceeds query limit')
            indexed = {row[0] for row in names}
            status.update(index_status='ready', guide_index_files=len(indexed))
            try:
                metadata = source_metadata(db, root)
            except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                metadata = {}
            if not metadata and indexed:
                status['index_status'] = 'legacy_unverified'
                # Read current documents instead of quoting unverifiable old chunks.
                return [], set()
            if not keys:
                return sources, indexed
            for join in (' AND ', ' OR '):
                rows = db.execute('SELECT file,location,text FROM chunks WHERE chunks MATCH ? ORDER BY rank LIMIT ?',
                                  (fts_query(keys, join), MAX_CANDIDATES)).fetchall()
                status['candidate_limit'] = MAX_CANDIDATES
                for name, location, text in rows:
                    if time.monotonic() >= deadline:
                        status['verification_limited'] = True
                        break
                    if name not in checked:
                        meta = metadata.get(name)
                        if (not isinstance(meta, tuple) or len(meta) != 2 or not isinstance(meta[0], str)
                                or not re.fullmatch('[0-9a-f]{64}', meta[0]) or type(meta[1]) is not int
                                or not 0 <= meta[1] <= INPUT_CAP):
                            checked[name] = False
                            indexed.discard(name)
                            status['unverified_sources'].append(name)
                            continue
                        if used + meta[1] > HASH_BUDGET:
                            checked[name] = False
                            status['verification_limited'] = True
                            continue
                        used += meta[1]
                        try:
                            body, _ = read_bounded(library.safe(root, name), meta[1])
                            matches = hashlib.sha256(body).hexdigest() == meta[0]
                            checked[name] = matches
                            if not matches:
                                status['stale_sources'].append({'file': name, 'reason': 'content changed'})
                        except (OSError, ValueError):
                            checked[name] = False
                            status['stale_sources'].append({'file': name, 'reason': 'missing, changed or unreadable'})
                    if checked[name] and isinstance(text, str) and isinstance(location, str):
                        source = library.record(name, location, library.excerpt(text, keys))
                        source.update(file=name, location=location, sha256=metadata[name][0], freshness='hash_verified_at_query')
                        sources.append(source)
                if sources:
                    break
            status['verified_input_bytes'] = used
    except (OSError, ValueError, sqlite3.Error):
        status['index_status'] = 'unreadable'
        # The bounded current-file scan is independent of an unusable index.
        return sources, set()
    return sources, indexed


def current_pages(root, name, deadline, page=None):
    """Read a stable, bounded revision. PDFs use a temporary snapshot, then cleanup."""
    import library_access as library
    from index_builder import read_bounded
    from reference_helpers import clean, run_result
    path = library.safe(root, name)
    suffix = path.suffix.lower()
    if suffix not in {'.pdf', '.txt', '.md', '.mdx', '.html', '.htm'}:
        raise ValueError('Unsupported readable document')
    cap = INPUT_CAP if suffix == '.pdf' else 2 * 1024 * 1024
    body, _ = read_bounded(path, cap)
    digest = hashlib.sha256(body).hexdigest()
    if time.monotonic() >= deadline:
        raise ValueError('Current-read deadline exceeded')
    if suffix == '.pdf':
        with tempfile.TemporaryDirectory(prefix='eotwb-reference-') as temporary:
            snapshot = Path(temporary) / 'source.pdf'
            snapshot.write_bytes(body)
            command = ['pdftotext']
            if page is not None:
                command += ['-f', str(page), '-l', str(page)]
            command += ['-layout', snapshot, '-']
            text = run_result(command, max(.001, deadline - time.monotonic()), 500000).require_complete()
        pages = [(page or 1) + offset for offset in range(len(text.split('\f')))]
        rows = list(zip(pages, text.split('\f')))
    else:
        text = body.decode('utf-8', 'replace')
        if suffix in {'.html', '.htm'}:
            text = clean(text)
        rows = [(1, text)]
    if hashlib.sha256(read_bounded(library.safe(root, name), cap)[0]).hexdigest() != digest:
        raise ValueError('Source changed while reading')
    return rows, digest, suffix


def direct_read(root, name, page, keys):
    import library_access as library
    if type(page) is not int or page < 1 or page > 100000:
        raise ValueError('Page must be between 1 and 100000')
    rows, digest, suffix = current_pages(root, name, time.monotonic() + 3, page)
    if suffix == '.pdf':
        text = library.excerpt(rows[0][1], keys)
        location = 'PDF page ' + str(page)
    else:
        offset = (page - 1) * 1000
        text = rows[0][1][offset:offset + 1000]
        location = 'text page ' + str(page) + ' offset ' + str(offset)
    if not text.strip():
        return []
    result = library.record(name, location, text)
    result.update(file=name, location=location, sha256=digest, freshness='current_read')
    return [result]


def scan_sources(root, names, indexed, keys, status, deadline):
    import library_access as library
    sources, scanned = [], 0
    status['scan_failures'] = []
    if keys:
        for name in sorted(names, key=lambda f: -library.relevance(f, keys)):
            if time.monotonic() >= deadline or scanned >= 32:
                status['scan_limited'] = True
                break
            if name in indexed or Path(name).suffix.lower() not in {'.pdf', '.html', '.htm', '.txt', '.md', '.mdx'}:
                continue
            scanned += 1
            try:
                rows, digest, suffix = current_pages(root, name, min(deadline, time.monotonic() + .7))
                for page, raw in rows:
                    if not library.relevance(raw, keys):
                        continue
                    # Match the indexer's whitespace normalization and page numbering.
                    normalized = ' '.join(raw.split())
                    for offset in range(0, len(normalized), 3000):
                        text = normalized[offset:offset + 3600]
                        if not library.relevance(text, keys):
                            continue
                        loc = (f'PDF page {page}, text offset {offset}' if suffix == '.pdf' else
                               f'text page 1 offset {offset}')
                        source = library.record(name, loc, library.excerpt(text, keys))
                        source.update(file=name, location=loc, sha256=digest, freshness='current_read')
                        sources.append(source)
                        if len(sources) >= MAX_CANDIDATES:
                            status['scan_limited'] = True
                            status['unindexed_documents_scanned'] = scanned
                            return sources
            except (OSError, ValueError):
                status['scan_failures'].append(name)
    status['unindexed_documents_scanned'] = scanned
    return sources


def notice(status):
    messages = []
    state = status.get('index_status')
    if state == 'missing':
        messages.append('Index missing; run index for a new library or reindex for an installed workspace. Bounded current-file scan used.')
    elif state == 'unreadable':
        messages.append('Index unreadable; preserve it and use the documented rebuild workflow. Bounded current-file scan used.')
    elif state == 'legacy_unverified':
        messages.append('Legacy index has no source hashes; old excerpts were not trusted. Bounded current-file scan used; rebuild recommended.')
    if status.get('stale_sources'):
        messages.append('Changed or missing indexed sources were skipped; rebuild to refresh them.')
    if status.get('unverified_sources'):
        messages.append('Some source metadata is missing; current-file reads were attempted instead of old excerpts.')
    if status.get('verification_limited') or status.get('scan_limited') or status.get('scan_failures'):
        messages.append('Some documents could not be checked within the read limits; results may be incomplete.')
    if status.get('archive_failures'):
        messages.append('Some archive tools or articles were unavailable; other reference results were retained.')
    return ' '.join(messages)
