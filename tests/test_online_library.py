# SPDX-License-Identifier: GPL-3.0-only
"""No live provider traffic: online workflows use explicit synthetic fixtures."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import online_library as online
from reference_helpers import ProcessResult

TEXT = b'SYNTHETIC reference: the amber beacon belongs in the dry blue cabinet. Software fixture only.'


def response(body=TEXT, kind='text/plain'):
    return {'status': 'downloaded', 'source_url': 'https://example.com/beacon',
            'final_url': 'https://example.com/beacon', 'content_type': kind,
            'charset': 'utf-8', 'retrieved_at': '2026-09-16T00:00:00+00:00',
            'body': base64.b64encode(body).decode()}


class OnlineLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name)

    def result(self):
        return {'status': 'online', 'provider': 'DuckDuckGo via ddgs', 'query': 'beacon',
                'retrieved_at': '2026-09-16T00:00:00+00:00',
                'results': [{'title': 'Synthetic fixture', 'url': 'https://example.com/beacon', 'snippet': 'Synthetic excerpt'}]}

    def test_search_saves_cache_and_offline_reuses_date(self):
        with patch.object(online, 'isolated', return_value=self.result()):
            result = online.search(self.app, 'beacon')
        self.assertFalse(result['cached'])
        with patch.object(online, 'isolated', side_effect=AssertionError('No network in offline mode')):
            cached = online.search(self.app, 'beacon', offline=True)
        self.assertTrue(cached['cached'])
        self.assertEqual(cached['retrieved_at'], self.result()['retrieved_at'])
        self.assertEqual(cached['status'], 'cached')

    def test_failed_online_search_falls_back(self):
        with patch.object(online, 'isolated', return_value=self.result()):
            online.search(self.app, 'beacon')
        with patch.object(online, 'isolated', return_value={'status': 'unavailable', 'reason': 'Synthetic outage'}):
            self.assertTrue(online.search(self.app, 'beacon')['cached'])

    def test_missing_cache_offline_no_writes(self):
        self.assertEqual(online.search(self.app, 'beacon', offline=True)['status'], 'unavailable')
        self.assertEqual(list(self.app.iterdir()), [])

    def test_invalid_cache_does_not_crash(self):
        folder = self.app / 'data/web-cache'
        folder.mkdir(parents=True)
        (folder / (hashlib.sha256(b'beacon').hexdigest() + '.json')).write_text('[]')
        self.assertEqual(online.search(self.app, 'beacon', offline=True)['status'], 'unavailable')

    def test_search_backend_is_duckduckgo_only(self):
        calls = []
        class Fake:
            def __init__(self, **kwargs):
                calls.append(kwargs)
            def text(self, query, **kwargs):
                calls.append(kwargs)
                return [{'title': 'Synthetic', 'href': 'https://example.com/beacon', 'body': 'Synthetic'}]
        with patch.dict('sys.modules', {'ddgs': SimpleNamespace(DDGS=Fake)}):
            result = online.worker({'operation': 'search', 'query': 'beacon'})
        self.assertEqual(result['status'], 'online')
        self.assertEqual(calls[1]['backend'], 'duckduckgo')
        self.assertEqual(calls[1]['max_results'], 5)

    @patch('network_permission.ask', return_value=True)
    def test_worker_deadline_reports_unavailable(self, permission):
        with patch.object(online, 'run_result', return_value=ProcessResult('', -9, True, False)):
            self.assertEqual(online.isolated({'operation': 'check'})['status'], 'unavailable')

    def test_plain_download_and_provenance(self):
        with patch.object(online, 'isolated', return_value=response()):
            result = online.download(self.app, 'https://example.com/beacon', 'beacon.txt')
        self.assertTrue(result['saved'])
        self.assertFalse(result['published'])
        self.assertEqual((self.app / 'data/intake/beacon.txt').read_bytes(), TEXT)
        receipt = json.loads((self.app / result['provenance_report']).read_text())
        self.assertEqual(receipt['stored_sha256'], hashlib.sha256(TEXT).hexdigest())
        self.assertNotIn('body', receipt)

    def test_html_download_becomes_plain_text(self):
        raw = b'<p>SYNTHETIC beacon in blue cabinet.</p><script>not_a_command()</script>'
        with patch.object(online, 'isolated', return_value=response(raw, 'text/html')):
            online.download(self.app, 'https://example.com/beacon', 'beacon.txt')
        text = (self.app / 'data/intake/beacon.txt').read_text()
        self.assertIn('blue cabinet', text)
        self.assertNotIn('not_a_command', text)
        self.assertNotIn('<', text)

    def test_existing_file_refused_before_network(self):
        folder = self.app / 'data/intake'
        folder.mkdir(parents=True)
        (folder / 'beacon.txt').write_bytes(TEXT)
        with patch.object(online, 'isolated', side_effect=AssertionError('No fetch before refusal')):
            with self.assertRaises(ValueError):
                online.download(self.app, 'https://example.com/beacon', 'beacon.txt')
        self.assertEqual((folder / 'beacon.txt').read_bytes(), TEXT)

    def test_failed_download_has_no_partial_document(self):
        with patch.object(online, 'isolated', return_value={'status': 'unavailable', 'reason': 'Synthetic timeout'}):
            result = online.download(self.app, 'https://example.com/beacon', 'beacon.txt')
        self.assertFalse(result['saved'])
        self.assertFalse((self.app / 'data/intake/beacon.txt').exists())

    def test_wrong_pdf_and_binary_text_refused(self):
        for body, kind, name in [(b'<html>error</html>', 'text/html', 'beacon.pdf'),
                                  (b'\x00\x01', 'text/plain', 'beacon.txt')]:
            with self.subTest(name=name), patch.object(online, 'isolated', return_value=response(body, kind)):
                with self.assertRaises(ValueError):
                    online.download(self.app, 'https://example.com/beacon', name)
        self.assertFalse((self.app / 'data/intake').exists())

    def test_download_reindex_connects_to_offline_library(self):
        with patch.object(online, 'isolated', return_value=response()):
            result = online.download(self.app, 'https://example.com/beacon', 'beacon.txt', reindex=True)
        self.assertTrue(result['saved'])
        self.assertTrue(result['published'], result)
        import bot
        import document_intake
        root = document_intake.active_library(self.app)
        found = bot.retrieve(root, 'beacon')
        self.assertIn('blue cabinet', found['sources'][0]['text'])
        self.assertIn('beacon.txt', found['sources'][0]['source'])

    def test_failed_reindex_keeps_download_and_old_browser(self):
        with patch.object(online, 'isolated', return_value=response()):
            online.download(self.app, 'https://example.com/beacon', 'beacon.txt', reindex=True)
        before = (self.app / 'reference.html').read_bytes()
        with patch.object(online, 'isolated', return_value=response(b'%PDF-1.4 SYNTHETIC broken PDF', 'application/pdf')):
            result = online.download(self.app, 'https://example.com/beacon.pdf', 'broken.pdf', reindex=True)
        self.assertTrue(result['saved'])
        self.assertFalse(result['published'])
        self.assertEqual((self.app / 'reference.html').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
