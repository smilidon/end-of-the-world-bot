"""
title: Emergency Offline Bot
version: 0.2.0
required_open_webui_version: 0.11.3
"""
import os
from urllib.parse import urlsplit
import asyncio, hashlib, json, urllib.request, urllib.error, re
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('Redirect forbidden')
class Pipe:
    def __init__(self):
        self.name = 'Emergency Offline Bot'
        self.url = os.environ.get('EOTWB_ADAPTER_URL', 'http://127.0.0.1:8769/trial')
        u = urlsplit(self.url)
        if u.scheme != 'http' or u.hostname != '127.0.0.1' or u.path != '/trial' or u.username or u.password or u.query or u.fragment:
            raise ValueError('Adapter must use numeric HTTP loopback /trial')
    async def pipe(self, body: dict, __user__: dict = None, __metadata__: dict = None) -> str:
        def call():
            # Only a hashed authenticated user/chat scope; no credentials or personal profile forwarded.
            messages = [{'role':m['role'],'content':m.get('content')} for m in body.get('messages',[]) if m.get('role') in ('user','assistant')]
            metadata = __metadata__ or body.get('metadata', {})
            uid = (__user__ or {}).get('id')
            cid = metadata.get('chat_id')
            scope = hashlib.sha256(json.dumps([uid,cid]).encode()).hexdigest() if isinstance(uid,str) and uid and isinstance(cid,str) and cid else None
            data = json.dumps({'messages':messages, 'route_scope':scope}).encode()
            if len(data)>180000:
                raise ValueError('Trial history bound exceeded')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            req = urllib.request.Request(self.url,data,{'Content-Type':'application/json'})
            try:
                with opener.open(req,timeout=90) as response:
                    result=json.load(response)
            except urllib.error.HTTPError as exc:
                try:
                    raw=exc.read(2048)
                finally:
                    exc.close()
                try: detail=json.loads(raw)
                except (ValueError,UnicodeError): detail={}
                code=detail.get('error','unknown') if isinstance(detail,dict) else 'unknown'
                known={'messages_shape','text_only','text_bound','fixture_only','input_budget','memory_bound','unsupported_tool','busy','timeout','internal'}
                if code not in known: code='unknown'
                rid=detail.get('request_id','') if isinstance(detail,dict) else ''
                if not isinstance(rid,str) or not re.fullmatch('[a-f0-9]{12}',rid): rid='unavailable'
                return 'Local adapter HTTP '+str(exc.code)+' ['+code+'; '+rid+']. Check the sanitized adapter log.'
            if result.get('error'):
                return result['answer']
            sources=result['context']['memory']+result['context']['summary']+result['context']['tool_results']
            citations='\n'.join('['+s['id']+'] '+str(s['source']) for s in sources)
            return result['answer']+'\n\n'+citations+'\n\nTrial: '+str(result['prompt_tokens'])+' input tokens; '+str(result['seconds'])+'s. Deterministic tool selection.'
        return await asyncio.to_thread(call)
