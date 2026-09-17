#!/usr/bin/env python3
"""Regression test: browser-export first-run defect — unittest-discoverable."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reference_browser


class BrowserDefectTests(unittest.TestCase):
    """Prove empty generated replacement, populated/unknown preservation, symlink refusal."""

    def _make_library(self, root_path: Path):
        guides_dir = root_path / 'guides'
        guides_dir.mkdir(parents=True, exist_ok=True)
        (guides_dir / 'fixture.md').write_text(
            'Fixture guide content for library index. \n' * 10, encoding='utf-8')
        (root_path / 'local-qa').mkdir(parents=True, exist_ok=True)
        return root_path

    def _generated_empty_export(self, rows=0):
        payload = json.dumps({'rows': [{}] * rows, 'truncated': False}, ensure_ascii=True) if rows > 0 else json.dumps({'rows': [], 'truncated': False}, ensure_ascii=True)
        payload_escaped = payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        return reference_browser.PAGE.replace('__DATA__', payload_escaped)

    def test_empty_generated_export_replaced_by_first_populated_export(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'lib'
            self._make_library(root)
            # Create a populated sqlite index with one chunk.
            db_path = root / 'local-qa' / 'guides.sqlite'
            conn = sqlite3.connect(str(db_path))
            conn.execute('CREATE TABLE chunks (file TEXT, location TEXT, text TEXT)')
            conn.execute('INSERT INTO chunks VALUES (?, ?, ?)', ('guides/fixture.md', 'p1', 'First chunk text content here.'))
            conn.commit()
            conn.close()

            dest = Path(td) / 'export.html'
            # Pre-populate destination with a recognizable empty generated export (zero rows).
            dest.write_text(self._generated_empty_export(rows=0), encoding='utf-8')
            # Must NOT use file size as discriminator; replacement allowed only for verified empty rows.
            original_size = dest.stat().st_size  # size check exists but must not be the discriminator
            self.assertGreater(original_size, 0)  # file has content (template), but zero rows

            result = reference_browser.export(str(root), str(dest))
            self.assertEqual(result['excerpts'], 1)
            # Replacement occurred: content now has 1 row.
            content = dest.read_text(encoding='utf-8')
            payload_raw = content.split('<script id="records" type="application/json">')[1].split('</script>')[0]
            payload = json.loads(__import__('html').unescape(payload_raw))
            self.assertEqual(len(payload['rows']), 1)

    def test_populated_existing_export_refused_and_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'lib'
            self._make_library(root)
            db_path = root / 'local-qa' / 'guides.sqlite'
            conn = sqlite3.connect(str(db_path))
            conn.execute('CREATE TABLE chunks (file TEXT, location TEXT, text TEXT)')
            conn.execute('INSERT INTO chunks VALUES (?, ?, ?)', ('guides/fixture.md', 'p1', 'Chunk text here for reference row.'))
            conn.commit()
            conn.close()

            dest = Path(td) / 'export.html'
            # Create a populated prior export (1 real row) — must be preserved.
            real_row_payload = json.dumps({'rows': [{'file':'guides/fixture.md','location':'p1','text':'Chunk text here.'}], 'truncated': False}, ensure_ascii=True)
            populated_raw = self._generated_empty_export(rows=0)
            # Replace payload inside PAGE with real_row_payload (escaped)
            real_escaped = real_row_payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            populated = reference_browser.PAGE.replace('__DATA__', real_escaped)
            payload_check = json.loads(
                __import__('html').unescape(
                    populated.split('<script id="records" type="application/json">')[1].split('</script>')[0]
                )
            )
            self.assertEqual(len(payload_check['rows']), 1)  # confirm populated
            dest.write_text(populated, encoding='utf-8')

            # Must refuse — file is non-empty and has a row.
            with self.assertRaises(ValueError) as ctx:
                reference_browser.export(str(root), str(dest))
            msg = str(ctx.exception)
            self.assertTrue('non-empty' in msg.lower() or 'refusal' in msg.lower() or 'overwrite' in msg.lower(), msg)
            # Preserve original: content unchanged.
            after = dest.read_text(encoding='utf-8')
            self.assertEqual(after, populated)

    def test_unknown_existing_export_refused_and_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'lib'
            self._make_library(root)
            db_path = root / 'local-qa' / 'guides.sqlite'
            conn = sqlite3.connect(str(db_path))
            conn.execute('CREATE TABLE chunks (file TEXT, location TEXT, text TEXT)')
            conn.execute('INSERT INTO chunks VALUES (?, ?, ?)', ('guides/fixture.md', 'p1', 'Content.'))
            conn.commit()
            conn.close()

            dest = Path(td) / 'export.html'
            # Unknown file: no recognizable script tag, arbitrary content.
            dest.write_text('Some random user file with no data tag.', encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                reference_browser.export(str(root), str(dest))
            msg = str(ctx.exception)
            self.assertIn('unknown', msg.lower())
            after = dest.read_text(encoding='utf-8')
            self.assertEqual(after, 'Some random user file with no data tag.')

    def test_symlink_destination_refused_and_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'lib'
            self._make_library(root)
            db_path = root / 'local-qa' / 'guides.sqlite'
            conn = sqlite3.connect(str(db_path))
            conn.execute('CREATE TABLE chunks (file TEXT, location TEXT, text TEXT)')
            conn.execute('INSERT INTO chunks VALUES (?, ?, ?)', ('guides/fixture.md', 'p1', 'Content text.'))
            conn.commit()
            conn.close()

            real_target = Path(td) / 'real.html'
            real_target.write_text('Preserve this file.', encoding='utf-8')
            symlink_dest = Path(td) / 'link.html'
            symlink_dest.symlink_to(real_target)

            with self.assertRaises(ValueError) as ctx:
                reference_browser.export(str(root), str(symlink_dest))
            msg = str(ctx.exception)
            self.assertIn('symlink', msg.lower())
            # Symlink preserved.
            self.assertTrue(symlink_dest.is_symlink())
            # Real file untouched.
            self.assertEqual(real_target.read_text(encoding='utf-8'), 'Preserve this file.')

    def test_empty_generated_non_zero_size_but_zero_rows_is_still_replaceable(self):
        # Key point: file size is NOT the discriminator; zero reference rows is.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'lib'
            self._make_library(root)
            db_path = root / 'local-qa' / 'guides.sqlite'
            conn = sqlite3.connect(str(db_path))
            conn.execute('CREATE TABLE chunks (file TEXT, location TEXT, text TEXT)')
            conn.execute('INSERT INTO chunks VALUES (?, ?, ?)', ('guides/fixture.md', 'p1', 'Chunk.'))
            conn.commit()
            conn.close()

            dest = Path(td) / 'export.html'
            empty_text = self._generated_empty_export(rows=0)
            # Empty generated file has template (non-zero bytes) but zero rows.
            self.assertGreater(len(empty_text.encode('utf-8')), 0)  # non-zero size
            dest.write_text(empty_text, encoding='utf-8')
            # Replacement allowed despite non-zero size because rows == 0.
            result = reference_browser.export(str(root), str(dest))
            self.assertEqual(result['excerpts'], 1)
            content_after = dest.read_text(encoding='utf-8')
            payload_after = json.loads(
                __import__('html').unescape(
                    content_after.split('<script id="records" type="application/json">')[1].split('</script>')[0]
                )
            )
            self.assertEqual(len(payload_after['rows']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
