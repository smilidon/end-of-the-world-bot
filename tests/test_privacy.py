# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('privacy_scan', Path(__file__).resolve().parents[1] / 'tools/privacy_scan.py')
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)


class Privacy(unittest.TestCase):
    def test_sensitive_patterns_and_allowlist(self):
        samples = [
            '/ho' + 'me/example/private.txt',
            'https://example.invalid/?' + 'X-Amz-Signature=synthetic',
            'example' + '@example.invalid',
            'ghp_' + 'x' * 24,
            'https://user:password' + '@example.invalid/',
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(scan.inspect('source.txt', sample.encode(), {'source.txt'}))
        self.assertTrue(scan.inspect('library/data.txt', b'ordinary data', {'source.txt'}))
        self.assertFalse(scan.inspect('source.txt', b'Synthetic public source', {'source.txt'}))
        self.assertFalse(scan.inspect('source.txt', b'https://www.cdc.gov/water-emergency/media/pdfs/example.pdf', {'source.txt'}))

    def test_deleted_sensitive_content_remains_detected_in_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def git(*args):
                return subprocess.check_output(['git', '-C', td, *args], stderr=subprocess.DEVNULL)
            git('init', '-q')
            (root / 'RELEASE_FILES.txt').write_text('RELEASE_FILES.txt\nsource.txt\n')
            (root / 'source.txt').write_text('/ho' + 'me/example/private.txt')
            git('add', 'RELEASE_FILES.txt', 'source.txt')
            git('-c', 'user.name=Synthetic Audit', '-c', 'user.email=example' + '@example.invalid', 'commit', '-qm', 'Synthetic privacy fixture\n\n— Thumbo')
            (root / 'source.txt').write_text('Clean replacement')
            git('add', 'source.txt')
            with patch.object(scan, 'ROOT', root), patch('builtins.print'):
                self.assertTrue(scan.main())

    def test_unlisted_worktree_and_binary_are_not_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'RELEASE_FILES.txt').write_text('RELEASE_FILES.txt\n')
            (root / 'unexpected.txt').write_text('Synthetic ordinary data')
            (root / 'installer.deb').write_bytes(b'\xff\x00')
            with patch.object(scan, 'ROOT', root), patch('builtins.print') as output:
                self.assertTrue(scan.main())
            output.assert_any_call('unexpected.txt: not in source allowlist')
            output.assert_any_call('installer.deb: not in source allowlist')
            output.assert_any_call('installer.deb: binary')

    def test_pinned_binary_accepted_only_at_its_exact_digest(self):
        name, digest = next(iter(scan.BINARIES.items()))
        body = (Path(__file__).resolve().parents[1] / name).read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), digest, 'Pinned digest is stale')
        # The real bytes pass; tampered bytes and an unpinned name do not.
        self.assertFalse(scan.inspect(name, body, {name}))
        self.assertIn((name, 'binary'), scan.inspect(name, body + b'\x00', {name}))
        self.assertIn(('other.ico', 'binary'), scan.inspect('other.ico', body, {'other.ico'}))
        # Pinning does not exempt a file from the release allowlist.
        self.assertIn((name, 'not in source allowlist'), scan.inspect(name, body, set()))

    def test_unlisted_staged_and_deleted_history_remain_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def git(*args):
                return subprocess.check_output(['git', '-C', td, *args], stderr=subprocess.DEVNULL)
            git('init', '-q')
            (root / 'RELEASE_FILES.txt').write_text('RELEASE_FILES.txt\n')
            (root / 'unlisted.txt').write_text('Synthetic ordinary data, not a secret')
            git('add', 'RELEASE_FILES.txt', 'unlisted.txt')
            (root / 'unlisted.txt').unlink()
            with patch.object(scan, 'ROOT', root), patch('builtins.print') as output:
                self.assertTrue(scan.main())
            output.assert_any_call('unlisted.txt: not in source allowlist')
            git('-c', 'user.name=Synthetic Audit', '-c', 'user.email=example' + '@example.invalid', 'commit', '-qm', 'Synthetic staged inventory')
            git('rm', '--cached', 'unlisted.txt')
            git('-c', 'user.name=Synthetic Audit', '-c', 'user.email=example' + '@example.invalid', 'commit', '-qm', 'Synthetic removal')
            with patch.object(scan, 'ROOT', root), patch('builtins.print') as output:
                self.assertTrue(scan.main())
            output.assert_any_call('unlisted.txt: not in source allowlist')


if __name__ == '__main__':
    unittest.main()