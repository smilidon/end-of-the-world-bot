# SPDX-License-Identifier: GPL-3.0-only
"""Export a bounded, self-contained offline reference browser from the FTS index."""
import contextlib
import json
from pathlib import Path
import sqlite3

import library_access

MAX_CHUNKS = 10000
MAX_TEXT = 16 * 1024 * 1024
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>Offline reference library</title><style>
body{font:18px system-ui,sans-serif;max-width:75ch;margin:2em auto;padding:1em}input{font:inherit;width:95%}
pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #888;padding:1em 0}
@media print{input,button{display:none}}
</style><h1>Offline reference library</h1>
<p>Local source excerpts, not AI answers. No model, server or internet required. Search is lexical, not medical or navigation advice.</p>
<p id="summary"></p><label>Search words <input id="query" maxlength="400" type="search"></label>
<button id="search">Search</button><p id="status" role="status"></p><main id="results"></main>
<script id="records" type="application/json">__DATA__</script><script>
'use strict';
const data=JSON.parse(document.getElementById('records').textContent);
const summary=document.getElementById('summary');
summary.textContent=data.rows.length+' excerpts. '+(data.truncated?'Export limit reached; use CLI search for the rest. ':'')+
(data.rows.length?'Source dates and rights remain those of each original.':'No reference documents installed yet. Add authorized documents to library/guides, then run sh launch.sh index and sh launch.sh browser.');
function search(){
 const words=document.getElementById('query').value.toLowerCase().match(/[\\p{L}\\p{N}]+/gu)||[];
 const ranked=data.rows.map((row,i)=>({row,i,score:words.reduce((n,w)=>n+(row.file+' '+row.text).toLowerCase().includes(w),0)}))
 .filter(v=>!words.length||v.score>0).sort((a,b)=>b.score-a.score||a.i-b.i);
 const target=document.getElementById('results'); target.replaceChildren();
 for(const {row,i} of ranked.slice(0,40)){
  const item=document.createElement('article'),head=document.createElement('h2'),body=document.createElement('pre');
  head.textContent='[R'+(i+1)+'] '+row.file+' — '+row.location;
  body.textContent=row.text;item.append(head,body);target.append(item);
 }
 document.getElementById('status').textContent='Showing '+Math.min(40,ranked.length)+' of '+ranked.length+' matching excerpts. Print with Ctrl+P. No match does not prove absence.';
}
document.getElementById('search').addEventListener('click',search);
document.getElementById('query').addEventListener('keydown',event=>{if(event.key==='Enter')search()});search();
</script></html>'''


def export(root, destination):
    root = Path(root).absolute()
    for part in [root, *root.parents]:
        if part.is_symlink():
            raise ValueError('Library path must not contain symlinks')
    if not root.is_dir():
        raise ValueError('Library unavailable; create a dedicated library first')
    rows, size, truncated = [], 0, False
    index = Path(root) / 'local-qa/guides.sqlite'
    if index.exists():
        index = library_access.safe(Path(root), 'local-qa/guides.sqlite')
        with contextlib.closing(sqlite3.connect(index.as_uri() + '?mode=ro', uri=True)) as db:
            for file, location, text in db.execute('SELECT file,location,text FROM chunks ORDER BY rowid'):
                # Reject stale/protected sources, keep each excerpt bounded.
                library_access.safe(Path(root), file)
                text = text[:3600]
                size += len(text.encode('utf-8'))
                if len(rows) >= MAX_CHUNKS or size > MAX_TEXT:
                    truncated = True
                    break
                rows.append({'file': file, 'location': location, 'text': text})
    # First-run browser-export defect: safe replacement / refusal rules.
    dest_path = Path(destination)
    # Refuse symlinks unconditionally (preserve them; never follow or replace).
    if dest_path.is_symlink() or (dest_path.exists() and dest_path.is_symlink()):
        raise ValueError('Destination is a symlink; refused to follow or replace')
    # If destination already exists: allow replacement ONLY when it is a
    # recognizable prior app-generated export with zero reference rows.
    # Any non-empty, user, populated, or unknown file is refused and preserved.
    if dest_path.exists() and not dest_path.is_symlink():
        is_generated_empty = False
        try:
            content = dest_path.read_text(encoding='utf-8')
            # Recognizable as our generated page (contains the embedded data script).
            has_script_tag = '<script id="records" type="application/json">' in content
            if has_script_tag:
                # Check reference rows embedded in the JSON data block.
                # Look for the JSON payload: count actual 'file'/'location'/'text'
                # reference rows rather than using file size or byte length.
                import re
                # Extract the data payload inside the script tag.
                m = re.search(
                    r'<script id="records" type="application/json">(.*?)</script>',
                    content, re.DOTALL)
                if m:
                    import html
                    raw = html.unescape(m.group(1))
                    try:
                        payload = json.loads(raw)
                        row_count = len(payload.get('rows', []))
                        if row_count == 0:
                            is_generated_empty = True
                    except (ValueError, TypeError):
                        pass
        except (OSError, UnicodeDecodeError):
            pass
        if not is_generated_empty:
            raise ValueError('Destination exists with non-empty or unknown content; refusal to overwrite user/populated export')
    # If we reach here, either destination does not exist, or it is a
    # recognized empty generated export that may be safely replaced.
    data = json.dumps({'rows': rows, 'truncated': truncated}, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    # Write (replace permitted only for the verified-empty-generated case above).
    with dest_path.open('w', encoding='utf-8') as stream:
        stream.write(PAGE.replace('__DATA__', data))
    return {'excerpts': len(rows), 'truncated': truncated, 'file': str(destination)}
