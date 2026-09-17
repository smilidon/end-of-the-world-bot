# SPDX-License-Identifier: GPL-3.0-only
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import compact_context as compact
import model_query


class Compact(unittest.TestCase):
    def test_serialization_whitelists_only_current_question_and_selected_excerpts(self):
        sources = [{'text': 'SYNTHETIC blue cabinet. ' * 2000, 'file': 'guide.md', 'location': 'page 1', 'tools': 'CATALOG_SECRET', 'history': 'HISTORY_SECRET'}] * 40
        for profile in compact.PROFILES:
            packed = compact.envelope('Current question?', sources, profile)
            body = json.dumps(packed['messages'])
            self.assertNotIn('CATALOG_SECRET', body);self.assertNotIn('HISTORY_SECRET', body)
            self.assertEqual(len(packed['messages']), 2)
            self.assertLessEqual(packed['input_token_upper_bound'], compact.PROFILES[profile]['input_budget'])
            self.assertLessEqual(len(packed['selected']), compact.PROFILES[profile]['excerpts'])
            self.assertIn('[excerpt ends]', body)
        self.assertIsNone(compact.envelope('Question?', sources, budget=1))
        with self.assertRaises(ValueError):
            compact.envelope('Question?', sources, budget=100000)

    def test_budget_fallback_and_incomplete_output_never_silently_truncated(self):
        with tempfile.TemporaryDirectory() as td:
            args = SimpleNamespace(question='Beacon?', search=None, retrieve_only=False, num_gpu=0, threads=1, ollama_url='http://127.0.0.1:11434/api/chat', profile='tiny', prompt_budget=1, history='IGNORED_HISTORY', tools='IGNORED_TOOLS')
            sources = [{'text': 'SYNTHETIC blue cabinet.', 'file': 'guide.md'}]
            with patch.object(model_query, 'HERE', Path(td), create=True), patch.object(model_query, 'MODEL', 'synthetic', create=True), patch.object(model_query, 'retrieve', return_value=sources, create=True):
                with patch('model_query.urllib.request.build_opener', side_effect=AssertionError('No inference over budget')):
                    result = model_query.query(args)
                self.assertFalse(result['model_called']);self.assertEqual(result['answer_status'], 'answer may be limited')
                args.prompt_budget = None
                opener = Mock();opener.open.return_value = io.BytesIO(json.dumps({'message': {'content': 'Incomplete dangerous sentence DO NOT'}, 'done_reason': 'length', 'eval_count': 128}).encode())
                with patch('model_query.urllib.request.build_opener', return_value=opener):
                    result = model_query.query(args)
                self.assertNotIn('Incomplete dangerous sentence', result['answer'])
                self.assertIn('Source excerpt', result['answer'])
                self.assertTrue(result['model_called'])
                self.assertNotIn('IGNORED_HISTORY', json.dumps(result['request']))
                self.assertNotIn('IGNORED_TOOLS', json.dumps(result['request']))

    def test_deterministic_calculation_no_execution(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No command')), patch('socket.socket', side_effect=AssertionError('No network')):
            self.assertEqual(compact.calculate('(8 + 4) / 3'), 4)
            for expression in ('__import__("os")', '2 ** 1000000', 'True', '1/0', '9e999', 'name.value'):
                with self.assertRaises((ValueError, SyntaxError)):
                    compact.calculate(expression)

    def test_explicit_retrieval_and_calculation_bypass_model_in_chat_adapter(self):
        import http_adapter
        app = http_adapter.Application(Path('/synthetic-unused'), 'synthetic', 'http://127.0.0.1:11434/api/chat')
        with patch('model_query.query', side_effect=AssertionError('No inference')), patch('http_adapter.bot.retrieve', return_value={'sources': [{'id': 'R1', 'source': 'fixture.md', 'text': 'SYNTHETIC evidence.'}]}):
            self.assertEqual(app.run({'messages': [{'role': 'user', 'content': 'calc: 2 + 3'}]})['answer'], '5')
            self.assertIn('SYNTHETIC evidence', app.run({'messages': [{'role': 'user', 'content': 'Read: fixture.md'}]})['answer'])


if __name__ == '__main__':
    unittest.main()
