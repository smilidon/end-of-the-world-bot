#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
case "$0" in */*) directory=${0%/*} ;; *) directory=. ;; esac
directory=$(CDPATH= cd -- "$directory" && pwd -P)
python=${PYTHON:-python3}
if ! command -v "$python" >/dev/null 2>&1; then
    echo "Python 3.11+ is required. Prepare Python with SQLite FTS5 on Linux before going offline; see START_HERE.md." >&2
    exit 1
fi
if ! "$python" -I -B -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    echo "Python 3.11+ is required. Select an installed interpreter with PYTHON; see START_HERE.md." >&2
    exit 1
fi
exec "$python" -I -B "$directory/portable.py" "$@"
