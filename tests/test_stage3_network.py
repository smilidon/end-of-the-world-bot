# SPDX-License-Identifier: GPL-3.0-only
"""Permission boundaries and program-release checks; no live provider traffic."""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
import urllib.error

import bootstrap
import download_manuals
import network_permission as permission
import online_library as online
from reference_helpers import ProcessResult
import update_checker as updates


class Permission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_only_explicit_yes_approves(self):
        for answer, expected in [('y', True), ('YES', True), (' yes ', True), ('', False),
                                 ('no', False), ('sure', False), ('yesterday', False)]:
            with self.subTest(answer=answer), patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value=answer):
                self.assertEqual(permission.ask('synthetic operation'), expected)

    def test_eof_interrupt_and_noninteractive_deny(self):
        for error in (EOFError, KeyboardInterrupt, OSError):
            with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', side_effect=error):
                self.assertFalse(permission.ask('synthetic operation'))
        with patch('sys.stdin.isatty', return_value=False), patch('builtins.input', side_effect=AssertionError('Should not read piped input')):
            self.assertFalse(permission.ask('synthetic operation'))

    def test_every_online_operation_denied_before_worker(self):
        for request in [{'operation': 'check'}, {'operation': 'search', 'query': 'beacon'},
                        {'operation': 'download', 'url': 'https://example.com/beacon'}, {'operation': 'updates'}]:
            with self.subTest(request=request), patch.object(permission, 'ask', return_value=False), \
                    patch.object(online, 'run_result', side_effect=AssertionError('Unapproved worker started')):
                result = online.isolated(request)
                self.assertEqual(result['status'], 'declined')
                self.assertFalse(result['network_attempted'])

    def test_approval_only_covers_one_invocation(self):
        process = ProcessResult('{"status":"reachable"}', 0, False, False)
        with patch.object(permission, 'ask', side_effect=[True, False]) as ask, patch.object(online, 'run_result', return_value=process) as run:
            self.assertEqual(online.isolated({'operation': 'check'})['status'], 'reachable')
            self.assertEqual(online.isolated({'operation': 'check'})['status'], 'declined')
        self.assertEqual(ask.call_count, 2)
        run.assert_called_once()
        sent = json.loads(run.call_args.args[0][-1])
        self.assertIs(sent['network_approved'], True)

    def test_private_worker_without_parent_approval_stays_offline(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(online.__file__)), '_worker', '{"operation":"check"}'], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'declined')

    def test_denied_download_does_not_create_intake(self):
        with patch.object(permission, 'ask', return_value=False), patch.object(online, 'run_result', side_effect=AssertionError('Network')):
            result = online.download(self.root, 'https://example.com/beacon', 'beacon.txt')
        self.assertFalse(result['saved'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_denied_search_uses_dated_cache(self):
        data = {'status': 'online', 'query': 'beacon', 'retrieved_at': '2026-09-16T00:00:00+00:00',
                'results': [{'title': 'SYNTHETIC', 'url': 'https://example.com/beacon', 'snippet': 'SYNTHETIC'}]}
        online.store_json(self.root / 'data/web-cache', hashlib.sha256(b'beacon').hexdigest() + '.json', data)
        with patch.object(permission, 'ask', return_value=False), patch.object(online, 'run_result', side_effect=AssertionError('Network')):
            result = online.search(self.root, 'beacon')
        self.assertEqual(result['status'], 'cached')
        self.assertEqual(result['retrieved_at'], data['retrieved_at'])
        self.assertIn('declined', result['reason'])

    def test_offline_search_never_prompts(self):
        with patch.object(permission, 'ask', side_effect=AssertionError('Prompt in offline mode')):
            self.assertEqual(online.search(self.root, 'beacon', offline=True)['status'], 'unavailable')

    def test_manual_fetch_denial_precedes_destination_and_publisher(self):
        catalog = self.root / 'catalog.json'
        item = {'id': 'fixture', 'title': 'SYNTHETIC', 'filename': 'fixture.pdf', 'format': 'pdf',
                'download_status': 'eligible', 'size_bytes': 1, 'sha256': '0' * 64,
                'source_url': 'https://example.com/fixture.pdf'}
        catalog.write_text(json.dumps({'schema': 1, 'items': [item]}))
        with patch.object(permission, 'ask', return_value=False), patch.object(download_manuals, 'Publisher', side_effect=AssertionError('Unapproved publisher')):
            code = download_manuals.main(['--manifest', str(catalog), '--dest', str(self.root / 'new'), '--all', '--fetch'])
        self.assertEqual(code, 0)
        self.assertFalse((self.root / 'new').exists())

    def test_bootstrap_denial_precedes_download_and_install(self):
        with patch.object(sys, 'argv', ['bootstrap.py', '--dest', str(self.root / 'new')]), \
                patch.object(bootstrap, 'ask_network', return_value=False), \
                patch.object(bootstrap, 'get', side_effect=AssertionError('Release download')), \
                patch.object(bootstrap.subprocess, 'run', side_effect=AssertionError('Installation')):
            self.assertEqual(bootstrap.main(), 0)
        self.assertFalse((self.root / 'new').exists())

    def test_standalone_bootstrap_prompt_defaults_no(self):
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value=''):
            self.assertFalse(bootstrap.ask_network('SYNTHETIC bootstrap'))
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='yes'):
            self.assertTrue(bootstrap.ask_network('SYNTHETIC bootstrap'))


class UpdateChecker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'VERSION').write_text('0.1.0-alpha.2\n')

    def listing(self, tags):
        return {'status': 'online', 'complete': True, 'checked_at': '2026-09-16T00:00:00+00:00',
                'releases': [{'tag': tag, 'prerelease': '-' in tag, 'release_url': updates.RELEASES + tag} for tag in tags]}

    def test_numeric_version_ordering(self):
        key = updates.version_key
        self.assertGreater(key('0.1.0-alpha.10'), key('0.1.0-alpha.2'))
        self.assertGreater(key('0.1.0-beta.1'), key('0.1.0-alpha.10'))
        self.assertGreater(key('0.1.0-rc.1'), key('0.1.0-beta.9'))
        self.assertGreater(key('0.1.0'), key('0.1.0-rc.9'))
        self.assertGreater(key('0.10.0'), key('0.9.10'))
        self.assertEqual(key('v1.2.3'), key('1.2.3'))

    def test_invalid_versions_not_guessed(self):
        for value in ['latest', 'v01.0.0', '0.1', '1.0.0-dev.1', '', None, '1.0.0;command']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                updates.version_key(value)

    def test_auto_prerelease_channel_includes_new_alphas(self):
        result = updates.compare('0.1.0-alpha.2', 'auto', self.listing(['v0.1.0-alpha.10', 'v0.1.0-alpha.3']))
        self.assertTrue(result['update_available'])
        self.assertEqual(result['latest_version'], '0.1.0-alpha.10')

    def test_stable_channel_excludes_prereleases(self):
        result = updates.compare('0.1.0', 'auto', self.listing(['v0.2.0-alpha.1', 'v0.1.1']))
        self.assertEqual(result['channel'], 'stable')
        self.assertEqual(result['latest_version'], '0.1.1')

    def test_equal_or_older_release_does_not_offer_downgrade(self):
        for tags in [['v0.1.0-alpha.2'], ['v0.1.0-alpha.1']]:
            result = updates.compare('0.1.0-alpha.2', 'auto', self.listing(tags))
            self.assertFalse(result['update_available'])
            self.assertEqual(result['status'], 'no_newer_release')
            self.assertIn('source', result['comparison'])

    def test_empty_channel_reports_unknown_not_up_to_date(self):
        result = updates.compare('0.1.0-alpha.2', 'stable', self.listing(['v0.2.0-alpha.1']))
        self.assertIsNone(result['update_available'])
        self.assertEqual(result['status'], 'no_matching_release')

    def test_release_rows_ignore_drafts_and_unrecognized_tags(self):
        rows = updates.release_rows([
            {'tag_name': 'v0.1.1', 'draft': False, 'prerelease': False, 'html_url': 'https://example.com/not-used'},
            {'tag_name': 'v9.0.0', 'draft': True, 'prerelease': False},
            {'tag_name': 'nightly', 'draft': False, 'prerelease': False}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['release_url'], updates.RELEASES + 'v0.1.1')

    def test_success_saved_and_offline_reuses_original_date(self):
        data = self.listing(['v0.1.0-alpha.3'])
        with patch.object(online, 'isolated', return_value=data):
            live = updates.check(self.root)
        self.assertTrue(live['update_available'])
        self.assertFalse(live['cached'])
        with patch.object(online, 'isolated', side_effect=AssertionError('Offline update request')), \
                patch.object(permission, 'ask', side_effect=AssertionError('Offline prompt')):
            cached = updates.check(self.root, offline=True)
        self.assertTrue(cached['cached'])
        self.assertEqual(cached['checked_at'], data['checked_at'])
        self.assertIn('not a live check', cached['notice'])
        self.assertFalse(cached['installed']); self.assertFalse(cached['downloaded'])

    def test_declined_check_reuses_cache(self):
        data = self.listing(['v0.1.0-alpha.3'])
        online.store_json(self.root / 'data/update-cache', 'releases.json', data)
        with patch.object(permission, 'ask', return_value=False), patch.object(online, 'run_result', side_effect=AssertionError('Unapproved request')):
            result = updates.check(self.root)
        self.assertTrue(result['cached'])
        self.assertEqual(result['network_status'], 'declined')

    def test_denied_check_without_cache_writes_nothing(self):
        with patch.object(permission, 'ask', return_value=False), patch.object(online, 'run_result', side_effect=AssertionError('Unapproved request')):
            result = updates.check(self.root)
        self.assertEqual(result['status'], 'declined')
        self.assertIsNone(result['update_available'])
        self.assertEqual([p.name for p in self.root.iterdir()], ['VERSION'])

    def test_corrupt_cache_does_not_crash(self):
        folder = self.root / 'data/update-cache'; folder.mkdir(parents=True)
        (folder / 'releases.json').write_text('{not JSON')
        self.assertIsNone(updates.check(self.root, offline=True)['update_available'])

    def test_invalid_local_version_refused_before_network(self):
        (self.root / 'VERSION').write_text('unknown')
        with patch.object(online, 'isolated', side_effect=AssertionError('No network for invalid version')), self.assertRaises(ValueError):
            updates.check(self.root)

    def test_cache_recompared_after_installed_version_changes(self):
        online.store_json(self.root / 'data/update-cache', 'releases.json', self.listing(['v0.1.0-alpha.3']))
        (self.root / 'VERSION').write_text('0.1.0-alpha.4')
        self.assertFalse(updates.check(self.root, offline=True)['update_available'])

    def test_forged_cache_url_refused(self):
        data = self.listing(['v0.1.0-alpha.3'])
        data['releases'][0]['release_url'] = 'https://example.com/not-this-program'
        with self.assertRaises(ValueError):
            updates.validate_cache(data)

    def test_github_fetch_uses_fixed_endpoint_and_headers(self):
        response = io.BytesIO(json.dumps([{'tag_name': 'v0.1.0-alpha.3', 'draft': False, 'prerelease': True}]).encode())
        response.status = 200
        opener = Mock(); opener.open.return_value = response
        with patch.object(updates.urllib.request, 'build_opener', return_value=opener):
            result = updates.fetch_releases()
        self.assertEqual(result['status'], 'online')
        request = opener.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith(updates.API + '?'))
        self.assertIsNone(request.get_header('Authorization'))

    def test_rate_limit_is_unavailable_not_no_updates(self):
        error = urllib.error.HTTPError(updates.API, 429, 'SYNTHETIC rate limit', {}, None)
        opener = Mock(); opener.open.side_effect = error
        with patch.object(updates.urllib.request, 'build_opener', return_value=opener):
            result = updates.fetch_releases()
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('429', result['reason'])

    def test_oversized_or_malformed_payload_refused(self):
        for payload in [b'x' * (updates.CACHE_CAP + 1), b'{}', b'not json']:
            response = io.BytesIO(payload); response.status = 200
            opener = Mock(); opener.open.return_value = response
            with patch.object(updates.urllib.request, 'build_opener', return_value=opener), self.assertRaises(ValueError):
                updates.fetch_releases()

    def test_pagination_checks_more_than_first_page(self):
        first = [{'tag_name': 'v0.1.0-alpha.1', 'draft': False, 'prerelease': True}] * 100
        second = [{'tag_name': 'v0.1.0-alpha.10', 'draft': False, 'prerelease': True}]
        responses = [io.BytesIO(json.dumps(page).encode()) for page in (first, second)]
        for response in responses: response.status = 200
        opener = Mock(); opener.open.side_effect = responses
        with patch.object(updates.urllib.request, 'build_opener', return_value=opener):
            result = updates.fetch_releases()
        self.assertEqual(opener.open.call_count, 2)
        self.assertEqual(updates.compare('0.1.0-alpha.2', 'auto', result)['latest_version'], '0.1.0-alpha.10')

    def test_incomplete_pagination_does_not_claim_latest(self):
        page = [{'tag_name': 'v0.1.0-alpha.1', 'draft': False, 'prerelease': True}] * 100
        responses = [io.BytesIO(json.dumps(page).encode()) for _ in range(3)]
        for response in responses: response.status = 200
        opener = Mock(); opener.open.side_effect = responses
        with patch.object(updates.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(updates.fetch_releases()['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
