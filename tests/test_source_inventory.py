# SPDX-License-Identifier: GPL-3.0-only
"""Release inventory regressions shared by the source feature branches."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceInventory(unittest.TestCase):
    def test_release_verification_inventory_counts(self):
        names = (ROOT / 'RELEASE_FILES.txt').read_text().splitlines()
        allowlist = set(names)
        self.assertEqual(len(names), len(allowlist), 'Duplicate release entry')
        manifest = {
            line.split('  ', 1)[1]
            for line in (ROOT / 'FILE_MANIFEST.sha256').read_text().splitlines()
        }
        verification = ' '.join((ROOT / 'docs/VERIFICATION.md').read_text().split())
        self.assertEqual(manifest, allowlist - {'FILE_MANIFEST.sha256'})
        self.assertIn(f'The source allowlist contains {len(allowlist)} files;', verification)
        self.assertIn(f'the checksum manifest covers the other {len(manifest)} files.', verification)
        self.assertTrue({'tests/test_usb_defect.py', 'tests/test_usb_browser_defect.py'} <= allowlist)

    def test_tracked_source_inventory_matches_release_allowlist(self):
        if not (ROOT / '.git').exists():
            self.skipTest('Source archive has no Git index; package membership is checked separately')
        tracked = subprocess.check_output(
            ['git', '-C', str(ROOT), 'ls-files', '-z'], timeout=10
        ).decode().rstrip('\0').split('\0')
        allowlist = set((ROOT / 'RELEASE_FILES.txt').read_text().splitlines())
        self.assertEqual(set(tracked), allowlist)


if __name__ == '__main__':
    unittest.main()
