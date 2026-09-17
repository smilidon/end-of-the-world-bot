# SPDX-License-Identifier: GPL-3.0-only
"""Stage 2 failure recovery and bounded resource regressions (synthetic data)."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import index_builder as index
from reference_helpers import ProcessResult, run_result

TEXT = 'SYNTHETIC reference: the amber beacon is stored in the dry blue cabinet. Software fixture only.'
SCHEMA = 'CREATE VIRTUAL TABLE chunks USING fts5(title,file UNINDEXED,location UNINDEXED,date UNINDEXED,text)'


class Extraction(unittest.TestCase):
    def test_success_and_exact_cap(self):
        result = run_result([sys.executable, '-c', 'print("x"*99)'], 2, 100)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.text), 100)

    def test_nonzero_partial_output(self):
        result = run_result([sys.executable, '-c', 'print("partial"); raise SystemExit(7)'], 2, 100)
        self.assertEqual(result.returncode, 7)
        self.assertIn('partial', result.text)
        with self.assertRaises(ValueError):
            result.require_complete()

    def test_oversize_output(self):
        result = run_result([sys.executable, '-c', 'print("x"*10000)'], 2, 100)
        self.assertTrue(result.truncated)
        self.assertEqual(len(result.text), 100)

    def test_wait_after_stdout_close_is_bounded(self):
        start = time.monotonic()
        result = run_result([sys.executable, '-c', 'import os,time; os.close(1); time.sleep(20)'], .15, 100)
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - start, 3)


class AtomicIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'guides').mkdir()
        (self.root / 'local-qa').mkdir()
        self.source = self.root / 'guides/beacon.txt'
        self.source.write_text(TEXT)
        self.target = self.root / 'local-qa/guides.sqlite'

    def failure(self):
        with self.assertRaises(index.IndexBuildError) as caught:
            index.build(self.root)
        self.assertFalse(caught.exception.report['published'])
        self.assertGreater(caught.exception.report['failed_files'], 0)
        self.assertFalse(list(self.target.parent.glob('.index-build-*')))
        return caught.exception.report

    def test_success_metadata_and_populated_preservation(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Unbounded read')):
            result = index.build(self.root)
        self.assertTrue(result['published'])
        self.assertEqual(result['indexed_files'], 1)
        with contextlib.closing(sqlite3.connect(self.target)) as db:
            row = db.execute('SELECT file,sha256,source_bytes,indexed_at FROM documents').fetchone()
            self.assertEqual(row[0], 'guides/beacon.txt')
            self.assertEqual(row[1], hashlib.sha256(TEXT.encode()).hexdigest())
            self.assertEqual(row[2], len(TEXT))
            self.assertTrue(row[3])
        before = self.target.read_bytes()
        self.failure()
        self.assertEqual(self.target.read_bytes(), before)

    def test_zero_stub_preserved_on_failure_and_retry(self):
        self.target.touch()
        with patch.object(index, 'extract', side_effect=ValueError('Synthetic extraction failure')):
            self.failure()
        self.assertEqual(self.target.read_bytes(), b'')
        self.assertTrue(index.build(self.root)['empty_index_replaced'])

    def test_empty_fts_stub_preserved_on_failure(self):
        with contextlib.closing(sqlite3.connect(self.target)) as db:
            db.execute(SCHEMA)
            db.commit()
        before = self.target.read_bytes()
        with patch.object(index, 'extract', side_effect=ValueError('Synthetic extraction failure')):
            self.failure()
        self.assertEqual(self.target.read_bytes(), before)
        self.assertTrue(index.build(self.root)['published'])

    def test_unrelated_database_preserved(self):
        with contextlib.closing(sqlite3.connect(self.target)) as db:
            db.execute('CREATE TABLE owner_notes(value TEXT)')
            db.execute("INSERT INTO owner_notes VALUES('SYNTHETIC owner data')")
            db.commit()
        before = self.target.read_bytes()
        self.failure()
        self.assertEqual(self.target.read_bytes(), before)

    def test_empty_fts_with_other_table_preserved(self):
        with contextlib.closing(sqlite3.connect(self.target)) as db:
            db.execute(SCHEMA)
            db.execute('CREATE TABLE owner_notes(value TEXT)')
            db.commit()
        before = self.target.read_bytes()
        self.failure()
        self.assertEqual(self.target.read_bytes(), before)

    def test_oversized_input_refused_before_publication(self):
        with self.source.open('wb') as stream:
            stream.truncate(index.TEXT_LIMIT + 1)
        self.failure()
        self.assertFalse(self.target.exists())

    def test_missing_extractor_no_final_index(self):
        self.source.unlink()
        (self.root / 'guides/beacon.pdf').write_bytes(b'%PDF-1.4 SYNTHETIC')
        with patch.object(index, 'run_result', side_effect=FileNotFoundError('pdftotext')):
            self.failure()
        self.assertFalse(self.target.exists())

    def test_partial_empty_timeout_and_truncated_pdf_rejected(self):
        self.source.unlink()
        (self.root / 'guides/beacon.pdf').write_bytes(b'%PDF-1.4 SYNTHETIC')
        for result in (ProcessResult(TEXT, 1, False, False), ProcessResult('', 0, False, False),
                       ProcessResult(TEXT, -9, True, False), ProcessResult(TEXT, -9, False, True)):
            with self.subTest(result=result), patch.object(index, 'run_result', return_value=result):
                self.failure()
                self.assertFalse(self.target.exists())

    def test_source_change_aborts_commit(self):
        original = index.extract
        def change(snapshot, deadline):
            raw = original(snapshot, deadline)
            self.source.write_text(TEXT + ' Changed during indexing.')
            return raw
        with patch.object(index, 'extract', side_effect=change):
            self.failure()
        self.assertFalse(self.target.exists())

    def test_racing_new_destination_never_overwritten(self):
        import download_manuals
        original = download_manuals.publish
        def race(fd, part, name):
            self.target.write_bytes(b'SYNTHETIC competing file')
            return original(fd, part, name)
        with patch.object(download_manuals, 'publish', side_effect=race):
            self.failure()
        self.assertEqual(self.target.read_bytes(), b'SYNTHETIC competing file')

    def test_replace_failure_preserves_stub(self):
        self.target.touch()
        with patch.object(index.os, 'replace', side_effect=OSError('Synthetic disk failure')):
            self.failure()
        self.assertEqual(self.target.read_bytes(), b'')

    def test_entry_and_document_limits(self):
        with patch.object(index, 'ENTRY_LIMIT', 1):
            self.failure()
        (self.root / 'guides/second.txt').write_text(TEXT)
        with patch.object(index, 'FILE_COUNT_LIMIT', 1):
            self.failure()

    def test_aggregate_text_limit(self):
        with patch.object(index, 'TOTAL_TEXT_LIMIT', 10):
            self.failure()
        self.assertFalse(self.target.exists())

    def test_post_commit_flush_warning_is_not_failure(self):
        original = index.os.fsync
        calls = []
        def flush(fd):
            calls.append(fd)
            if len(calls) > 1:
                raise OSError('Synthetic directory flush failure')
            return original(fd)
        with patch.object(index.os, 'fsync', side_effect=flush):
            result = index.build(self.root)
        self.assertTrue(result['published'])
        self.assertIn('durability_warning', result)


class IntakeRecovery(unittest.TestCase):
    def setUp(self):
        import document_intake
        self.intake = document_intake
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name)
        for path in ('library/guides', 'data/intake', 'data/generations'):
            (self.app / path).mkdir(parents=True, exist_ok=True)
        self.source = self.app / 'data/intake/beacon.txt'
        self.source.write_text(TEXT)

    def test_text_extraction_does_not_read_whole_file(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('Unbounded read')):
            self.assertEqual(self.intake.extract(self.source, time.monotonic() + 2), TEXT)
        with patch.object(self.intake, 'TEXT_LIMIT', 10):
            with self.assertRaises(ValueError):
                self.intake.extract(self.source, time.monotonic() + 2)

    def test_low_disk_preserves_active_publication(self):
        first = self.intake.reindex(self.app)
        self.assertTrue(first['published'], first)
        before = (self.app / 'reference.html').read_bytes()
        count = len(list((self.app / 'data/generations').iterdir()))
        with patch.object(self.intake.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 0})()):
            result = self.intake.reindex(self.app)
        self.assertFalse(result['published'])
        self.assertEqual((self.app / 'reference.html').read_bytes(), before)
        self.assertEqual(len(list((self.app / 'data/generations').iterdir())), count)

    def test_failed_publication_cleans_temporary_html(self):
        self.assertTrue(self.intake.reindex(self.app)['published'])
        before = (self.app / 'reference.html').read_bytes()
        with patch.object(self.intake.os, 'replace', side_effect=OSError('Synthetic commit failure')):
            result = self.intake.reindex(self.app)
        self.assertFalse(result['published'])
        self.assertEqual((self.app / 'reference.html').read_bytes(), before)
        self.assertFalse(list((self.app / 'data').glob('publish-*.html')))

    def test_download_provenance_is_hash_bound(self):
        (self.app / 'data/downloads').mkdir()
        record = {'filename': 'beacon.txt', 'stored_sha256': hashlib.sha256(TEXT.encode()).hexdigest(),
                  'source_url': 'https://example.com/beacon.txt', 'final_url': 'https://example.com/beacon.txt',
                  'retrieved_at': '2026-09-16T00:00:00+00:00', 'source_sha256': hashlib.sha256(TEXT.encode()).hexdigest()}
        (self.app / 'data/downloads/beacon.txt.json').write_text(json.dumps(record))
        items, _ = self.intake.inventory(self.app)
        self.assertEqual(items[0]['download']['source_url'], record['source_url'])
        self.source.write_text(TEXT + ' changed')
        items, _ = self.intake.inventory(self.app)
        self.assertNotIn('download', items[0])


if __name__ == '__main__':
    unittest.main()
