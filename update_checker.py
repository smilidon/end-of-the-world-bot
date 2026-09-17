#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in release checker, not an installer. Standard library only; cache works offline."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
API = 'https://api.github.com/repos/smilidon/end-of-the-world-bot/releases'
RELEASES = 'https://github.com/smilidon/end-of-the-world-bot/releases/tag/'
CACHE_CAP = 512 * 1024
VERSION = re.compile(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(alpha|beta|rc)\.(0|[1-9][0-9]*))?\Z')


def version_key(value):
    """Order project SemVer releases numerically, including alpha.10 > alpha.2."""
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError('Unrecognized release version')
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError('Unrecognized release version')
    major, minor, patch, stage, number = match.groups()
    return (int(major), int(minor), int(patch), {'alpha': 0, 'beta': 1, 'rc': 2, None: 3}[stage], int(number or 0))


def release_rows(payload):
    if not isinstance(payload, list) or len(payload) > 100:
        raise ValueError('Invalid release listing')
    rows = []
    for item in payload:
        if not isinstance(item, dict) or item.get('draft') is not False:
            continue
        tag = item.get('tag_name')
        try:
            key = version_key(tag)
        except ValueError:
            continue
        # Both the GitHub flag and the version suffix can mark a prerelease.
        if type(item.get('prerelease')) is not bool:
            continue
        rows.append({'tag': tag, 'prerelease': item['prerelease'] or key[3] < 3,
                     'release_url': RELEASES + tag})
    return rows


def fetch_releases():
    """Internal worker: parent online_library.isolated() obtains permission first."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            raise ValueError('Unexpected release API redirect')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    rows = []
    for page in range(1, 4):
        request = urllib.request.Request(API + '?per_page=100&page=' + str(page), headers={
            'Accept': 'application/vnd.github+json', 'Accept-Encoding': 'identity',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'EndOfWorldBot-UpdateChecker'})
        try:
            with opener.open(request, timeout=5) as response:
                if response.status != 200:
                    raise ValueError('Release API did not return success')
                raw = response.read(CACHE_CAP + 1)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            return {'status': 'unavailable', 'reason': 'Release API HTTP ' + str(code) +
                    '; may be rate limited or unavailable. No update downloaded.'}
        if len(raw) > CACHE_CAP:
            raise ValueError('Release response exceeds limit')
        payload = json.loads(raw)
        rows.extend(release_rows(payload))
        if len(payload) < 100:
            return {'status': 'online', 'checked_at': datetime.now(timezone.utc).isoformat(),
                    'releases': rows, 'complete': True}
    return {'status': 'unavailable', 'reason': 'Release listing exceeds bounded pagination; latest release not established.'}


def validate_cache(data):
    if (not isinstance(data, dict) or data.get('status') != 'online' or data.get('complete') is not True
            or not isinstance(data.get('releases'), list) or len(data['releases']) > 300):
        raise ValueError('Invalid release cache')
    timestamp = datetime.fromisoformat(data['checked_at'])
    if timestamp.tzinfo is None:
        raise ValueError('Cache date must include a timezone')
    for row in data['releases']:
        version_key(row['tag'])
        if type(row['prerelease']) is not bool or row['release_url'] != RELEASES + row['tag']:
            raise ValueError('Invalid cached release')
    return data


def compare(current, channel, data):
    installed = version_key(current)
    selected_channel = ('prerelease' if installed[3] < 3 else 'stable') if channel == 'auto' else channel
    if selected_channel not in {'stable', 'prerelease'}:
        raise ValueError('Choose auto, stable or prerelease')
    candidates = [row for row in data['releases'] if selected_channel == 'prerelease' or
                  (not row['prerelease'] and version_key(row['tag'])[3] == 3)]
    result = {'installed_version': current, 'channel': selected_channel,
              'checked_at': data['checked_at'], 'update_available': None,
              'comparison': 'Published release versions only; unversioned source/branch changes are not compared.',
              'installed': False, 'downloaded': False}
    if not candidates:
        return {**result, 'status': 'no_matching_release', 'reason': 'No recognized release in this channel; update status unknown.'}
    latest = max(candidates, key=lambda row: version_key(row['tag']))
    available = version_key(latest['tag']) > installed
    return {**result, 'status': 'update_available' if available else 'no_newer_release',
            'update_available': available, 'latest_version': latest['tag'].removeprefix('v'),
            'release_url': latest['release_url'],
            'next_step': 'Review the release and install separately into a new folder; preserve your existing library.' if available else
                         'No newer published version found in this listing; this does not verify local source changes.'}


def check(app=ROOT, offline=False, channel='auto'):
    from index_builder import read_bounded
    from online_library import isolated, store_json
    app = Path(app).absolute()
    current = read_bounded(app / 'VERSION', 128)[0].decode('utf-8').strip()
    version_key(current)  # Do not make a connection for an invalid local version.
    if channel not in {'auto', 'stable', 'prerelease'}:
        raise ValueError('Choose auto, stable or prerelease')
    folder = app / 'data/update-cache'
    cached = None
    try:
        cached = validate_cache(json.loads(read_bounded(folder / 'releases.json', CACHE_CAP)[0]))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    fetched = {'status': 'offline', 'reason': 'Offline-only update check; no connection attempted.'} if offline else isolated({'operation': 'updates'})
    using_cache = fetched['status'] != 'online'
    data = cached if using_cache else validate_cache(fetched)
    if data is None:
        return {**fetched, 'cached': False, 'installed_version': current, 'update_available': None,
                'reason': fetched.get('reason', 'Release lookup failed') + ' No cached release information.',
                'installed': False, 'downloaded': False}
    warning = None
    if not using_cache:
        try:
            store_json(folder, 'releases.json', data, replace=True)
        except (OSError, ValueError):
            warning = 'Release check succeeded, but its cache could not be saved.'
    result = {**compare(current, channel, data), 'cached': using_cache,
              'network_status': fetched['status']}
    if using_cache:
        result['notice'] = 'Saved release information, not a live check. Original checked_at is retained.'
    if warning:
        result['cache_warning'] = warning
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=ROOT)
    parser.add_argument('--offline', action='store_true', help='Read saved release information without prompting or connecting')
    parser.add_argument('--channel', choices=['auto', 'stable', 'prerelease'], default='auto')
    args = parser.parse_args(argv)
    try:
        result = check(args.app, args.offline, args.channel)
        print(json.dumps(result, indent=2))
        return 1 if result['status'] in {'unavailable', 'offline'} else 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
