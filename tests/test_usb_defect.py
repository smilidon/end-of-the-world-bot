#!/usr/bin/env python3
"""Regression test: SQLite first-run USB defect — unittest-discoverable TestCase."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot


class USBDefectTests(unittest.TestCase):
    """Cover 0-byte index rebuild, preserved/refused valid/symlink index, and no-guide refusal."""

    def _fixture_text(self):
        # Long enough to create an FTS chunk (needs >40 chars per chunk segment)
        paragraphs = [
            "Diagnostic reference for the USB installation defect. "
            "When a 0-byte installer stub is present in the library directory, "
            "it must not silently replace a working index. The guide explains "
            "first-run behavior, symlink refusal, and empty-table handling.",
        ] * 20  # ~20 repetitions => long content for chunking
        return "\n\n".join(paragraphs)

    def _setup_library(self, td_path: Path, guides=True, empty_index=False, symlink_index=False):
        root = td_path if isinstance(td_path, Path) else Path(td_path)
        root.mkdir(parents=True, exist_ok=True)
        if guides:
            guides_dir = root / 'guides'
            guides_dir.mkdir(exist_ok=True)
            (guides_dir / 'fixture.md').write_text(self._fixture_text(), encoding='utf-8')
        index_dir = root / 'local-qa'
        index_dir.mkdir(parents=True, exist_ok=True)
        target = index_dir / 'guides.sqlite'
        if symlink_index:
            link_target = index_dir / 'real.sqlite'
            link_target.write_bytes(b'')
            target.symlink_to(link_target)
        elif empty_index:
            # 0-byte installer stub (no SQLite header, no chunks table)
            target.write_bytes(b'')
        return root, target

    def test_empty_index_with_guide_rebuilt(self):
        with tempfile.TemporaryDirectory() as td:
            root, target = self._setup_library(Path(td), guides=True, empty_index=True)
            result = bot.build(root)
            # After rebuild, chunks should exist and index should have data.
            self.assertEqual(result['indexed_files'], 1)
            self.assertGreater(result['chunks'], 0)
            with sqlite3.connect(str(target)) as db:
                count = db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
                self.assertGreater(count, 0)

    def test_valid_populated_index_preserved_and_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root, target = self._setup_library(Path(td), guides=True)
            # Create a real, populated index first.
            first = bot.build(root)
            self.assertGreater(first['chunks'], 0)
            # Second call with valid non-empty index must refuse.
            with self.assertRaises(ValueError) as ctx:
                bot.build(root)
            self.assertIn('Index exists with data', str(ctx.exception))

    def test_index_symlink_refused_and_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root, target = self._setup_library(Path(td), guides=True, symlink_index=True)
            with self.assertRaises(ValueError) as ctx:
                bot.build(root)
            msg = str(ctx.exception).lower()
            self.assertIn('symlink', msg)
            # Symlink must remain untouched (preserved, not followed/replaced).
            self.assertTrue(target.is_symlink())

    def test_empty_index_without_guide_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            root, target = self._setup_library(Path(td), guides=False, empty_index=True)
            # 0-byte index but no guides present => must refuse, not replace silently.
            with self.assertRaises(ValueError) as ctx:
                bot.build(root)
            msg = str(ctx.exception)
            # Either "empty and no guides present" or similar refusal message.
            self.assertTrue(
                'empty' in msg.lower() or 'no guides' in msg.lower() or 'unreadable' in msg.lower(),
                f"Unexpected refusal message: {msg}",
            )
            # The empty stub should remain (preserved, not replaced silently).
            self.assertTrue(target.exists())
            # Must still be 0 bytes (not replaced by a new SQLite file).
            self.assertEqual(target.stat().st_size, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
