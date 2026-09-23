# SPDX-License-Identifier: GPL-3.0-only
"""Interactive flash installation layered on the existing verified installer."""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

MIN_FREE = 100 * 1024 * 1024


def no_links(path):
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError('Symlink install paths are not supported')


def removable_drives():
    """Read-only Linux discovery; never mount, format, unmount or invoke sudo."""
    try:
        result = subprocess.run(['lsblk', '--json', '--bytes', '--output',
                                 'PATH,TYPE,RM,TRAN,MOUNTPOINTS,RO,SIZE'],
                                check=True, capture_output=True, text=True, timeout=10)
        tree = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    found = []
    def enabled(value):
        return value is True or value == 1 or value == '1'
    def visit(device, removable=False, readonly=False):
        removable = removable or enabled(device.get('rm')) or device.get('tran') == 'usb'
        readonly = readonly or enabled(device.get('ro'))
        for mount in device.get('mountpoints') or []:
            if removable and not readonly and mount and Path(mount).is_absolute() and mount != '/':
                path = Path(mount)
                if path.is_dir() and os.path.ismount(path):
                    found.append({'mount': str(path), 'device': device.get('path', '?'), 'bytes': device.get('size', 0)})
        for child in device.get('children') or []:
            visit(child, removable, readonly)
    for device in tree.get('blockdevices', []):
        visit(device)
    return sorted(found, key=lambda item: item['mount'])


def validate_drive(drive, simulation=False):
    drive = Path(os.path.abspath(drive.expanduser()))
    no_links(drive)
    if not drive.is_dir():
        raise ValueError('Drive must already be mounted and writable; installer does not mount drives')
    if simulation:
        temporary = Path(tempfile.gettempdir()).resolve()
        if (drive == temporary or temporary not in drive.parents or os.path.ismount(drive)
                or drive.stat().st_dev != temporary.stat().st_dev):
            raise ValueError('Simulation requires a dedicated directory under the host temporary directory, not a mounted drive')
    elif str(drive) not in {item['mount'] for item in removable_drives()}:
        raise ValueError('Target is not a detected mounted writable removable/USB drive; no override is allowed. Use --dest for an explicit local install.')
    if not os.access(drive, os.W_OK | os.X_OK):
        raise ValueError('Drive is not writable by this user')
    return drive


def validate_target(destination, source, drive=None):
    target = Path(os.path.abspath(destination.expanduser()))
    no_links(target)
    if target.exists():
        raise ValueError('Destination already exists; nothing overwritten. Choose a new folder.')
    source = source.resolve()
    if target == source or source in target.parents or target in source.parents:
        raise ValueError('Destination must be separate from the source checkout')
    protected = [Path('/' + name) for name in ('etc', 'usr', 'bin', 'sbin', 'lib', 'lib64', 'boot', 'dev', 'proc', 'sys')]
    if target == Path.home() or any(target == p or p in target.parents for p in protected):
        raise ValueError('Unsafe system/home destination')
    if drive is not None and target.parent != drive:
        raise ValueError('Choose a NEW folder directly inside the selected drive, never its root')
    parent = target.parent
    while not parent.exists():
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        raise ValueError('Permission denied: destination parent is not writable')
    if shutil.disk_usage(parent).free < MIN_FREE:
        raise ValueError('At least 100 MiB free space required; documents and optional models need additional space')
    return target


def choose(prompt, default, choices):
    value = input(prompt).strip().lower() or default
    if value not in choices:
        raise ValueError('Invalid choice; nothing installed')
    return value


def main(root, arguments):
    import portable
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--interactive', action='store_true', help='Prompt for mounted drive, mode and options (default with no destination)')
    p.add_argument('--dest', type=Path, help='NEW install folder; without --drive this explicitly selects a local install')
    drives = p.add_mutually_exclusive_group()
    drives.add_argument('--drive', type=Path, help='Detected mounted removable drive; never a device node')
    drives.add_argument('--simulate-drive', type=Path, help='Dedicated existing temporary directory, NOT real removable media')
    p.add_argument('--local', action='store_true', help='Explicitly use the legacy versioned user-local destination')
    p.add_argument('--mode', choices=['bot', 'database'], default='bot')
    p.add_argument('--models', choices=['host', 'usb'], default='host', help='Placement plan only; no model download or host configuration changes')
    p.add_argument('--fetch-manuals', action='store_true', help='Explicitly fetch rights-eligible originals for personal noncommercial use; no models')
    p.add_argument('--confirm-target', help='For unattended drive installs, repeat the exact absolute NEW destination')
    p.add_argument('--dry-run', action='store_true', help='Verify and show plan; no writes or downloads')
    a = p.parse_args(arguments)
    if a.local and (a.drive or a.simulate_drive or a.dest):
        p.error('--local cannot be combined with a destination or drive')
    interactive = a.interactive or not (a.dest or a.drive or a.simulate_drive or a.local)
    print('Models are OPTIONAL. Keep models on the host SSD for performance (default).')
    print('USB model loading depends on speed/latency and may be very slow. No model is downloaded, moved or started by this installer.')
    drive = a.drive or a.simulate_drive
    if interactive:
        if not drive and not a.dest and not a.local:
            available = removable_drives()
            for number, item in enumerate(available, 1):
                print(f"{number}: {item['mount']} ({item['device']}, {item['bytes']} bytes)")
            selection = input('Select removable drive number, or type local for a user-local install: ').strip()
            if selection == 'local':
                a.local = True
            elif selection.isdecimal() and 1 <= int(selection) <= len(available):
                drive = Path(available[int(selection) - 1]['mount'])
            else:
                raise ValueError('No valid drive selected. Mount a drive in your file manager and retry.')
        a.mode = choose('Install [1] Bot (default) or [2] browser/database only? [1]: ', '1', {'1', '2'})
        a.mode = 'bot' if a.mode == '1' else 'database'
        if a.mode == 'bot' and drive:
            a.models = choose('Optional model placement plan: host (recommended) or usb? [host]: ', 'host', {'host', 'usb'})
        else:
            a.models = 'host'
        print('Reference documents are not bundled. The catalog lists eligible originals and manual-action items separately.')
        a.fetch_manuals = choose('Download eligible originals now for personal noncommercial use? [y/N]: ', 'n', {'y', 'n'}) == 'y'
    if a.mode == 'database' and a.models != 'host':
        raise ValueError('Database mode never needs models; omit --models usb')
    if a.models == 'usb' and not drive:
        raise ValueError('USB model placement requires an explicitly selected drive')
    if drive:
        drive = validate_drive(drive, bool(a.simulate_drive))
    identity = (drive.stat().st_dev, drive.stat().st_ino) if drive else None
    version = (root / 'VERSION').read_text().strip()
    # Pre-release channels only; a bare X.Y.Z is still refused as a stable claim.
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-(?:alpha|beta|rc)\.[0-9]+', version):
        raise ValueError('Invalid release version')
    destination = a.dest or (drive / 'EndOfWorldBot' if drive else Path.home() / '.local/share/end-of-world-bot' / version)
    target = validate_target(destination, root, drive)
    # Verify all source before confirmation, download, or creating any files.
    portable.package_files(root)
    plan = {'target': str(target), 'mode': a.mode, 'models': a.models, 'fetch_manuals': a.fetch_manuals,
            'simulation': bool(a.simulate_drive), 'dry_run': a.dry_run}
    print(json.dumps(plan, indent=2))
    subprocess.run([sys.executable, '-I', '-B', str(root / 'download_manuals.py'), '--dest', str(target / 'library/guides'), '--all'], check=True)
    if a.dry_run:
        print('DRY RUN: no files written, no downloads, no services changed.')
        return
    if drive or interactive:
        confirmed = input('Confirm by typing the exact target path above: ').strip() if interactive else a.confirm_target
        if confirmed != str(target):
            raise ValueError('Exact target confirmation required; nothing installed')
    if drive:
        # Recheck immediately before mutation in case media changed during prompts.
        validate_drive(drive, bool(a.simulate_drive))
        if (drive.stat().st_dev, drive.stat().st_ino) != identity:
            raise ValueError('Selected drive changed during confirmation; nothing installed')
    validate_target(target, root, drive)
    portable.install(target)
    try:
        (target / 'data/intake').mkdir(parents=True, mode=0o700)
        (target / 'data/generations').mkdir(mode=0o700)
        if a.mode == 'bot':
            (target / 'workspace').mkdir(mode=0o700)
            (target / 'diagnostics/guides').mkdir(parents=True, mode=0o700)
        config = {'mode': a.mode, 'model_location': 'models' if a.models == 'usb' else 'host'}
        (target / 'portable-install.json').write_text(json.dumps(config, indent=2) + '\n')
        if a.models == 'usb':
            (target / 'models').mkdir()
            (target / 'models/README.txt').write_text('Optional model storage only. No weights downloaded. See docs/FLASH_INSTALL.md. USB speed/latency matters. Configure only your own separately started Ollama process; never change an existing service.\n')
        if a.fetch_manuals:
            result = subprocess.run([sys.executable, '-I', '-B', str(target / 'download_manuals.py'), '--dest', str(target / 'library/guides'), '--all', '--fetch'])
            if result.returncode:
                print('Some manuals failed. Keep this installation; inspect download-results reports and resume the downloader, not the installer.')
            if shutil.which('pdftotext'):
                import bot
                bot.build(target / 'library')
            else:
                print('PDFs retained but not indexed: prepare Poppler pdftotext, then run index and browser. No system packages changed.')
        import reference_browser
        reference_browser.export(target / 'library', target / 'reference.html')
    except (OSError, ValueError) as exc:
        raise ValueError('New installation retained; optional preparation incomplete. Follow docs/FLASH_INSTALL.md to resume. ' + str(exc)) from exc
    print('Open reference.html in a browser (no server/model), or run sh launch.sh search in Bot mode after indexing.')
    if a.mode == 'bot':
        print('Workspace: workspace/. Optional AI: sh launch.sh ask QUESTION --model ALREADY_INSTALLED_MODEL')
    print('No host packages, service settings, Open WebUI data, or existing user files changed.')
