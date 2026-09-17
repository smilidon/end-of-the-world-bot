# SPDX-License-Identifier: GPL-3.0-only
"""Optional local Ollama query adapted from the original bounded ask.py."""
import fcntl,json,time,urllib.request
from compact_context import INSTRUCTION as SYSTEM, envelope, fallback
def query(a):
 start=time.monotonic()
 if len(a.question)>400 or len(a.search or '')>160:raise ValueError('Question limited to 400 characters; search to 160')
 with open(HERE/'query.lock','a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('Another library query is active; no request submitted')
  sources=retrieve(a)
  sources=[dict(source, id='S'+str(i+1)) for i,source in enumerate(sources) if source.get('text')][:3]
  rt=time.monotonic()-start
  result={'question':a.question,'sources':sources,'retrieval_seconds':rt,'model':MODEL,'deadline_seconds':90,'model_called':False}
  if a.retrieve_only or not sources:
   result.update(answer='RETRIEVAL_ONLY' if sources else 'UNKNOWN',inference_seconds=0,wall_seconds=time.monotonic()-start);return result
  packed=envelope(a.question,sources,getattr(a,'profile','tiny'),getattr(a,'prompt_budget',None))
  if packed is None:
   result.update(fallback(sources,'compact prompt budget exceeded; no inference requested'),inference_seconds=0,wall_seconds=time.monotonic()-start);return result
  limits=packed['limits']
  result['compact_context']={k:packed[k] for k in ('profile','serialized_bytes','input_token_upper_bound','input_budget')}
  result['sources']=packed['selected']
  req={'model':MODEL,'messages':packed['messages'],'stream':False,'think':False,'keep_alive':0,'options':{'num_ctx':limits['context'],'num_gpu':a.num_gpu,'num_batch':128,'num_thread':a.threads,'num_predict':limits['output_tokens'],'temperature':0,'top_k':1,'top_p':1,'seed':42}}
  result['request']=req
  t=time.monotonic()
  # Hardcoded numeric loopback; proxies disabled, no redirects and no fallback.
  class NoRedirect(urllib.request.HTTPRedirectHandler):
   def redirect_request(self,*args):raise ValueError('Redirect forbidden')
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
  request=urllib.request.Request(a.ollama_url,json.dumps(req).encode(),{'Content-Type':'application/json'})
  with opener.open(request,timeout=max(1,87-(t-start))) as response:
   body=response.read(65537)
  if len(body)>65536:
   result.update(fallback(result['sources'],'model response exceeded safe size'),model_called=True);return result
  r=json.loads(body)
  result.update(answer=r.get('message',{}).get('content',''),inference_seconds=time.monotonic()-t,wall_seconds=time.monotonic()-start,input_tokens=r.get('prompt_eval_count'),output_tokens=r.get('eval_count'),done_reason=r.get('done_reason'),native_seconds={k:r.get(k,0)/1e9 for k in ('load_duration','prompt_eval_duration','eval_duration','total_duration')})
  result['output_chars']=len(result['answer']);result['output_words']=len(result['answer'].split())
  result['model_called']=True
  result['input_target_met']=isinstance(result['input_tokens'],int) and result['input_tokens']<=packed['input_budget']
  result['answer_status']='compact answer'
  if r.get('done_reason')=='length' or (r.get('eval_count') or 0)>=limits['output_tokens'] or len(result['answer'])>4000 or (isinstance(result['input_tokens'],int) and result['input_tokens']>packed['input_budget']):
   result.update(fallback(result['sources'],'model output/context limit reached; incomplete generated answer withheld'),model_called=True)
  return result
