# SPDX-License-Identifier: GPL-3.0-only
"""Original bounded artifact reader/server; illustrated Guide generation not ported."""
import os,re,stat
from urllib.parse import urlsplit
from .artifact_config import ART,BASE
FORMATS={"pdf":"application/pdf","png":"image/png","svg":"image/svg+xml"}
def open_artifact(name):
 if not re.fullmatch(r'[a-f0-9]{32}\.(pdf|png|svg)',name):raise ValueError('Unavailable')
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in ART.parts[1:]:
   new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=new
  out=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
 finally:os.close(fd)
 if not stat.S_ISREG(os.fstat(out).st_mode):os.close(out);raise ValueError('Unavailable')
 return os.fdopen(out,'rb')

def serve(handler,head=False):
 if not handler.path.startswith('/artifacts/'):return False
 try:
  if handler.headers.get_all('Host')!=['127.0.0.1:'+str(handler.server.server_port)]:handler.send_error(403);return True
  parsed=urlsplit(handler.path)
  if parsed.query or parsed.fragment:raise ValueError('No query')
  name=parsed.path.removeprefix('/artifacts/')
  with open_artifact(name) as f:
   handler.send_response(200);handler.send_header('Content-Type',FORMATS[name.rsplit('.',1)[1]])
   handler.send_header('Content-Length',str(os.fstat(f.fileno()).st_size));handler.send_header('Content-Disposition','inline; filename="'+name+'"')
   handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Cache-Control','no-store');handler.send_header('Referrer-Policy','no-referrer')
   handler.send_header('Content-Security-Policy',"sandbox; default-src 'none'; frame-ancestors 'none'");handler.end_headers()
   if not head:
    while chunk:=f.read(65536):handler.wfile.write(chunk)
 except (OSError,ValueError):handler.send_error(404)
 return True
