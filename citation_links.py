# SPDX-License-Identifier: GPL-3.0-only
"""Read-only, fixed-inventory local citations. No generic filesystem handler."""
import io, json, os, pathlib, re, stat
from urllib.parse import quote, unquote, urlsplit, parse_qs
import library_access
ALLOWED=frozenset()  # Populated only by explicit local CLI configuration.
BASE='http://127.0.0.1:8769/documents/'

def open_document(root, name):
 if name not in ALLOWED:raise ValueError('Unavailable')
 # Walk all components with dirfd + NOFOLLOW, including mount-root ancestors.
 parts=(root/pathlib.PurePosixPath(name)).parts
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in parts[1:-1]:
   new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
   os.close(fd);fd=new
  out=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
 finally:os.close(fd)
 if not stat.S_ISREG(os.fstat(out).st_mode):os.close(out);raise ValueError('Unavailable')
 return os.fdopen(out,'rb')

def source_url(source,root):
 m=re.fullmatch(r'(guides/[^\r\n]+\.pdf) PDF page ([1-9][0-9]*)(?:, text offset [0-9]+)?',source)
 z=re.match(r'(collections/[^\r\n]+\.zim) article ([0-9]+): ',source)
 hit=m or z
 if not hit:return None
 try:
  with open_document(root,hit[1]):pass
 except (OSError,ValueError):return None
 return BASE+quote(hit[1],safe='/')+('#page='+hit[2] if m else '?article='+hit[2])

def escape_label(s):
 return re.sub(r'([\\\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e])',r'\\\1',' '.join(s.split()))

def render(answer,sources,root):
 links=[];seen=set()
 for s in sources:
  sid=s.get('id','')
  if not re.fullmatch(r'R[1-9][0-9]*',sid) or sid in seen:continue
  url=source_url(str(s.get('source','')),root)
  if not url:continue
  seen.add(sid)
  answer=answer.replace('['+sid+']','['+sid+']('+url+')')
  links.append('- ['+escape_label(sid+' — '+s['source'])+']('+url+')')
 return answer+('\n\nLocal sources:\n'+'\n'.join(links) if links else '')

def serve(handler,root,head=False):
 if not handler.path.startswith('/documents/'):return False
 stream=None
 try:
  if handler.headers.get_all('Host')!=['127.0.0.1:'+str(handler.server.server_port)]:
   handler.send_error(403);return True
  u=urlsplit(handler.path)
  name=unquote(u.path[len('/documents/'):],errors='strict')
  stream=open_document(root,name)
  kind='application/pdf';filename='document.pdf'
  if name.endswith('.zim'):
   q=parse_qs(u.query,strict_parsing=True)
   if set(q)!={'article'} or len(q['article'])!=1 or not re.fullmatch(r'[0-9]{1,10}',q['article'][0]):raise ValueError('Article required')
   helper=library_access.load(root)
   binary=library_access.safe(root,'local-qa/bin/zimdump')
   # Stable descriptor path avoids replacing the checked archive before extraction.
   archive='/proc/'+str(os.getpid())+'/fd/'+str(stream.fileno())
   idx=q['article'][0]
   meta=helper.run([binary,'list','--idx='+idx,archive],2,8000)
   if not re.search(r'mime-type:\s+text/(?:html|plain)',meta):raise ValueError('Not a text article')
   size=re.search(r'item size:\s+(\d+)',meta)
   if not size or int(size[1])>1000000:raise ValueError('Article exceeds bounded reader')
   raw=helper.run([binary,'show','--idx='+idx,archive],3,1000001)
   if len(raw.encode())>1000000 or not raw:raise ValueError('Article unavailable')
   body=('Local archive: '+name+'\nArticle '+idx+' (plain-text extraction; no images or active content)\n\n'+helper.clean(raw)).encode()
   stream.close();stream=io.BytesIO(body);kind='text/plain; charset=utf-8';filename='article.txt'
  elif u.query:raise ValueError('Unknown query')
  size=stream.seek(0,2);stream.seek(0);start=0;end=size-1;status=200
  value=handler.headers.get('Range')
  if value and not head:
   m=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
   if not m or not any(m.groups()):raise IndexError()
   if m[1]:start=int(m[1]);end=min(int(m[2]) if m[2] else end,end)
   else:start=max(0,size-int(m[2]))
   if start>=size or start>end:raise IndexError()
   status=206
  handler.send_response(status)
  handler.send_header('Content-Type',kind)
  handler.send_header('Content-Disposition','inline; filename="'+filename+'"')
  handler.send_header('Content-Length',str(end-start+1))
  handler.send_header('Accept-Ranges','bytes')
  if status==206:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  handler.send_header('X-Content-Type-Options','nosniff')
  handler.send_header('Content-Security-Policy',"sandbox; default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
  handler.send_header('Referrer-Policy','no-referrer')
  handler.send_header('Cache-Control','no-store')
  handler.end_headers()
  if not head:
   stream.seek(start);remaining=end-start+1
   while remaining:
    chunk=stream.read(min(65536,remaining))
    if not chunk:break
    handler.wfile.write(chunk);remaining-=len(chunk)
 except IndexError:
  handler.send_response(416);handler.send_header('Content-Range','bytes */'+str(size));handler.send_header('Content-Length','0');handler.end_headers()
 except (ValueError,OSError,UnicodeError):
  handler.send_error(404,'Document unavailable')
 finally:
  if stream is not None:stream.close()
 return True
