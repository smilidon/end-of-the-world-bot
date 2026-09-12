# SPDX-License-Identifier: GPL-3.0-only
"""Minimal bounded subprocess and HTML helpers extracted from the existing local-qa/ask.py."""
import html.parser, os, pathlib, selectors, subprocess, time, types
class Text(html.parser.HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]; self.skip=0
 def handle_starttag(self,t,a):
  if t in ('script','style'): self.skip+=1
 def handle_endtag(self,t):
  if t in ('script','style'): self.skip=max(0,self.skip-1)
 def handle_data(self,d):
  if not self.skip:self.parts.append(d)

def clean(s):
 p=Text(); p.feed(s); return ' '.join(' '.join(p.parts).split())

def run(cmd,seconds=8,cap=2000000):
 p=subprocess.Popen([str(x) for x in cmd],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 out=bytearray(); sel=selectors.DefaultSelector(); sel.register(p.stdout,selectors.EVENT_READ); end=time.monotonic()+seconds
 try:
  while time.monotonic()<end and len(out)<cap:
   if not sel.select(min(.1,max(.001,end-time.monotonic()))):continue
   b=os.read(p.stdout.fileno(),min(65536,cap-len(out)))
   if not b:break
   out.extend(b)
  if p.poll() is None:p.terminate()
  p.wait(timeout=1)
 finally:
  if p.poll() is None:p.kill();p.wait()
  sel.close();p.stdout.close()
 return out.decode('utf-8','replace')

def for_root(root):
 return types.SimpleNamespace(HERE=root/'local-qa', run=run, clean=clean)
