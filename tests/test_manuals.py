# SPDX-License-Identifier: GPL-3.0-only
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.parse
import download_manuals as dm

PDF = b'%PDF-1.4\nSynthetic download fixture, not a real manual.\n%%EOF\n'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.hits.append(self.path)
        route = self.server.routes.get(self.path, (404, {}, b''))
        if isinstance(route, list):
            route = route.pop(0) if len(route) > 1 else route[0]
        code, headers, body = route
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass


class LocalOpener:
    """Test-only transport rewrite; production has no HTTP/local bypass flag."""
    def __init__(self, port):
        self.port = port
        self.inner = urllib.request.build_opener(dm.NoRedirect())
    def open(self, req, timeout):
        path = urllib.parse.urlsplit(req.full_url).path
        req = urllib.request.Request('http://127.0.0.1:' + str(self.port) + path, headers=dict(req.header_items()))
        return self.inner.open(req, timeout=timeout)


class Manuals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.worker.join()
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fd = dm.directory(self.root)
        self.addCleanup(os.close, self.fd)
        self.server.routes = {'/robots.txt':(200, {}, b'User-agent: *\nAllow: /\n'), '/manual.pdf':(200, {'Content-Type':'application/pdf'}, PDF)}
        self.server.hits = []
        self.waits = []
        self.pub = dm.Publisher(opener=LocalOpener(self.server.server_port), delay=0, sleep=self.waits.append)
        self.item = {'id':'m001', 'title':'Synthetic fixture', 'filename':'fixture.pdf', 'source_url':'https://publisher.test/manual.pdf', 'format':'pdf', 'download_status':'eligible', 'size_bytes':len(PDF), 'sha256':hashlib.sha256(PDF).hexdigest()}
    def test_download_resume_and_no_overwrite(self):
        self.assertEqual(dm.fetch_one(self.fd,self.item,self.pub),'downloaded_verified')
        hits = len(self.server.hits)
        self.assertEqual(dm.fetch_one(self.fd,self.item,self.pub),'already_verified')
        self.assertEqual(len(self.server.hits),hits)
        (self.root/'fixture.pdf').write_bytes(b'user document')
        with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
        self.assertEqual((self.root/'fixture.pdf').read_bytes(),b'user document')
    def test_html_mime_and_magic_rejected(self):
        for mime,body in [('text/html',PDF),('application/pdf',b'<html>access denied</html>')]:
            self.server.routes['/manual.pdf']=(200,{'Content-Type':mime},body)
            with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
            self.assertFalse(list(self.root.iterdir()))
    def test_short_oversize_wrong_hash(self):
        for body in [PDF[:-2],PDF+b'x',PDF.replace(b'Synthetic',b'Altered!!')]:
            self.server.routes['/manual.pdf']=(200,{'Content-Type': 'application/pdf'},body)
            with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
            self.assertFalse(list(self.root.iterdir()))
    def test_content_length_rejected_before_write(self):
        self.server.routes['/manual.pdf']=(200,{'Content-Type':'application/pdf','Content-Length':'99999999'},b'')
        with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
        self.assertFalse(list(self.root.iterdir()))
    def test_redirect_and_unapproved_redirect(self):
        self.server.routes['/manual.pdf']=(302,{'Location':'/actual.pdf'},b'')
        self.server.routes['/actual.pdf']=(200,{'Content-Type':'application/pdf'},PDF)
        self.assertEqual(dm.fetch_one(self.fd,self.item,self.pub),'downloaded_verified')
        (self.root/'fixture.pdf').unlink()
        for target in ['https://mirror.test/manual.pdf','http://publisher.test/manual.pdf','https://publisher.test/manual.pdf?' + 'token=example']:
            self.server.routes['/manual.pdf']=(302,{'Location':target},b'')
            with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
    def test_redirect_loop_bounded(self):
        self.server.routes['/manual.pdf']=(302,{'Location':'/manual.pdf'},b'')
        with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
        self.assertEqual(self.server.hits.count('/manual.pdf'),6)
    def test_robots_denied_or_unavailable(self):
        for route in [(200,{},b'User-agent: *\nDisallow: /\n'),(403,{},b'')]:
            self.pub.robots.clear(); self.server.routes['/robots.txt']=route
            with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
        self.assertNotIn('/manual.pdf',self.server.hits)
    def test_429_retry_after_and_excessive_wait(self):
        self.server.routes['/manual.pdf']=[(429,{'Retry-After':'3'},b''),(200,{'Content-Type':'application/pdf'},PDF)]
        self.assertEqual(dm.fetch_one(self.fd,self.item,self.pub),'downloaded_verified')
        self.assertIn(3,self.waits)
        (self.root/'fixture.pdf').unlink()
        self.server.routes['/manual.pdf']=(429,{'Retry-After':'600'},b'')
        with self.assertRaises(ValueError):dm.fetch_one(self.fd,self.item,self.pub)
        self.assertNotIn(600,self.waits)
    def test_retry_exhaustion(self):
        self.server.routes['/manual.pdf']=(503,{},b'')
        with self.assertRaises(OSError):dm.fetch_one(self.fd,self.item,self.pub)
        self.assertEqual(self.server.hits.count('/manual.pdf'),3)
    def test_symlink_and_permission_paths(self):
        (self.root/'link').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):dm.directory(self.root/'link'/'nested',True)
        (self.root/'fixture.pdf').symlink_to(self.root/'missing')
        with self.assertRaises(OSError):dm.fetch_one(self.fd,self.item,self.pub)
        blocked=self.root/'blocked';blocked.mkdir();blocked.chmod(0o500)
        try:
            if os.geteuid()!=0:
                with self.assertRaises(PermissionError):dm.directory(blocked/'new',True)
        finally:blocked.chmod(0o700)
    def test_atomic_publication_refuses_race(self):
        (self.root/'part').write_bytes(PDF)
        (self.root/'fixture.pdf').write_bytes(b'user')
        with self.assertRaises(FileExistsError):dm.publish(self.fd,'part','fixture.pdf')
        self.assertEqual((self.root/'fixture.pdf').read_bytes(),b'user')
    def test_catalog_validation_empty_dryrun_and_selection(self):
        path=self.root/'catalog.json'
        path.write_text(json.dumps({'schema':1,'items':[self.item]}))
        self.assertEqual(len(dm.load_catalog(path)['items']),1)
        for change in [{'filename':'../escape.pdf'},{'filename':'a/b.pdf'},{'source_url':'file:///etc/passwd'},{'sha256':None},{'size_bytes':dm.CAP+1}]:
            path.write_text(json.dumps({'schema':1,'items':[{**self.item,**change}]}))
            with self.assertRaises(ValueError):dm.load_catalog(path)
        path.write_text(json.dumps({'schema':1,'items':[]}))
        self.assertEqual(dm.main(['--manifest',str(path),'--dest',str(self.root/'new')]),0)
        self.assertFalse((self.root/'new').exists())
        with self.assertRaises(ValueError):dm.plan({'items':[]},['missing'],self.root)
    def test_timeout_retries_bounded(self):
        with patch.object(self.pub.opener,'open',side_effect=TimeoutError), self.assertRaises(TimeoutError):
            self.pub.request('https://publisher.test/manual.pdf')
        self.assertIn(1,self.waits);self.assertIn(2,self.waits)
    @patch('network_permission.ask', return_value=True)
    def test_incomplete_transfer_report_and_repeat(self, permission):
        import http.client
        catalog=self.root/'catalog.json'
        catalog.write_text(json.dumps({'schema':1,'items':[self.item]}))
        destination=self.root/'library'
        with patch.object(dm,'Publisher',return_value=self.pub), patch.object(dm,'fetch_one',side_effect=http.client.IncompleteRead(b'',1)):
            self.assertEqual(dm.main(['--manifest',str(catalog),'--dest',str(destination),'--all','--fetch']),1)
        report=json.loads(next(destination.glob('download-results-*.json')).read_text())
        self.assertEqual(len(report['failures']),1)
        with patch.object(dm,'Publisher',return_value=self.pub):
            self.assertEqual(dm.main(['--manifest',str(catalog),'--dest',str(destination),'--all','--fetch']),0)
        self.assertEqual((destination/'fixture.pdf').read_bytes(),PDF)

    def test_manifest_duplicate_and_missing_fetch_selection(self):
        path=self.root/'catalog.json'
        path.write_text(json.dumps({'schema':1,'items':[self.item,self.item]}))
        with self.assertRaises(ValueError):dm.load_catalog(path)
        self.assertEqual(dm.main(['--manifest',str(path),'--fetch']),2)

    def test_catalog_public_scope(self):
        data=dm.load_catalog(Path(dm.__file__).with_name('manuals.json'))
        self.assertEqual(len(data['items']),39)
        self.assertEqual(sum(x['download_status']=='eligible' for x in data['items']),21)
        self.assertTrue(all(x['format']=='pdf' for x in data['items'] if x['download_status']=='eligible'))
        self.assertNotIn('files',set().union(*(x.keys() for x in data['items'])))

if __name__=='__main__':unittest.main()
