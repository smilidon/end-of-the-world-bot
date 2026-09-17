# SPDX-License-Identifier: GPL-3.0-only
"""Per-operation network permission. Importing this module never connects."""
import sys


def ask(description):
    """Only an explicit interactive yes grants this one operation.

    EOF, unavailable/non-interactive stdin, Ctrl-C and every other reply deny.
    Approval is never saved. A localhost-only Ollama call is not Internet use.
    """
    try:
        if not sys.stdin.isatty():
            print('Network access not approved: run interactively to answer the prompt.', file=sys.stderr)
            return False
        print('This operation will use your existing network connection: ' + description, file=sys.stderr)
        print('It will not join Wi-Fi or change your network settings.', file=sys.stderr)
        print('Allow network access for this operation? [y/N] ', end='', flush=True, file=sys.stderr)
        return input().strip().casefold() in {'y', 'yes'}
    except (EOFError, OSError, AttributeError, KeyboardInterrupt):
        print('\nNetwork access declined; staying offline.', file=sys.stderr)
        return False


def describe(request):
    operation = request.get('operation')
    if operation == 'check':
        return 'contact duckduckgo.com to test reachability.'
    if operation == 'search':
        return 'send the query ' + repr(request.get('query', '')) + ' to DuckDuckGo through ddgs.'
    if operation == 'download':
        return ('download ' + repr(request.get('url', '')) +
                ', including publisher robots checks, retries and document redirects.')
    if operation == 'updates':
        return 'contact api.github.com for this program\'s release metadata only; no update will be installed.'
    raise ValueError('Unknown network operation')


def declined():
    return {'status': 'declined', 'network_attempted': False,
            'reason': 'Network access declined; no connection attempted. Local library unchanged.'}
