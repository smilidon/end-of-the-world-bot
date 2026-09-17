# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic retrieval regressions, independent of a model or live network."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

import library_access as library
import retrieval_support as support


class Retrieval(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'guides').mkdir()
        self.no_connect = patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline retrieval connected'))
        self.no_dns = patch.object(socket, 'getaddrinfo', side_effect=AssertionError('Offline retrieval resolved DNS'))
        self.no_connect.start(); self.no_dns.start()
        self.addCleanup(self.no_connect.stop); self.addCleanup(self.no_dns.stop)

    def index(self, documents, metadata=True):
        folder = self.root / 'local-qa'
        folder.mkdir(exist_ok=True)
        with contextlib.closing(sqlite3.connect(folder / 'guides.sqlite')) as db, db:
            db.execute('CREATE VIRTUAL TABLE chunks USING fts5(title,file UNINDEXED,location UNINDEXED,date UNINDEXED,text)')
            if metadata:
                db.execute('CREATE TABLE documents(file TEXT PRIMARY KEY,sha256 TEXT,source_bytes INTEGER,source_mtime_ns INTEGER,extracted_bytes INTEGER,indexed_at TEXT)')
            for name, text in documents.items():
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
                body = path.read_bytes()
                db.execute('INSERT INTO chunks VALUES(?,?,?,?,?)', (path.stem, name, 'text page 1 offset 0', 'unverified', text))
                if metadata:
                    db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)', (name, hashlib.sha256(body).hexdigest(), len(body), path.stat().st_mtime_ns, len(body), '2026-09-16'))

    def query(self, query):
        sources, status, message = library.retrieve(query, self.root)
        return {'sources': sources, 'status': status, 'message': message}

    def test_plural_alias_matches_unchanged_index(self):
        self.index({'guides/example.txt': 'SYNTHETIC batteries belong in a blue cabinet.'})
        for query in ('battery', 'batteries'):
            found = self.query(query)
            self.assertIn('batteries', found['sources'][0]['text'])
            self.assertEqual(found['sources'][0]['freshness'], 'hash_verified_at_query')

    def test_alias_reverse_direction(self):
        self.index({'guides/example.txt': 'SYNTHETIC battery belongs in a blue cabinet.'})
        self.assertTrue(self.query('batteries')['sources'])

    def test_pv_and_microhydro_expansion(self):
        self.index({'guides/example.txt': 'SYNTHETIC pv and micro-hydro reference example.'})
        self.assertTrue(self.query('photovoltaic')['sources'])
        self.assertTrue(self.query('microhydro')['sources'])

    def test_sql_query_keys_and_operator_validated(self):
        for keys, join in [(['bad" OR x'], ' AND '), (['battery'], ' NOT ')]:
            with self.assertRaises(ValueError):
                support.fts_query(keys, join)

    def test_changed_file_skipped_other_result_survives(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon was in the red cabinet.',
                    'guides/b.txt': 'SYNTHETIC beacon belongs in the blue cabinet.'})
        (self.root / 'guides/a.txt').write_text('SYNTHETIC beacon now elsewhere.')
        found = self.query('beacon')
        self.assertEqual([s['file'] for s in found['sources']], ['guides/b.txt'])
        self.assertIn('skipped', found['message'])
        self.assertEqual(len(found['status']['stale_sources']), 1)

    def test_missing_file_skipped_other_result_survives(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon red.', 'guides/b.txt': 'SYNTHETIC beacon blue.'})
        (self.root / 'guides/a.txt').unlink()
        found = self.query('beacon')
        self.assertEqual(found['sources'][0]['file'], 'guides/b.txt')
        self.assertTrue(found['status']['stale_sources'])

    def test_hash_detects_same_size_restored_mtime_edit(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon red.'})
        path = self.root / 'guides/a.txt'
        before = path.stat()
        path.write_text('SYNTHETIC beacon tan.')
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        found = self.query('beacon')
        self.assertFalse(found['sources'])
        self.assertTrue(found['status']['stale_sources'])

    def test_metadata_missing_row_uses_current_file(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon red.'})
        with contextlib.closing(sqlite3.connect(self.root / 'local-qa/guides.sqlite')) as db, db:
            db.execute('DELETE FROM documents')
        (self.root / 'guides/a.txt').write_text('SYNTHETIC beacon blue.')
        found = self.query('beacon')
        self.assertIn('blue', found['sources'][0]['text'])
        self.assertNotIn('red', found['sources'][0]['text'])

    def test_legacy_index_never_returns_stale_chunk(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon red.'}, metadata=False)
        (self.root / 'guides/a.txt').write_text('SYNTHETIC beacon blue.')
        found = self.query('beacon')
        self.assertEqual(found['status']['index_status'], 'legacy_unverified')
        self.assertIn('blue', found['sources'][0]['text'])
        self.assertEqual(found['sources'][0]['freshness'], 'current_read')

    def test_missing_index_reports_status_and_reads_current_document(self):
        (self.root / 'guides/a.txt').write_text('SYNTHETIC batteries blue.')
        found = self.query('battery')
        self.assertEqual(found['status']['index_status'], 'missing')
        self.assertTrue(found['sources'])
        self.assertFalse((self.root / 'local-qa').exists())

    def test_corrupt_index_preserved_and_current_scan_works(self):
        folder = self.root / 'local-qa'; folder.mkdir()
        path = folder / 'guides.sqlite'; path.write_bytes(b'SYNTHETIC invalid database')
        (self.root / 'guides/a.txt').write_text('SYNTHETIC beacon blue.')
        before = path.read_bytes()
        found = self.query('beacon')
        self.assertEqual(found['status']['index_status'], 'unreadable')
        self.assertTrue(found['sources'])
        self.assertEqual(path.read_bytes(), before)

    def test_no_match_distinct_from_index_error(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon blue.'})
        found = self.query('quuxmissing')
        self.assertEqual(found['status']['index_status'], 'ready')
        self.assertFalse(found['sources'])
        self.assertIn('does not prove', found['message'])

    def test_empty_terms_dont_run_raw_scan(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon blue.'})
        with patch.object(support, 'current_pages', side_effect=AssertionError('Unnecessary scan')):
            self.assertFalse(self.query('the and of')['sources'])

    def test_freshness_byte_budget_is_visible(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon blue.'})
        with patch.object(support, 'HASH_BUDGET', 1):
            found = self.query('beacon')
        self.assertFalse(found['sources'])
        self.assertTrue(found['status']['verification_limited'])

    def test_missing_archive_tools_dont_erase_document_matches(self):
        self.index({'guides/a.txt': 'SYNTHETIC beacon blue.'})
        (self.root / 'collections').mkdir()
        (self.root / 'collections/example.zim').write_bytes(b'SYNTHETIC archive fixture')
        found = self.query('beacon')
        self.assertTrue(found['sources'])
        self.assertTrue(found['status']['archive_failures'])

    def test_uppercase_html_read_is_clean_text(self):
        (self.root / 'guides/a.HTML').write_text('<p>SYNTHETIC beacon blue.</p><script>discard()</script>')
        found = self.query('Read: guides/a.HTML')
        self.assertIn('beacon blue', found['sources'][0]['text'])
        self.assertNotIn('script', found['sources'][0]['text'])

    def test_page_zero_does_not_read_tail(self):
        (self.root / 'guides/a.txt').write_text('SYNTHETIC beacon blue.' * 100)
        self.assertFalse(self.query('Read: guides/a.txt page 0')['sources'])

    def test_unindexed_and_uppercase_pdf_keep_page_number(self):
        from reportlab.pdfgen.canvas import Canvas
        path = self.root / 'guides/example.PDF'
        canvas = Canvas(str(path))
        canvas.drawString(40, 700, 'SYNTHETIC first page red cabinet.')
        canvas.showPage()
        canvas.drawString(40, 700, 'SYNTHETIC second page beacon blue cabinet.')
        canvas.save()
        found = self.query('beacon')
        self.assertIn('PDF page 2', found['sources'][0]['source'])
        read = self.query('Read: guides/example.PDF page 2')
        self.assertIn('second page', read['sources'][0]['text'])
        self.assertIn('PDF page 2', read['sources'][0]['source'])

    def test_generation_provenance_supplies_source_hash(self):
        generation = self.root / ('a' * 32)
        self.root = generation / 'library'
        (self.root / 'guides').mkdir(parents=True)
        self.index({'guides/a.txt': 'SYNTHETIC beacon blue.'}, metadata=False)
        body = (self.root / 'guides/a.txt').read_bytes()
        (generation / 'provenance.json').write_text(json.dumps({'documents': [
            {'snapshot': 'guides/a.txt', 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}]}))
        found = self.query('beacon')
        self.assertEqual(found['sources'][0]['freshness'], 'hash_verified_at_query')
        (self.root / 'guides/a.txt').write_text('SYNTHETIC changed revision')
        self.assertFalse(self.query('beacon')['sources'])

    def test_route_words_in_document_questions_are_not_geography(self):
        for q in ['Where is the beacon stored?', 'hard drive maintenance', 'What is a route table?',
                  'Search: driving directions', 'Read: guides/route.txt']:
            with self.subTest(q=q):
                self.assertFalse(support.route_intent(q))
        for q in ['Directions from Alpha to Beta', 'Route: Alpha to Beta', 'navigate to Exampleville',
                  'How do I get to Exampleville?', 'Find Exampleville on the map']:
            with self.subTest(q=q):
                self.assertTrue(support.route_intent(q))


if __name__ == '__main__':
    unittest.main()
