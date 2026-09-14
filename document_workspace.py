# SPDX-License-Identifier: GPL-3.0-only
"""Small document tool API. The owner supplies the root, never the model/request."""
import contextlib
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys

LIMIT = 256 * 1024
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,79}\.(?:txt|md)\Z')


@contextlib.contextmanager
def directory(root):
    """Open every directory component without following symlinks; pin its inode."""
    path = Path(root).absolute()
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        os.close(fd)


def read_at(fd, name):
    file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(file_fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT:
            raise ValueError('Only bounded, single-link regular documents are allowed')
        body = stream.read(LIMIT + 1)
    if len(body) > LIMIT:
        raise ValueError('Document too large')
    return body


def printable(name, text):
    return ('<!doctype html><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>' + html.escape(name) + '</title><style>body{font:16px sans-serif;max-width:70ch;margin:2em auto}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere}@media print{body{margin:0}}</style>'
            '<h1>' + html.escape(name) + '</h1><pre>' + html.escape(text) + '</pre>').encode()


class Workspace:
    def __init__(self, root):
        self.root = Path(root)

    def dispatch(self, request):
        """create/read/update/print only; no shell, execution, deletion or host paths.

        update requires the SHA-256 returned by read/create (optimistic concurrency).
        print exclusively creates escaped HTML; the user opens it and uses Ctrl+P.
        """
        if not isinstance(request, dict) or set(request) - {'action', 'name', 'text', 'expected_sha256'}:
            raise ValueError('Invalid document request')
        action, name = request.get('action'), request.get('name')
        if not isinstance(action, str) or action not in {'create', 'read', 'update', 'print'} or not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError('Use create/read/update/print and a plain .txt or .md document name')
        if action in {'create', 'update'}:
            text = request.get('text')
            if not isinstance(text, str) or '\x00' in text:
                raise ValueError('UTF-8 document text required')
            body = text.encode('utf-8')
            if len(body) > LIMIT:
                raise ValueError('Document too large (256 KiB maximum)')
        with directory(self.root) as fd:
            if action in {'read', 'print', 'update'}:
                old = read_at(fd, name)
                digest = hashlib.sha256(old).hexdigest()
                if action == 'read':
                    return {'name': name, 'text': old.decode('utf-8'), 'sha256': digest}
                if action == 'update' and request.get('expected_sha256') != digest:
                    raise ValueError('Document changed; read it again before updating')
                if action == 'print':
                    body = printable(name, old.decode('utf-8'))
                    name += '.print.html'
            if action in {'create', 'print'}:
                out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                with os.fdopen(out, 'wb') as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
            else:
                # Replace the directory entry, never truncate a symlink/hardlink target.
                temp = '.edit-' + secrets.token_hex(16)
                out = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                try:
                    with os.fdopen(out, 'wb') as stream:
                        stream.write(body)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
                finally:
                    try:
                        os.unlink(temp, dir_fd=fd)
                    except FileNotFoundError:
                        pass
        return {'name': name, 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}


def main(root):
    raw = sys.stdin.buffer.read(LIMIT * 6 + 1025)
    if len(raw) > LIMIT * 6 + 1024:
        raise ValueError('Request too large')
    print(json.dumps(Workspace(root).dispatch(json.loads(raw)), ensure_ascii=False))
