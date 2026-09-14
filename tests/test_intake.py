# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bot
import document_intake as intake


class Intake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='intake fixture ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('data/intake', 'data/generations', 'library/guides'):
            (self.root / name).mkdir(parents=True)
        (self.root / 'reference.html').write_text('Original empty reference page')
        self.doc = self.root / 'data/intake/beacon.md'
        self.doc.write_text('SYNTHETIC amber beacon batteries belong in the blue cabinet. ' * 3)

    def publish(self):
        result = intake.reindex(self.root)
        self.assertTrue(result['published'], result)
        return result

    def search(self, text):
        return bot.retrieve(intake.active_library(self.root), text)['sources']

    def test_airgapped_add_change_reindex_and_provenance(self):
        with patch('socket.socket', side_effect=AssertionError('No network')):
            first = self.publish()
            self.assertIn('blue cabinet', self.search('beacon batteries')[0]['text'])
            self.doc.write_text('SYNTHETIC amber beacon batteries now belong in the orange cabinet. ' * 3)
            (self.root / 'data/intake/new.txt').write_text('SYNTHETIC cobalt lantern belongs in the green cabinet. ' * 3)
            second = self.publish()
        self.assertNotEqual(first['generation'], second['generation'])
        self.assertEqual(second['counts']['changed'], 1)
        self.assertEqual(second['counts']['added'], 1)
        self.assertIn('orange cabinet', self.search('beacon batteries')[0]['text'])
        page = (self.root / 'reference.html').read_text()
        self.assertIn('orange cabinet', page)
        self.assertNotIn('blue cabinet', page)
        manifest = json.loads((intake.active_library(self.root).parent / 'provenance.json').read_text())
        self.assertIn('indexed_at', manifest)
        self.assertEqual(manifest['documents'][0]['sha256'], hashlib.sha256(self.doc.read_bytes()).hexdigest())
        self.assertTrue((self.root / 'data/generations' / first['generation'] / 'library/local-qa/guides.sqlite').is_file())

    def test_pdf_extraction_page_citations(self):
        from reportlab.pdfgen.canvas import Canvas
        pdf = self.root / 'data/intake/lantern.pdf'
        canvas = Canvas(str(pdf));canvas.drawString(40, 700, 'SYNTHETIC cobalt lantern in the purple cabinet. Software fixture only.');canvas.save()
        self.publish()
        found = self.search('cobalt lantern')[0]
        self.assertIn('PDF page 1', found['source'])
        self.assertIn('purple cabinet', found['text'])

    def test_failure_at_build_export_and_commit_preserves_prior_search(self):
        self.publish()
        old = (self.root / 'reference.html').read_bytes()
        self.doc.write_text('SYNTHETIC beacon moved to orange cabinet. ' * 3)
        for target in ('document_intake.build_generation', 'document_intake.reference_browser.export', 'document_intake.os.replace'):
            with patch(target, side_effect=OSError('synthetic failure')):
                result = intake.reindex(self.root)
            self.assertFalse(result['published'])
            self.assertGreater(result['counts']['failed'], 0)
            self.assertEqual((self.root / 'reference.html').read_bytes(), old)
            self.assertIn('blue cabinet', self.search('beacon batteries')[0]['text'])

    def test_missing_source_or_dependency_preserves_prior(self):
        self.publish(); old = (self.root / 'reference.html').read_bytes()
        self.doc.rename(self.root / 'parked.md')
        result = intake.reindex(self.root)
        self.assertFalse(result['published'])
        self.assertEqual((self.root / 'reference.html').read_bytes(), old)
        (self.root / 'parked.md').rename(self.doc)
        (self.root / 'data/intake/new.pdf').write_bytes(b'%PDF-synthetic nonextractable fixture')
        with patch('document_intake.shutil.which', return_value=None):
            self.assertFalse(intake.reindex(self.root)['published'])
        self.assertEqual((self.root / 'reference.html').read_bytes(), old)

    def test_bad_inputs_and_count_size_bounds(self):
        for name, body in [('bad.sh', b'echo no'), ('.env', b'secret'), ('config.md', b'config'), ('binary.txt', b'\x7fELF'), ('script.md', b'#!/bin/sh'), ('fake.pdf', b'not PDF')]:
            (self.root / 'data/intake' / name).write_bytes(body)
        (self.root / 'data/intake/link.md').symlink_to(self.doc)
        os.mkfifo(self.root / 'data/intake/pipe.txt')
        os.link(self.doc, self.root / 'data/intake/hard.md')
        items, _ = intake.inventory(self.root)
        self.assertTrue(any(item['status'] == 'failed' for item in items))
        self.assertFalse(intake.reindex(self.root)['published'])
        with patch('document_intake.COUNT_LIMIT', 1):
            self.assertTrue(any(item['status'] == 'failed' for item in intake.inventory(self.root)[0]))
        with patch('document_intake.TOTAL_LIMIT', 1):
            self.assertFalse(intake.reindex(self.root)['published'])

    def test_changed_mid_build_is_not_published(self):
        self.publish(); old = (self.root / 'reference.html').read_bytes()
        real_build = intake.build_generation
        def changed(stage, documents):
            result = real_build(stage, documents)
            self.doc.write_text('SYNTHETIC concurrently changed document.')
            return result
        with patch('document_intake.build_generation', side_effect=changed):
            self.assertFalse(intake.reindex(self.root)['published'])
        self.assertEqual((self.root / 'reference.html').read_bytes(), old)


if __name__ == '__main__':
    unittest.main()
