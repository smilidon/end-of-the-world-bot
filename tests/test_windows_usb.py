# SPDX-License-Identifier: GPL-3.0-only
"""Execute the shipped PowerShell copier on Linux fixtures; not Windows qualification."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import portable
from tools.build_release import build

ROOT = Path(__file__).resolve().parents[1]
PWSH = os.environ.get('PWSH') or shutil.which('pwsh')


class WindowsUsbPackage(unittest.TestCase):
    def test_creator_and_tests_are_shipped_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = build(ROOT, base / 'first')
            self.assertEqual(archive.read_bytes(), build(ROOT, base / 'second').read_bytes())
            with zipfile.ZipFile(archive) as bundle:
                names = {name.split('/', 1)[1] for name in bundle.namelist()}
                self.assertTrue({'create-usb.ps1', 'docs/WINDOWS_USB.md',
                                 'tests/test_windows_usb.py'} <= names)
                self.assertEqual(names, set(portable.package_files(ROOT)))


@unittest.skipUnless(PWSH, 'PowerShell not installed; set PWSH to test the actual script')
class WindowsUsbCopy(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='windows usb fixtures ')
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.source = self.base / 'Extracted source [literal]'
        self.source.mkdir()
        for name, body in portable.package_files(ROOT).items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        self.drive = self.base / 'Mounted drive [literal]'
        self.drive.mkdir()
        self.target = self.drive / 'New Bot folder'
        self.sentinel = self.drive / 'existing personal file.txt'
        self.sentinel.write_bytes(b'Leave this file alone.\x00')

    def run_copy(self, *args, target=None, success=True):
        result = subprocess.run(
            [PWSH, '-NoLogo', '-NoProfile', '-NonInteractive', '-File',
             str(self.source / 'create-usb.ps1'), '-Destination',
             str(target or self.target), *map(str, args)],
            cwd=self.base, capture_output=True, text=True, timeout=45)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.sentinel.read_bytes(), b'Leave this file alone.\x00')
        return result.stdout + result.stderr

    def assert_no_copy(self):
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.drive.iterdir()), [self.sentinel])

    def test_copy_exact_allowlist_no_implicit_private_data(self):
        (self.source / '.secret').write_text('private fixture')
        (self.source / 'reference.html').write_text('not explicitly selected')
        (self.source / 'library').mkdir()
        (self.source / 'library/private.txt').write_text('private document')
        text = self.run_copy()
        self.assertIn('no Windows reference reader/content', text)
        actual = {p.relative_to(self.target).as_posix(): p.read_bytes()
                  for p in self.target.rglob('*') if p.is_file()}
        self.assertEqual(actual, portable.package_files(ROOT))
        self.assertNotIn('.end-of-world-copy-', ' '.join(p.name for p in self.drive.iterdir()))

    def test_optional_real_linux_export(self):
        import reference_browser
        import bot
        library = self.base / 'library'
        (library / 'guides').mkdir(parents=True)
        (library / 'guides/beacon.txt').write_text('SYNTHETIC amber beacon in the blue cabinet. ' * 4)
        bot.build(library)
        page = self.base / 'Prepared reference.html'
        reference_browser.export(library, page)
        self.run_copy('-ReferenceHtml', page)
        self.assertEqual((self.target / 'reference.html').read_bytes(), page.read_bytes())
        self.assertIn('amber beacon', page.read_text())
        self.assertFalse((self.target / 'library').exists())

    def test_preview_writes_nothing(self):
        self.assertIn('What if:', self.run_copy('-WhatIf'))
        self.assert_no_copy()

    def test_existing_empty_populated_and_file_destinations_preserved(self):
        for kind in ('empty', 'populated', 'file'):
            target = self.drive / kind
            if kind == 'file':
                target.write_bytes(b'original')
            else:
                target.mkdir()
                if kind == 'populated':
                    (target / 'settings.json').write_bytes(b'original')
            text = self.run_copy(target=target, success=False)
            self.assertIn('already exists', text)
            if kind == 'file':
                self.assertEqual(target.read_bytes(), b'original')
            elif kind == 'populated':
                self.assertEqual((target / 'settings.json').read_bytes(), b'original')
            else:
                self.assertEqual(list(target.iterdir()), [])

    def test_missing_parent_relative_and_nested_destination(self):
        for target in (self.drive / 'missing/new', Path('relative'), self.source / 'new'):
            with self.subTest(target=target):
                self.run_copy(target=target, success=False)
        self.assert_no_copy()
        self.assertFalse((self.source / 'new').exists())

    def test_tampered_missing_and_mismatched_manifest(self):
        path = self.source / 'bot.py'
        original = path.read_bytes()
        path.write_text('tampered')
        self.assertIn('checksum mismatch', self.run_copy(success=False))
        self.assert_no_copy()
        path.unlink()
        self.assertIn('file missing', self.run_copy(success=False))
        path.write_bytes(original)
        manifest = self.source / 'FILE_MANIFEST.sha256'
        manifest.write_text(manifest.read_text().splitlines()[0] + '\n')
        self.assertIn('does not match', self.run_copy(success=False))
        self.assert_no_copy()

    def test_unsafe_windows_names_and_case_collisions(self):
        allowlist = self.source / 'RELEASE_FILES.txt'
        original = allowlist.read_text()
        for name in ('../escape', '/absolute', './bot.py', 'a//b', 'a\\b',
                     'data:stream', 'CON', 'aux.txt', 'COM1.log', 'name.',
                     'name ', 'wild*card', 'BOT.py', 'bot.py'):
            with self.subTest(name=name):
                allowlist.write_text(original + name + '\n')
                text = self.run_copy(success=False)
                self.assertTrue('Unsafe Windows' in text or 'case-colliding' in text, text)
                self.assert_no_copy()
        allowlist.write_text(original)

    @unittest.skipIf(os.name == 'nt', 'Windows reparse-point coverage requires a separately prepared fixture')
    def test_symlink_source_files_parents_and_destinations(self):
        outside = self.base / 'outside'
        outside.mkdir()
        link = self.drive / 'linked'
        link.symlink_to(outside, target_is_directory=True)
        self.assertIn('reparse points', self.run_copy(target=link / 'new', success=False))
        self.assertEqual(list(outside.iterdir()), [])
        link.unlink()
        self.target.symlink_to(self.base / 'nonexistent')
        self.assertIn('reparse points', self.run_copy(success=False))
        self.target.unlink()
        bot = self.source / 'bot.py'
        bot.unlink()
        bot.symlink_to(ROOT / 'bot.py')
        self.assertIn('reparse points', self.run_copy(success=False))
        bot.unlink()
        bot.write_bytes((ROOT / 'bot.py').read_bytes())
        docs = self.source / 'docs'
        docs.rename(self.source / 'original-docs')
        docs.symlink_to(self.source / 'original-docs', target_is_directory=True)
        self.assertIn('reparse points', self.run_copy(success=False))
        self.assert_no_copy()

    def test_missing_or_linked_optional_reader_refused_before_copy(self):
        self.run_copy('-ReferenceHtml', self.base / 'missing.html', success=False)
        self.assert_no_copy()
        if os.name == 'nt':
            return
        page = self.base / 'linked.html'
        page.symlink_to(ROOT / 'README.md')
        self.run_copy('-ReferenceHtml', page, success=False)
        self.assert_no_copy()

    def test_copy_failure_and_late_destination_preserve_existing_data(self):
        # Inject deterministic races at staging creation without editing the
        # shipped script: source changes after validation, or target appears.
        wrapper = self.base / 'copy race fixture.ps1'
        for mode in ('source-changed', 'target-created'):
            with self.subTest(mode=mode):
                target = self.drive / mode
                wrapper.write_text(r"""
param($Creator, $ChosenTarget, $FixtureSource, $Mode)
function New-Item {
    [CmdletBinding()]
    param($ItemType, $Path)
    $item = Microsoft.PowerShell.Management\New-Item -ItemType $ItemType -Path $Path -ErrorAction Stop
    if ($Mode -eq 'source-changed') {
        [IO.File]::WriteAllText([IO.Path]::Combine($FixtureSource, 'bot.py'), 'changed after preflight')
    } else {
        [IO.Directory]::CreateDirectory($ChosenTarget) | Out-Null
        [IO.File]::WriteAllText([IO.Path]::Combine($ChosenTarget, 'personal.txt'), 'keep me')
    }
    return $item
}
& $Creator -Destination $ChosenTarget
""")
                result = subprocess.run(
                    [PWSH, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(wrapper),
                     str(self.source / 'create-usb.ps1'), str(target), str(self.source), mode],
                    capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('Partial files retained at:', result.stdout + result.stderr)
                self.assertNotIn('Copy complete:', result.stdout)
                partials = list(self.drive.glob('.end-of-world-copy-*'))
                self.assertEqual(len(partials), 1 if mode == 'source-changed' else 2)
                if mode == 'source-changed':
                    self.assertIn('Copied checksum mismatch', result.stdout + result.stderr)
                    self.assertFalse(target.exists())
                    (self.source / 'bot.py').write_bytes((ROOT / 'bot.py').read_bytes())
                else:
                    self.assertEqual((target / 'personal.txt').read_text(), 'keep me')
                    self.assertEqual(len(list(target.iterdir())), 1)
                self.assertEqual(self.sentinel.read_bytes(), b'Leave this file alone.\x00')

    @unittest.skipIf(os.name == 'nt' or getattr(os, 'geteuid', lambda: 1)() == 0,
                     'Permission checks require an ordinary non-Windows user')
    def test_permission_failure_preserves_drive(self):
        self.drive.chmod(0o555)
        try:
            self.run_copy(success=False)
            self.assert_no_copy()
        finally:
            self.drive.chmod(0o755)


if __name__ == '__main__':
    unittest.main()
