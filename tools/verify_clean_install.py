#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Repeatable clean-room journey. All simulated installs/data live in fresh temp dirs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(source=None, repo=None, ref=None, expected_sha=None):
    receipt = {'checks': [], 'physical_usb': False, 'model_downloads': False}
    with tempfile.TemporaryDirectory(prefix='bot clean room ') as td:
        base = Path(td)
        home = base / 'synthetic home'
        home.mkdir()
        env = dict(os.environ, HOME=str(home), PYTHON=sys.executable, PYTHONPATH='/nonexistent', PYTHONHOME='/nonexistent')
        def run(command, *, input=None, ok=True, label=None):
            result = subprocess.run(list(map(str, command)), input=input, text=True, capture_output=True,
                                    cwd=base, env=env, timeout=120)
            if (result.returncode == 0) != ok:
                raise AssertionError(f'{label or command}: {result.returncode}\n{result.stdout}\n{result.stderr}')
            receipt['checks'].append({'check': label or str(command[-1]), 'exit': result.returncode})
            return result
        checkout = base / 'fresh source'
        if repo:
            # Clone uses existing Git authentication, not a synthetic HOME. No push or mutation of the remote.
            subprocess.run(['git', 'clone', '--single-branch', '--branch', ref, repo, str(checkout)], check=True, timeout=120)
            sha = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
            if not expected_sha or sha != expected_sha:
                raise AssertionError('Fresh clone HEAD differs from expected pushed SHA')
            receipt.update(repo=repo, ref=ref, commit=sha)
        else:
            source = Path(source or ROOT).resolve()
            sys.path.insert(0, str(source))
            import portable
            bodies = portable.package_files(source)
            checkout.mkdir()
            for name, body in bodies.items():
                path = checkout / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            receipt['source'] = 'verified allowlisted temporary download copy'
        # Absolute paths in a checksum manifest are deliberately not supported.
        checked = subprocess.run(['sha256sum', '-c', 'FILE_MANIFEST.sha256'], cwd=checkout, capture_output=True, text=True, timeout=30)
        if checked.returncode:
            raise AssertionError(checked.stdout + checked.stderr)
        receipt['checks'].append({'check': 'fresh source manifest', 'exit': 0})
        for path in checkout.rglob('*'):
            if path.is_file() and '.git' not in path.relative_to(checkout).parts:
                path.chmod(0o644)
        drive = base / 'simulated flash drive'
        drive.mkdir()
        sentinels = base / 'untouched existing data'
        sentinels.mkdir()
        for name in ('trial.txt', 'usb-library.txt', 'service.txt', 'openwebui.db', 'user.txt'):
            (sentinels / name).write_text('synthetic existing data: ' + name)
        def hashes(root):
            return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        old = hashes(sentinels)
        installs = []
        for mode in ('bot', 'database'):
            target = drive / (mode + ' installation')
            args = ['sh', checkout / 'install.sh', '--simulate-drive', drive, '--dest', target, '--mode', mode]
            before = hashes(base)
            run([*args, '--dry-run', '--fetch-manuals'], label=mode + ': dry-run with fetch selected')
            if before != hashes(base) or target.exists():
                raise AssertionError('Dry-run mutated files')
            run([*args, '--confirm-target', target], label=mode + ': install')
            run(['sh', target / 'launch.sh', 'doctor'], label=mode + ': doctor')
            (target / 'library/guides/beacon.txt').write_text('SYNTHETIC: Store amber beacon batteries in the dry blue cabinet. Software fixture, not real advice. ' * 3)
            run(['sh', target / 'launch.sh', 'index'], label=mode + ': index')
            found = json.loads(run(['sh', target / 'launch.sh', 'search', 'beacon batteries'], label=mode + ': search').stdout)
            source_record = found['sources'][0]
            if source_record['id'] != 'R1' or 'guides/beacon.txt text page 1' not in source_record['source'] or 'dry blue cabinet' not in source_record['text']:
                raise AssertionError('Missing exact source/excerpt proof')
            receipt.setdefault('references', {})[mode] = {'id': source_record['id'], 'source': source_record['source'], 'excerpt_contains': 'dry blue cabinet'}
            run(['sh', target / 'launch.sh', 'browser'], label=mode + ': static export')
            page = (target / 'reference-updated.html').read_text()
            if 'dry blue cabinet' not in page or 'guides/beacon.txt' not in page:
                raise AssertionError('Static browser lacks source records')
            if mode == 'bot':
                def tool(request):
                    return json.loads(run(['sh', target / 'launch.sh', 'document'], input=json.dumps(request), label='document: ' + request['action']).stdout)
                created = tool({'action': 'create', 'name': 'Directions.md', 'text': 'SYNTHETIC directions. Review before printing.'})
                tool({'action': 'read', 'name': 'Directions.md'})
                tool({'action': 'update', 'name': 'Directions.md', 'text': 'Reviewed synthetic directions.', 'expected_sha256': created['sha256']})
                printed = tool({'action': 'print', 'name': 'Directions.md'})
                if 'Reviewed synthetic directions.' not in (target / 'workspace' / printed['name']).read_text():
                    raise AssertionError('Printable document not created')
                def diagnose(request):
                    return json.loads(run(['sh', target / 'launch.sh', 'diagnose'], input=json.dumps(request), label='diagnostics: ' + request['action']).stdout)
                main_index = target / 'library/local-qa/guides.sqlite'
                index_before = hashlib.sha256(main_index.read_bytes()).hexdigest()
                imported = diagnose({'action': 'import-guide', 'name': 'Offline fixture.md', 'text': '# Storage\nInspect free space. password=synthetic-sensitive-value'})
                if 'synthetic-sensitive-value' in (target / 'diagnostics/guides/Offline fixture.md').read_text():
                    raise AssertionError('Guide redaction failed')
                diagnose({'action': 'import-guide', 'name': 'Offline fixture.md', 'text': '# Storage\nUpdated offline guide.', 'expected_sha256': imported['sha256']})
                diagnose({'action': 'reindex'})
                diagnosis = diagnose({'action': 'analyze', 'text': '2026-09-13T12:34:56Z Linux ENOSPC password=synthetic-sensitive-value', 'report_name': 'Diagnostic observations.md'})
                if len(diagnosis['findings']) != 1 or diagnosis['findings'][0]['category'] != 'storage' or 'synthetic-sensitive-value' in json.dumps(diagnosis):
                    raise AssertionError('Evidence/redaction diagnostic proof failed')
                tool({'action': 'print', 'name': 'Diagnostic observations.md'})
                if hashlib.sha256(main_index.read_bytes()).hexdigest() != index_before:
                    raise AssertionError('Diagnostic reindex changed main library index')
                receipt['diagnostics'] = {'evidence': 'ENOSPC', 'secret_redacted': True, 'offline_guide_update': True, 'main_index_unchanged': True, 'printable_report': True}
            else:
                run(['sh', target / 'launch.sh', 'ask', 'beacon', '--model', 'NOT_INSTALLED'], ok=False, label='database: inference refused')
                run(['sh', target / 'launch.sh', 'document'], input='{}', ok=False, label='database: document tool refused')
            incoming = target / 'data/intake/lantern.md'
            incoming.write_text('SYNTHETIC cobalt lantern in the teal cabinet. Fixture only. ' * 3)
            before_scan = hashes(target)
            run(['sh', target / 'launch.sh', 'intake-scan'], label=mode + ': explicit intake scan')
            if hashes(target) != before_scan:
                raise AssertionError('Intake scan wrote files')
            run(['sh', target / 'launch.sh', 'reindex'], label=mode + ': atomic add/reindex')
            incoming.write_text('SYNTHETIC cobalt lantern now in the violet cabinet. Fixture only. ' * 3)
            run(['sh', target / 'launch.sh', 'reindex'], label=mode + ': offline change/reindex')
            updated = json.loads(run(['sh', target / 'launch.sh', 'search', 'cobalt lantern'], label=mode + ': updated search').stdout)
            if 'violet cabinet' not in updated['sources'][0]['text'] or 'violet cabinet' not in (target / 'reference.html').read_text():
                raise AssertionError('CLI/browser did not share updated content')
            old_page = (target / 'reference.html').read_bytes()
            bad = target / 'data/intake/invalid.pdf';bad.write_bytes(b'not a PDF')
            run(['sh', target / 'launch.sh', 'reindex'], ok=False, label=mode + ': failed rebuild preserved')
            if (target / 'reference.html').read_bytes() != old_page:
                raise AssertionError('Failed rebuild replaced valid publication')
            bad.rename(base / (mode + ' rejected synthetic PDF'))
            receipt.setdefault('reindex', {})[mode] = {'updated_excerpt': 'violet cabinet', 'source': updated['sources'][0]['source'], 'failure_preserved': True}
            run(['sh', target / 'launch.sh', 'calc', '(8 + 4) / 3'], label=mode + ': deterministic arithmetic')
            if mode == 'bot':
                limited = json.loads(run(['sh', target / 'launch.sh', 'ask', 'cobalt lantern', '--model', 'NOT_INSTALLED', '--prompt-budget', '1'], label='compact budget: no-model fallback').stdout)
                if limited['model_called'] or limited['answer_status'] != 'answer may be limited':
                    raise AssertionError('Budget fallback attempted inference')
            before = hashes(target)
            run([*args, '--confirm-target', target], ok=False, label=mode + ': reinstall refused')
            if hashes(target) != before:
                raise AssertionError('Reinstall changed existing installation')
            installs.append((mode, target))
        fixture_code = 'import sys,unittest;sys.path.insert(0,sys.argv[1]);suite=unittest.defaultTestLoader.discover(sys.argv[1]+"/tests",pattern="test_diagnostic_logs.py");result=unittest.TextTestRunner().run(suite);sys.exit(not result.wasSuccessful())'
        run([sys.executable, '-I', '-B', '-c', fixture_code, checkout], label='approved diagnostic discovery/scan: isolated fixtures, no live log reads')
        # Simulate deletion only by hiding our disposable source copy. Never touch the caller checkout.
        checkout.rename(base / 'source parked to simulate deletion')
        for mode, target in installs:
            moved = drive / (mode + ' moved installation')
            target.rename(moved)
            run(['sh', moved / 'launch.sh', 'search', 'Read: guides/legacy-guides/beacon.txt'], label=mode + ': moved-folder read without source')
        if hashes(sentinels) != old:
            raise AssertionError('Synthetic pre-existing data changed')
        receipt['checks'].append({'check': 'all five synthetic existing-data sentinels unchanged', 'exit': 0})
        receipt['result'] = 'PASS'
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--repo', help='Git URL to clone; no real install/data paths accepted')
    parser.add_argument('--ref', help='Branch to clone')
    parser.add_argument('--expect-sha', help='Required exact commit for remote verification')
    parser.add_argument('--receipt', type=Path, help='Write JSON to a NEW file outside the checkout')
    a = parser.parse_args()
    if a.repo and not (a.ref and a.expect_sha):
        parser.error('--repo requires --ref and --expect-sha')
    result = verify(a.source, a.repo, a.ref, a.expect_sha)
    text = json.dumps(result, indent=2) + '\n'
    if a.receipt:
        with a.receipt.open('x') as stream:
            stream.write(text)
    print(text, end='')


if __name__ == '__main__':
    main()
