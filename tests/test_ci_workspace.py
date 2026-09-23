# SPDX-License-Identifier: GPL-3.0-only
"""Exercise CI download isolation with fake installers; no network or elevation."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CIWorkspace(unittest.TestCase):
    def run_install_step(self, fail=False):
        workflow = (ROOT / '.github/workflows/tests.yml').read_text()
        marker = '      - name: Install PowerShell for USB copier tests\n        run: |\n'
        self.assertEqual(workflow.count(marker), 1)
        section = workflow.split(marker, 1)[1].split('\n      - ', 1)[0]
        script = textwrap.dedent(section)
        with tempfile.TemporaryDirectory(prefix='ci isolation ') as td:
            root = Path(td)
            checkout, runner, binaries = root / 'checkout', root / 'runner temp', root / 'bin'
            for folder in (checkout, runner, binaries):
                folder.mkdir()
            sentinel = checkout / 'source.txt'
            sentinel.write_text('Synthetic unchanged source')
            tools = {
                'wget': '''#!/bin/sh
set -eu
out=''
while [ "$#" -gt 0 ]; do
    if [ "$1" = '-O' ]; then shift; out="$1"; fi
    shift
done
case "$out" in "$RUNNER_TEMP"/*) ;; *) exit 31 ;; esac
printf 'synthetic installer' > "$out"
''',
                'sudo': '''#!/bin/sh
set -eu
case "$1" in
    dpkg)
        [ "$2" = '-i' ]
        case "$3" in "$RUNNER_TEMP"/*) ;; *) exit 32 ;; esac
        [ -f "$3" ]
        printf 'verified temporary installer\n' > "$PROOF"
        if [ "$FAIL_INSTALL" = 1 ]; then exit 23; fi
        ;;
    apt-get) ;;
    *) exit 33 ;;
esac
''',
                'pwsh': '#!/bin/sh\nexit 0\n',
            }
            for name, content in tools.items():
                path = binaries / name
                path.write_text(content)
                path.chmod(0o700)
            proof = root / 'proof.txt'
            env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ.get('PATH', '/usr/bin:/bin'),
                       RUNNER_TEMP=str(runner), FAIL_INSTALL='1' if fail else '0', PROOF=str(proof))
            result = subprocess.run(['/bin/bash', '-e', '-o', 'pipefail', '-c', script],
                                    cwd=checkout, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 23 if fail else 0, result.stderr)
            self.assertEqual(proof.read_text(), 'verified temporary installer\n')
            self.assertEqual(list(checkout.iterdir()), [sentinel])
            self.assertEqual(sentinel.read_text(), 'Synthetic unchanged source')
            self.assertEqual(list(runner.iterdir()), [], 'Installer staging must be cleaned on success and failure')

    def test_powershell_bootstrap_keeps_download_outside_checkout(self):
        self.run_install_step()

    def test_powershell_bootstrap_cleans_staging_after_failure(self):
        self.run_install_step(fail=True)


if __name__ == '__main__':
    unittest.main()
