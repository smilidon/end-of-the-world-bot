# SPDX-License-Identifier: GPL-3.0-only
"""Exercise the actual shipped scripts, copies, permissions, and hostile paths."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import portable
from tools.build_release import build

ROOT = Path(__file__).resolve().parents[1]


class Portable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bot release test ')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.archive = build(ROOT, self.base / 'output')
        with zipfile.ZipFile(self.archive) as bundle:
            bundle.extractall(self.base / 'USB with spaces')
        self.app = self.base / 'USB with spaces' / self.archive.stem

    def run_script(self, *args, app=None, script='launch.sh', env=None, success=True):
        result = subprocess.run(['/bin/sh', str((app or self.app) / script), *args],
                                cwd=self.base, text=True, capture_output=True,
                                timeout=30, env=env)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def fixture(self, app):
        guides = app / 'library/guides'
        guides.mkdir(parents=True, exist_ok=True)
        (guides / 'beacon.txt').write_text('SYNTHETIC: Store amber beacon batteries in the dry blue cabinet. Software fixture only. ' * 3)
        return guides

    def assert_search(self, app):
        found = json.loads(self.run_script('search', 'Where are beacon batteries?', app=app).stdout)
        self.assertEqual(found['sources'][0]['id'], 'R1')
        self.assertIn('beacon.txt', found['sources'][0]['source'])
        self.assertIn('dry blue cabinet', found['sources'][0]['text'])
        self.assertIn('text page 1', found['sources'][0]['source'])

    def test_install_preserve_and_move(self):
        destination = self.base / 'Installed with spaces'
        self.run_script('--dest', str(destination), script='install.sh')
        self.fixture(destination)
        (destination / 'settings.json').write_text('{"synthetic":true}')
        self.run_script('index', app=destination)
        before = {str(p.relative_to(destination)): p.read_bytes() for p in destination.rglob('*') if p.is_file()}
        self.assert_search(destination)
        result = self.run_script('--dest', str(destination), script='install.sh', success=False)
        self.assertIn('already exists', result.stderr)
        after = {str(p.relative_to(destination)): p.read_bytes() for p in destination.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        moved = self.base / 'Moved USB folder'
        destination.rename(moved)
        self.assert_search(moved)
        self.run_script('index', app=moved, success=False)

    def test_default_install_and_new_version_preserve_library(self):
        user_dir = self.base / 'synthetic user'
        user_dir.mkdir()
        env = dict(os.environ, HOME=str(user_dir), PYTHON=sys.executable)
        self.run_script(script='install.sh', env=env)
        destination = user_dir / '.local/share/end-of-world-bot' / (ROOT / 'VERSION').read_text().strip()
        self.assertTrue((destination / 'launch.sh').is_file())
        self.fixture(destination)
        self.run_script('index', app=destination)
        upgraded = self.base / 'Separate new version'
        self.run_script('--dest', str(upgraded), script='install.sh')
        self.assertFalse((upgraded / 'library/guides/beacon.txt').exists())
        result = json.loads(self.run_script('--library', str(destination / 'library'),
                                           'search', 'beacon batteries', app=upgraded).stdout)
        self.assertIn('dry blue cabinet', result['sources'][0]['text'])
        self.assert_search(destination)

    def test_portable_no_executable_bits_or_pip_environment(self):
        self.fixture(self.app)
        for path in self.app.rglob('*'):
            if path.is_file():
                path.chmod(0o644)
        env = dict(os.environ, PYTHON=sys.executable, PYTHONPATH='/nonexistent', PYTHONHOME='/nonexistent')
        self.run_script('doctor', env=env)
        self.run_script('index', env=env)
        self.assert_search(self.app)
        moved = self.base / 'Another removable folder'
        self.app.rename(moved)
        self.assert_search(moved)

    def test_pdf_page_citation(self):
        from reportlab.pdfgen.canvas import Canvas
        guides = self.fixture(self.app)
        pdf = guides / 'example.pdf'
        canvas = Canvas(str(pdf))
        canvas.drawString(40, 700, 'SYNTHETIC cobalt lantern instructions: keep it in the green cabinet. Fixture only.')
        canvas.save()
        self.run_script('index')
        result = json.loads(self.run_script('search', 'cobalt lantern').stdout)
        self.assertIn('example.pdf PDF page 1', result['sources'][0]['source'])
        self.assertEqual(result['sources'][0]['id'], 'R1')

    def test_missing_python_and_poppler(self):
        empty = self.base / 'empty PATH'
        empty.mkdir()
        result = self.run_script('doctor', env=dict(os.environ, PATH=str(empty), PYTHON='missing-python'), success=False)
        self.assertIn('Python 3.11+', result.stderr)
        env = dict(os.environ, PATH=str(empty), PYTHON=sys.executable)
        self.assertIn('optional, missing', self.run_script('doctor', env=env).stdout)
        guides = self.fixture(self.app)
        self.run_script('index', env=env)
        (guides / 'example.pdf').write_text('synthetic not-a-real-PDF; dependency probe only')
        (self.app / 'library/local-qa/guides.sqlite').unlink()
        result = self.run_script('index', env=env, success=False)
        self.assertIn('PDFs need pdftotext', result.stderr)
        self.assertFalse((self.app / 'library/local-qa/guides.sqlite').exists())

    def test_permissions_and_symlink_destinations(self):
        blocked = self.base / 'read only'
        blocked.mkdir()
        blocked.chmod(0o555)
        self.addCleanup(blocked.chmod, 0o755)
        if os.geteuid() != 0:
            result = self.run_script('--dest', str(blocked / 'new'), script='install.sh', success=False)
            self.assertIn('Permission denied', result.stderr)
        link = self.base / 'linked'
        link.symlink_to(blocked, target_is_directory=True)
        result = self.run_script('--dest', str(link / 'new'), script='install.sh', success=False)
        self.assertIn('Symlink', result.stderr)
        self.assertFalse((blocked / 'new').exists())

    def test_manifest_paths_tampering_and_determinism(self):
        self.assertEqual(self.archive.read_bytes(), build(ROOT, self.base / 'second build').read_bytes())
        for name in ['../escape', '/absolute', 'a/../b', 'a//b', './bot.py', 'a\\b']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                portable.regular_path(self.app, name)
        linked = self.app / 'linked'
        linked.symlink_to(ROOT, target_is_directory=True)
        with self.assertRaises(ValueError):
            portable.regular_path(self.app, 'linked/bot.py')
        (self.app / 'bot.py').write_text('tampered synthetic content')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            build(self.app, self.base / 'tampered output')
        self.run_script('--dest', str(self.base / 'must not exist'), script='install.sh', success=False)
        self.assertFalse((self.base / 'must not exist').exists())
        with zipfile.ZipFile(self.archive) as bundle:
            expected = set((ROOT / 'RELEASE_FILES.txt').read_text().splitlines())
            self.assertEqual({name.split('/', 1)[1] for name in bundle.namelist()}, expected)
            self.assertTrue(all((info.external_attr >> 16) == 0o100644 for info in bundle.infolist()))

    def test_runtime_diagnostics(self):
        with patch.object(sys, 'version_info', (3, 10)), self.assertRaisesRegex(ValueError, 'Python 3.11'):
            portable.check_runtime()
        with patch('sqlite3.connect', side_effect=RuntimeError('synthetic missing FTS5')), self.assertRaisesRegex(ValueError, 'SQLite with FTS5'):
            portable.check_runtime()


if __name__ == '__main__':
    unittest.main()
