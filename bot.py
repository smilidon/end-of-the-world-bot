#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""End of the World Bot: local reference CLI and explicit citation server."""
import contextlib
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit
import library_access as library
import citation_links
from reference_helpers import run, clean

def build(root):
    """Adapted from local-qa/ask.py build: same FTS5 schema and page chunks."""
    if not root.is_dir():
        raise ValueError('Create a dedicated library directory first')
    directory = root / 'local-qa'
    if directory.is_symlink():
        raise ValueError('Index directory must not be a symlink')
    directory.mkdir(exist_ok=True)
    target = directory / 'guides.sqlite'
    if target.exists():
        raise ValueError('Index exists; move it aside explicitly before rebuilding')
    files = [f for f in library.catalog(root) if Path(f).suffix.lower() in {'.pdf','.html','.htm','.txt','.md','.mdx'}]
    # Exclusive create: never replace a pre-existing index or follow a symlink.
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    count = 0
    with contextlib.closing(sqlite3.connect(target)) as db, db:
        db.execute('CREATE VIRTUAL TABLE chunks USING fts5(title,file UNINDEXED,location UNINDEXED,date UNINDEXED,text)')
        for name in files:
            f = library.safe(root, name)
            pdf = f.suffix.lower() == '.pdf'
            raw = run(['pdftotext','-layout',f,'-'],12,5000000) if pdf else f.read_bytes()[:5000000].decode('utf8','replace')
            pages = raw.split('\f') if pdf else [clean(raw) if f.suffix.lower() in {'.html','.htm'} else raw]
            for page, text in enumerate(pages, 1):
                text = ' '.join(text.split())
                for offset in range(0,len(text),3000):
                    chunk = text[offset:offset+3600]
                    if len(chunk)<40:
                        continue
                    location = f'PDF page {page}, text offset {offset}' if pdf else f'text page {page} offset {offset}'
                    db.execute('INSERT INTO chunks VALUES(?,?,?,?,?)',(f.stem,name,location,'publication date unverified',chunk))
                    count += 1
    return {'indexed_files':len(files),'chunks':count}

def retrieve(root, question):
    sources, status, message = library.retrieve(question, root)
    return {'sources':sources,'status':status,'message':message}

def serve(root, allowlist, port):
    names = json.loads(allowlist.read_text())
    if not isinstance(names,list) or not all(isinstance(n,str) and n.startswith(('guides/','collections/')) and n.endswith(('.pdf','.zim')) for n in names):
        raise ValueError('Allowlist must be a JSON array of guides/*.pdf or collections/*.zim paths')
    for name in names:
        library.safe(root,name)
    citation_links.ALLOWED = frozenset(names)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not citation_links.serve(self,root):
                self.send_error(404)
        def do_HEAD(self):
            if not citation_links.serve(self,root,head=True):
                self.send_error(404)
        def log_message(self,*args):
            pass
    with HTTPServer(('127.0.0.1',port),Handler) as server:
        citation_links.BASE = f'http://127.0.0.1:{server.server_port}/documents/'
        print(citation_links.BASE,flush=True)
        server.serve_forever()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True,help='Dedicated trusted document library; never a home directory')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('index')
    for name in ('search','ask'):
        p = sub.add_parser(name)
        p.add_argument('question')
        if name=='ask':
            p.add_argument('--model',required=True,help='Already installed Ollama model name')
            p.add_argument('--profile', choices=['tiny', 'standard'], default='tiny')
            p.add_argument('--prompt-budget', type=int, help='Optional smaller conservative prompt budget')
            p.add_argument('--num-gpu',type=int,default=0)
            p.add_argument('--threads',type=int,default=4)
            p.add_argument('--ollama-url',default='http://127.0.0.1:11434/api/chat')
    p = sub.add_parser('serve')
    p.add_argument('--allowlist',type=Path,required=True)
    p.add_argument('--port',type=int,default=8769)
    a = parser.parse_args()
    root = a.root.resolve()
    try:
        if a.command=='index':
            result = build(root)
        elif a.command=='search':
            result = retrieve(root,a.question)
        elif a.command=='serve':
            serve(root,a.allowlist,a.port)
            return
        else:
            u = urlsplit(a.ollama_url)
            if u.scheme!='http' or u.hostname!='127.0.0.1' or u.username or u.password or u.query or u.fragment or u.path!='/api/chat':
                raise ValueError('Ollama must use numeric HTTP loopback /api/chat')
            import model_query
            model_query.HERE = library.safe(root,'local-qa/guides.sqlite').parent
            model_query.MODEL = a.model
            def sources(_):
                return [{'id':s['id'],'title':s['source'],'file':s['source'],'location':s['source'],'date':'unverified','text':s['text']} for s in retrieve(root,a.question)['sources']]
            model_query.retrieve = sources
            a.search=None
            a.retrieve_only=False
            result = model_query.query(a)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (ValueError,OSError,sqlite3.Error) as exc:
        print(json.dumps({'error':type(exc).__name__,'message':'Local operation failed; check paths, dependencies and documented limits.'}),file=sys.stderr)
        raise SystemExit(1)

if __name__=='__main__':
    main()
