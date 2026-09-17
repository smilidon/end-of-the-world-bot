# SPDX-License-Identifier: GPL-3.0-only
"""Real HTTP Application dispatch with synthetic library and mocked model/routes."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import http_adapter
import network_permission
import retrieval_support


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'guides').mkdir()
        (self.root / 'guides/route.txt').write_text('SYNTHETIC beacon storage in blue cabinet. Hard drive maintenance and route table reference.')
        self.app = http_adapter.Application(self.root, 'synthetic-model', 'http://127.0.0.1:11434/api/chat')
        self.scope = 'a' * 64

    def run_question(self, text):
        return self.app.run({'messages': [{'role': 'user', 'content': text}], 'route_scope': self.scope})

    def test_incidental_route_words_use_reference_fallback_without_model_or_network(self):
        with patch.object(http_adapter.named_routing, 'parse_request', side_effect=AssertionError('Misrouted reference')), \
                patch.object(http_adapter.model_query, 'query', side_effect=AssertionError('Missing-index fallback called model')), \
                patch.object(network_permission, 'ask', side_effect=AssertionError('Offline query requested network')):
            for q in ['Where is the beacon stored?', 'hard drive maintenance', 'What is a route table?']:
                with self.subTest(q=q):
                    result = self.run_question(q)
                    self.assertIn('SYNTHETIC', result['answer'])
                    self.assertEqual(result['retrieval_status']['index_status'], 'missing')

    def test_explicit_document_command_clears_pending_route(self):
        self.app.pending[self.scope] = {'time': time.time(), 'request': {'awaiting': 'region'}}
        with patch.object(http_adapter.named_routing, 'parse_request', side_effect=AssertionError('Read became a route')):
            result = self.run_question('Read: guides/route.txt')
        self.assertIn('blue cabinet', result['answer'])
        self.assertNotIn(self.scope, self.app.pending)

    def test_unrelated_question_does_not_continue_pending_route(self):
        self.app.pending[self.scope] = {'time': time.time(), 'request': {'awaiting': 'region'}}
        with patch.object(http_adapter.named_routing, 'parse_request', side_effect=AssertionError('Unrelated question continued route')):
            self.assertIn('blue cabinet', self.run_question('Where is the beacon stored?')['answer'])
        self.assertNotIn(self.scope, self.app.pending)

    def test_recognized_pending_region_still_dispatches(self):
        self.app.pending[self.scope] = {'time': time.time(), 'request': {'awaiting': 'region'}}
        with patch.object(http_adapter.named_routing, 'maps', return_value=[('ohio', {})]), \
                patch.object(http_adapter.multistate_routing, 'parse', return_value=None), \
                patch.object(http_adapter.named_routing, 'parse_request', return_value={'awaiting': 'endpoints', 'message': 'SYNTHETIC choose endpoints'}) as route:
            result = self.run_question('Ohio')
        route.assert_called_once()
        self.assertIn('choose endpoints', result['answer'])

    def test_explicit_geographic_request_still_dispatches(self):
        with patch.object(http_adapter.multistate_routing, 'parse', return_value=None), \
                patch.object(http_adapter.named_routing, 'parse_request', return_value={'awaiting': 'region', 'message': 'SYNTHETIC choose region'}) as route:
            result = self.run_question('Directions from Alpha to Beta')
        route.assert_called_once()
        self.assertIn('choose region', result['answer'])

    def test_empty_library_returns_missing_index_message_not_model_error(self):
        (self.root / 'guides/route.txt').unlink()
        with patch.object(http_adapter.model_query, 'query', side_effect=AssertionError('No-evidence model call')):
            result = self.run_question('beacon')
        self.assertIn('Index missing', result['answer'])
        self.assertEqual(result['prompt_tokens'], 0)

    def test_launcher_updates_offline_without_document_library(self):
        (self.root / 'VERSION').write_text('0.1.0-alpha.2\n')
        launch = Path(http_adapter.__file__).with_name('launch.sh')
        result = subprocess.run(['sh', str(launch), 'updates', '--app', str(self.root), '--offline'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        output = json.loads(result.stdout)
        self.assertEqual(output['status'], 'offline')
        self.assertIsNone(output['update_available'])
        self.assertNotIn('Allow network', result.stderr)


if __name__ == '__main__':
    unittest.main()
