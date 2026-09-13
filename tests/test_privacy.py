# SPDX-License-Identifier: GPL-3.0-only
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


if __name__ == '__main__':
    unittest.main()
