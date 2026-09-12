# SPDX-License-Identifier: GPL-3.0-only
"""Resource lifetime contracts, independent of interpreter garbage collection."""
import asyncio
import builtins
import fcntl
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error

import model_query
import openwebui_pipe


class QueryResources(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.handles = []
        self.args = SimpleNamespace(question='Synthetic beacon location?', search=None,
                                    retrieve_only=True, num_gpu=0, threads=1,
                                    ollama_url='http://127.0.0.1:11434/api/chat')
        self.sources = [{'source': 'synthetic.txt', 'text': 'Synthetic blue cabinet.'}]
        self.retrieve = Mock(return_value=self.sources)
        for name, value in [('HERE', self.root), ('MODEL', 'synthetic'),
                            ('retrieve', self.retrieve), ('open', self.open_lock)]:
            patcher = patch.object(model_query, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)

    def open_lock(self, *args, **kwargs):
        handle = builtins.open(*args, **kwargs)
        # Retain the real file object so refcounting cannot hide missing cleanup.
        self.handles.append(handle)
        self.addCleanup(handle.close)
        return handle

    def assert_closed(self):
        self.assertTrue(self.handles)
        self.assertTrue(all(handle.closed for handle in self.handles))
        with builtins.open(self.root / 'query.lock', 'a') as probe:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_retrieval_return_releases_lock(self):
        def retrieve(args):
            with builtins.open(self.root / 'query.lock', 'a') as probe:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self.sources
        self.retrieve.side_effect = retrieve
        self.assertEqual(model_query.query(self.args)['answer'], 'RETRIEVAL_ONLY')
        self.assert_closed()
        self.assertEqual(model_query.query(self.args)['answer'], 'RETRIEVAL_ONLY')
        self.assert_closed()

    def test_no_sources_return_releases_lock(self):
        self.retrieve.return_value = []
        self.assertEqual(model_query.query(self.args)['answer'], 'UNKNOWN')
        self.assert_closed()

    def test_retrieval_failure_releases_lock(self):
        self.retrieve.side_effect = RuntimeError('synthetic retrieval failure')
        with self.assertRaisesRegex(RuntimeError, 'synthetic retrieval failure'):
            model_query.query(self.args)
        self.assert_closed()

    def test_busy_closes_contender_without_unlocking_owner(self):
        with builtins.open(self.root / 'query.lock', 'a') as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'Another library query is active'):
                model_query.query(self.args)
            self.assertTrue(self.handles[0].closed)
            self.retrieve.assert_not_called()
            with builtins.open(self.root / 'query.lock', 'a') as probe:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assert_closed()

    def test_other_lock_failure_closes_file(self):
        with patch.object(model_query.fcntl, 'flock', side_effect=OSError('synthetic lock failure')):
            with self.assertRaisesRegex(OSError, 'synthetic lock failure'):
                model_query.query(self.args)
        self.retrieve.assert_not_called()
        self.assert_closed()

    def test_inference_success_and_failure_release_lock(self):
        self.args.retrieve_only = False
        for failure in (False, True):
            with self.subTest(failure=failure):
                opener = Mock()
                if failure:
                    opener.open.side_effect = TimeoutError('synthetic model timeout')
                else:
                    opener.open.return_value = io.BytesIO(json.dumps({
                        'message': {'content': 'Synthetic answer [S1].'},
                        'prompt_eval_count': 1200, 'eval_count': 8}).encode())
                with patch.object(model_query.urllib.request, 'build_opener', return_value=opener):
                    if failure:
                        with self.assertRaises(TimeoutError):
                            model_query.query(self.args)
                    else:
                        self.assertEqual(model_query.query(self.args)['answer'], 'Synthetic answer [S1].')
                self.assert_closed()


class PipeResources(unittest.TestCase):
    def test_http_errors_close_and_keep_sanitized_output(self):
        for raw, expected in [(b'{"error":"busy","request_id":"abcdef123456"}', 'busy; abcdef123456'),
                              (b'{"error":"private-detail","request_id":"invalid"}', 'unknown; unavailable'),
                              (b'not JSON', 'unknown; unavailable')]:
            with self.subTest(raw=raw):
                response = io.BytesIO(raw)
                self.addCleanup(response.close)
                error = urllib.error.HTTPError('http://127.0.0.1:8769/trial', 400, 'synthetic', {}, response)
                self.addCleanup(error.close)
                opener = Mock()
                opener.open.side_effect = error
                with patch.object(openwebui_pipe.urllib.request, 'build_opener', return_value=opener):
                    output = asyncio.run(openwebui_pipe.Pipe().pipe({'messages': []}))
                self.assertTrue(response.closed)
                self.assertEqual(output, 'Local adapter HTTP 400 [' + expected + ']. Check the sanitized adapter log.')

    def test_http_error_read_failure_still_closes_response(self):
        class BrokenBody(io.BytesIO):
            def read(self, size=-1):
                if size != 2048:
                    raise AssertionError('Error body read must remain bounded')
                raise OSError('synthetic read failure')
        response = BrokenBody()
        self.addCleanup(response.close)
        error = urllib.error.HTTPError('http://127.0.0.1:8769/trial', 400, 'synthetic', {}, response)
        self.addCleanup(error.close)
        opener = Mock()
        opener.open.side_effect = error
        with patch.object(openwebui_pipe.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(OSError, 'synthetic read failure'):
                asyncio.run(openwebui_pipe.Pipe().pipe({'messages': []}))
        self.assertTrue(response.closed)
