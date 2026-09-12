# SPDX-License-Identifier: GPL-3.0-only
"""Real Pipe -> localhost adapter -> real retrieval -> explicitly fake Ollama."""
import asyncio,json,tempfile,threading,unittest,urllib.request
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from unittest.mock import patch
import bot,http_adapter,openwebui_pipe
from local_visuals import print_routes

class Chat(unittest.TestCase):
 def test_real_pipe_retrieval(self):
  seen=[]
  class FakeOllama(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_POST(self):
    seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
    out=json.dumps({'message':{'content':'SYNTHETIC fake inference: blue cabinet [S1].'},'prompt_eval_count':1200,'eval_count':12}).encode()
    self.send_response(200);self.send_header('Content-Length',str(len(out)));self.end_headers();self.wfile.write(out)
  with tempfile.TemporaryDirectory() as td, HTTPServer(('127.0.0.1',0),FakeOllama) as model:
   root=Path(td);(root/'guides').mkdir();(root/'guides/beacon.txt').write_text('SYNTHETIC reference: the amber beacon batteries belong in the blue cabinet. This is a test fixture only.')
   bot.build(root)
   app=http_adapter.Application(root,'synthetic-fake-model','http://127.0.0.1:'+str(model.server_port)+'/api/chat')
   with http_adapter.make_server(app,0) as server:
    threads=[threading.Thread(target=x.serve_forever,daemon=True) for x in (model,server)]
    for t in threads:t.start()
    try:
     pipe=openwebui_pipe.Pipe();pipe.url='http://127.0.0.1:'+str(server.server_port)+'/trial'
     output=asyncio.run(pipe.pipe({'messages':[{'role':'user','content':'Where are the beacon batteries?'}]}, {'id':'synthetic-user'}, {'chat_id':'synthetic-chat'}))
     self.assertIn('blue cabinet',output);self.assertIn('[S1] guides/beacon.txt',output)
     self.assertIn('blue cabinet',seen[0]['messages'][1]['content']);self.assertNotIn('synthetic-user',json.dumps(seen))
     output=asyncio.run(pipe.pipe({'messages':[{'role':'user','content':[{'type':'image_url','image_url':'fixture'}]}]}))
     self.assertIn('text_only',output)
    finally:
     server.shutdown();model.shutdown()
     for t in threads:t.join()
 def test_scope_and_failed_route_invalidation(self):
  import time
  a='a'*64;b='b'*64
  print_routes.SELECTED.clear()
  print_routes.SELECTED[a]={'time':time.time(),'answer':'SYNTHETIC verified directions'}
  self.assertEqual(print_routes.dispatch('print directions',a)['route'],'route.print')
  for scope in (b,None):self.assertEqual(print_routes.dispatch('print directions',scope)['route'],'clarify')
  self.assertIsNone(print_routes.scope({'route_scope':'invalid'}))
  with tempfile.TemporaryDirectory() as td:
   app=http_adapter.Application(Path(td),'fake','http://127.0.0.1:11434/api/chat')
   app.run({'route_scope':a,'messages':[{'role':'user','content':'directions from Alpha to Beta'}]})
  self.assertNotIn(a,print_routes.SELECTED)
  self.assertEqual(print_routes.save(b,{'status':'error'}),'');self.assertNotIn(b,print_routes.SELECTED)
