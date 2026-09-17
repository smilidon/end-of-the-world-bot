# SPDX-License-Identifier: GPL-3.0-only
"""Bounded subprocess results and HTML helpers; legacy run() returns text."""
from dataclasses import dataclass
import html.parser
import os
import selectors
import signal
import subprocess
import time
import types


class Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, t, a):
        if t in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, t):
        if t in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, d):
        if not self.skip:
            self.parts.append(d)


def clean(s):
    p = Text()
    p.feed(s)
    return ' '.join(' '.join(p.parts).split())


@dataclass(frozen=True)
class ProcessResult:
    text: str
    returncode: int
    timed_out: bool
    truncated: bool

    @property
    def ok(self):
        return self.returncode == 0 and not self.timed_out and not self.truncated

    def require_complete(self):
        if not self.ok:
            reason = 'timeout' if self.timed_out else 'output limit' if self.truncated else 'nonzero exit'
            raise ValueError('Extraction failed: ' + reason)
        return self.text


def run_result(cmd, seconds=8, cap=2000000):
    """Capture at most cap bytes; distinguish partial output from success.

    A deadline covers reading AND waiting after stdout closes. A process group
    prevents ordinary extractor children from surviving a timeout. No shell.
    """
    if seconds <= 0 or cap < 1:
        raise ValueError('Positive subprocess time and byte bounds required')
    end = time.monotonic() + seconds
    out = bytearray()
    timed_out = truncated = False
    with subprocess.Popen([str(x) for x in cmd], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                          start_new_session=True) as child:
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(child.stdout, selectors.EVENT_READ)
                while True:
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        break
                    if not sel.select(remaining):
                        timed_out = True
                        break
                    chunk = os.read(child.stdout.fileno(), min(65536, cap + 1 - len(out)))
                    if not chunk:
                        break
                    out.extend(chunk)
                    if len(out) > cap:
                        truncated = True
                        break
            if not timed_out and not truncated:
                try:
                    child.wait(timeout=max(.001, end - time.monotonic()))
                except subprocess.TimeoutExpired:
                    timed_out = True
        finally:
            if child.poll() is None or timed_out or truncated:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            child.wait()
    return ProcessResult(bytes(out[:cap]).decode('utf-8', 'replace'),
                         child.returncode, timed_out, truncated)


def run(cmd, seconds=8, cap=2000000):
    """Compatibility: bounded partial text for existing best-effort readers.

    Indexing must use run_result(...).require_complete(), never this wrapper.
    """
    return run_result(cmd, seconds, cap).text


def for_root(root):
    return types.SimpleNamespace(HERE=root / 'local-qa', run=run, clean=clean)
