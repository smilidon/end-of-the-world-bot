# SPDX-License-Identifier: GPL-3.0-only
"""Static regressions for the beginner-friendly Windows installer path."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowsInstallerPackaging(unittest.TestCase):
    def test_installer_sources_are_release_allowlisted(self):
        allowlist = set((ROOT / 'RELEASE_FILES.txt').read_text().splitlines())
        required = {
            'windows/setup-wsl.sh',
            'windows/setup-windows.ps1',
            'windows/EndOfWorldBot-Setup.cmd',
            'packaging/windows/EndOfWorldBot.iss',
            'docs/WINDOWS_INSTALL.md',
            'tests/test_windows_installer.py',
        }
        self.assertTrue(required <= allowlist)

    def test_inno_installer_is_per_user_and_wsl_explicit(self):
        iss = (ROOT / 'packaging/windows/EndOfWorldBot.iss').read_text()
        self.assertIn('PrivilegesRequired=lowest', iss)
        self.assertIn('{localappdata}\\Programs\\EndOfWorldBot', iss)
        self.assertIn('windows\\EndOfWorldBot-Setup.cmd', iss)

        assistant = (ROOT / 'windows/setup-windows.ps1').read_text()
        self.assertIn('wsl.exe', assistant)
        self.assertIn('wsl --install -d Ubuntu', assistant)
        self.assertIn('does not silently enable Windows features', assistant)

    def test_release_workflow_builds_and_smoke_tests_setup_exe(self):
        workflow = (ROOT / '.github/workflows/archify.yml').read_text()
        self.assertIn('windows-installer:', workflow)
        self.assertIn('runs-on: windows-2025', workflow)
        self.assertIn('ISCC.exe', workflow)
        self.assertIn('Smoke-test silent installation', workflow)
        self.assertIn('EndOfWorldBot-Windows-Setup-', workflow)


if __name__ == '__main__':
    unittest.main()
