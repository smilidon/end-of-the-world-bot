# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import document_workspace as documents
import flash_install
import reference_browser

ROOT = Path(__file__).resolve().parents[1]


class FlashInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='flash install fixture ')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.drive = self.base / 'simulated USB'
        self.drive.mkdir()
        self.target = self.drive / 'Offline Bot'
        self.env = dict(os.environ, HOME=str(self.base / 'synthetic home'), PYTHON=sys.executable)
        Path(self.env['HOME']).mkdir()

    def run_install(self, *args, input=None, ok=True):
        result = subprocess.run(['sh', str(ROOT / 'install.sh'), *map(str, args)],
                                input=input, text=True, capture_output=True, cwd=self.base,
                                env=self.env, timeout=30)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def args(self):
        return ['--simulate-drive', self.drive, '--dest', self.target]

    def test_bot_default_and_database(self):
        for mode in ('bot', 'database'):
            self.target = self.drive / mode
            self.run_install(*self.args(), '--mode', mode, '--confirm-target', self.target)
            config = json.loads((self.target / 'portable-install.json').read_text())
            self.assertEqual(config, {'mode': mode, 'model_location': 'host'})
            self.assertEqual((self.target / 'workspace').is_dir(), mode == 'bot')
            self.assertFalse((self.target / 'models').exists())
            page = (self.target / 'reference.html').read_text()
            self.assertIn('No reference documents installed yet', page)
            self.assertIn('connect-src \'none\'', page)
            self.assertFalse((self.target / 'library/local-qa').exists())
            if mode == 'database':
                result = subprocess.run(['sh', str(self.target / 'launch.sh'), 'ask', 'test', '--model', 'NOT_INSTALLED'], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('no inference', result.stderr)

    def test_interactive_defaults_and_confirmation(self):
        output = self.run_install(*self.args(), '--interactive', input='\n\n\n' + str(self.target) + '\n')
        self.assertIn('OPTIONAL', output.stdout)
        self.assertEqual(json.loads((self.target / 'portable-install.json').read_text())['mode'], 'bot')
        self.target = self.drive / 'Rejected'
        self.run_install(*self.args(), '--interactive', input='2\nn\nwrong\n', ok=False)
        self.assertFalse(self.target.exists())

    def test_dry_run_no_write_even_when_fetch_requested(self):
        before = list(self.base.rglob('*'))
        self.run_install(*self.args(), '--dry-run', '--mode', 'database', '--fetch-manuals')
        self.assertEqual(list(self.base.rglob('*')), before)
        self.run_install(*self.args(), '--confirm-target', 'wrong', ok=False)
        self.assertFalse(self.target.exists())

    def test_optional_usb_models_are_empty_and_explicit(self):
        output = self.run_install(*self.args(), '--models', 'usb', '--confirm-target', self.target)
        self.assertIn('speed/latency', output.stdout)
        self.assertEqual([p.name for p in (self.target / 'models').iterdir()], ['README.txt'])
        self.assertEqual(json.loads((self.target / 'portable-install.json').read_text())['model_location'], 'models')
        self.target = self.drive / 'db'
        self.run_install(*self.args(), '--mode', 'database', '--models', 'usb', ok=False)

    def test_unsafe_existing_symlink_system_and_source_targets(self):
        marker = self.drive / 'precious.txt'
        marker.write_text('synthetic user file')
        self.run_install('--drive', self.drive, '--dry-run', ok=False)
        self.run_install('--simulate-drive', '/', '--dry-run', ok=False)
        self.run_install('--dest', Path('/etc') / 'offline-bot-test', '--dry-run', ok=False)
        self.run_install('--dest', ROOT / 'new-install', '--dry-run', ok=False)
        self.run_install('--simulate-drive', self.drive, '--dest', self.drive, '--dry-run', ok=False)
        self.run_install(*self.args(), '--confirm-target', self.target)
        snapshot = {p.relative_to(self.target): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.target.rglob('*') if p.is_file()}
        self.run_install(*self.args(), '--confirm-target', self.target, ok=False)
        self.assertEqual(snapshot, {p.relative_to(self.target): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.target.rglob('*') if p.is_file()})
        self.assertEqual(marker.read_text(), 'synthetic user file')
        link = self.base / 'link'
        link.symlink_to(self.drive, target_is_directory=True)
        self.run_install('--dest', link / 'new', '--dry-run', ok=False)

    def test_discovery_inherits_usb_and_rejects_internal_readonly(self):
        tree = {'blockdevices': [
            {'path': '/dev/example', 'tran': 'usb', 'rm': False, 'children': [
                {'path': '/dev/example1', 'mountpoints': [str(self.drive)], 'size': 123}]},
            {'path': '/dev/internal', 'mountpoints': [str(self.base)], 'rm': '0', 'ro': '0'},
            {'path': '/dev/readonly', 'rm': True, 'ro': True, 'mountpoints': [str(self.base)]}]}
        with patch('flash_install.subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(tree))), patch('flash_install.os.path.ismount', return_value=True):
            found = flash_install.removable_drives()
        self.assertEqual([x['mount'] for x in found], [str(self.drive)])
        with patch('flash_install.shutil.disk_usage', return_value=type('Usage', (), {'free': 0})()):
            with self.assertRaisesRegex(ValueError, 'free space'):
                flash_install.validate_target(self.target, ROOT, self.drive)

    def test_clean_isolated_journey(self):
        from tools.verify_clean_install import verify
        result = verify(ROOT)
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual(set(result['references']), {'bot', 'database'})

    def test_drive_replaced_during_confirmation_is_refused(self):
        def answer(prompt):
            if prompt.startswith('Confirm'):
                self.drive.rename(self.base / 'old drive')
                self.drive.mkdir()
                return str(self.target)
            return ''
        with patch('builtins.input', side_effect=answer), patch('sys.stdout', new_callable=io.StringIO), patch('flash_install.subprocess.run'), patch('portable.install') as install:
            with self.assertRaisesRegex(ValueError, 'drive changed'):
                flash_install.main(ROOT, [*map(str, self.args()), '--interactive'])
            install.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_explicit_manual_fetch_prepares_browser_in_both_modes(self):
        for mode in ('bot', 'database'):
            self.target = self.drive / mode
            calls = []
            def download(command, **kwargs):
                calls.append(command)
                if '--fetch' in command:
                    (self.target / 'library/guides/fixture.txt').write_text('SYNTHETIC manual reference: amber beacon batteries in the blue cabinet. ' * 3)
                return subprocess.CompletedProcess(command, 0)
            with patch('flash_install.subprocess.run', side_effect=download), patch('sys.stdout', new_callable=io.StringIO), patch('flash_install.shutil.which', return_value='/synthetic/pdftotext'):
                flash_install.main(ROOT, [*map(str, self.args()), '--mode', mode, '--confirm-target', str(self.target), '--fetch-manuals'])
            self.assertEqual(len(calls), 2)
            self.assertNotIn('--fetch', calls[0])
            self.assertIn('--fetch', calls[1])
            self.assertIn('amber beacon batteries', (self.target / 'reference.html').read_text())

    def test_source_bootstrap_does_not_use_pinned_release(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'bootstrap.py'), '--from-source', str(ROOT), *map(str, self.args()), '--dry-run'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('DRY RUN', result.stdout)
        self.assertFalse(self.target.exists())


class DocumentWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'workspace'
        self.root.mkdir()
        self.tool = documents.Workspace(self.root)

    def test_create_read_update_print_and_conflict(self):
        created = self.tool.dispatch({'action': 'create', 'name': 'Directions.md', 'text': 'SYNTHETIC directions <script>alert(1)</script>'})
        read = self.tool.dispatch({'action': 'read', 'name': 'Directions.md'})
        self.assertEqual(created['sha256'], read['sha256'])
        for digest in (None, 'wrong'):
            with self.assertRaises(ValueError):
                self.tool.dispatch({'action': 'update', 'name': 'Directions.md', 'text': 'changed', 'expected_sha256': digest})
        changed = self.tool.dispatch({'action': 'update', 'name': 'Directions.md', 'text': 'Reviewed <script>not executable</script>', 'expected_sha256': read['sha256']})
        self.assertNotEqual(changed['sha256'], read['sha256'])
        out = self.tool.dispatch({'action': 'print', 'name': 'Directions.md'})
        page = (self.root / out['name']).read_text()
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>', page)
        with self.assertRaises(FileExistsError):
            self.tool.dispatch({'action': 'print', 'name': 'Directions.md'})

    def test_containment_and_actions(self):
        for name in ('../outside.txt', '/etc/passwd', '.env', 'nested/file.txt', 'a\\b.txt', 'a.py', 'a.sh', 'x\x00.txt', 'a..txt'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.tool.dispatch({'action': 'create', 'name': name, 'text': 'blocked'})
        for request in ({'action': 'shell', 'name': 'a.txt'}, {'action': 'read', 'name': 'a.txt', 'root': '/'}, {'action': 'create', 'name': 'a.txt', 'text': 'x' * (documents.LIMIT + 1)}):
            with self.assertRaises(ValueError):
                self.tool.dispatch(request)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_links_fifo_and_root_symlinks_do_not_touch_host_file(self):
        outside = self.base / 'outside.txt'
        outside.write_text('private synthetic sentinel')
        (self.root / 'link.txt').symlink_to(outside)
        os.link(outside, self.root / 'hard.txt')
        os.mkfifo(self.root / 'pipe.txt')
        for name in ('link.txt', 'hard.txt', 'pipe.txt'):
            for action in ('read', 'update', 'print', 'create'):
                with self.subTest(name=name, action=action), self.assertRaises((OSError, ValueError)):
                    self.tool.dispatch({'action': action, 'name': name, 'text': 'no', 'expected_sha256': hashlib.sha256(outside.read_bytes()).hexdigest()})
        linked_root = self.base / 'linked'
        linked_root.symlink_to(self.root)
        with self.assertRaises(OSError):
            documents.Workspace(linked_root).dispatch({'action': 'create', 'name': 'new.txt', 'text': 'no'})
        self.assertEqual(outside.read_text(), 'private synthetic sentinel')


class BrowserExport(unittest.TestCase):
    def test_real_index_safe_embedding_bounds_and_no_model(self):
        import bot
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / 'guides').mkdir()
            (base / 'guides/beacon.txt').write_text('SYNTHETIC amber beacon in blue cabinet </script><script>attack()</script> ' * 3)
            bot.build(base)
            out = base / 'reference.html'
            with patch('model_query.query', side_effect=AssertionError('No inference allowed')):
                result = reference_browser.export(base, out)
            self.assertGreater(result['excerpts'], 0)
            page = out.read_text()
            self.assertIn('guides/beacon.txt', page)
            self.assertIn('text page 1', page)
            self.assertNotIn('</script><script>attack()', page)
            with self.assertRaises(ValueError):
                reference_browser.export(base, out)
            # Verify existing output preserved (file unchanged) after refusal.
            preserved = out.read_text()
            self.assertIn('guides/beacon.txt', preserved)
            self.assertIn('text page 1', preserved)
            with patch('reference_browser.MAX_CHUNKS', 0):
                self.assertTrue(reference_browser.export(base, base / 'bounded.html')['truncated'])


if __name__ == '__main__':
    unittest.main()
