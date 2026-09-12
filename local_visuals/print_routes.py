# SPDX-License-Identifier: GPL-3.0-only
"""Print only a successful result selected in an authenticated user/chat scope."""
import json,re,uuid,time,os
from pathlib import Path
import fitz
from . import export
from .units import distance,imperial_text
from .print_route_formatter import render,validate
SELECTED={}
def scope(body):
 s=body.get('route_scope');return s if isinstance(s,str) and re.fullmatch('[a-f0-9]{64}',s) else None
def intent(q):
 return bool(re.fullmatch(r'\s*(?:(?:can|could|would) you\s+)?(?:please\s+)?(?:print\s+(?:(?:the|these|this|my|that)\s+)?(?:directions|route)|(?:make|create|give me|export)\s+(?:a\s+)?(?:printable\s+(?:directions|route)|(?:directions|route)\s+pdf))(?:\s+please)?[.!?]?\s*',q,re.I))
def clear(s):SELECTED.pop(s,None)
def dispatch(q,s):
 if not intent(q):return None
 item=SELECTED.get(s) if s else None
 if item and time.time()-item['time']>86400:clear(s);item=None
 answer=item['answer'] if item else 'No complete saved route is selected in this user/chat. Request directions in this conversation first, then ask to print them. No route was calculated.'
 return {'route':'route.print' if item else 'clarify','query':q,'direct':answer}
def save(s,d):
 if not s or not isinstance(d,dict) or d.get('status')!='ok' or not d.get('maneuvers') or not d.get('route_visual'):return ''
 try:
  name=d['route_visual']['files']['png'].removeprefix(export.BASE)
  with export.open_artifact(name) as f:assert f.read(8)==b'\x89PNG\r\n\x1a\n'
  maneuvers=[]
  for m in d['maneuvers']:
   match=re.search(r'\band go (\d+(?:\.\d+)? (?:mi|ft))\b',imperial_text(m['description']))
   if not match:raise ValueError('No source maneuver distance')
   maneuvers.append(dict(segment_index=m['segment_index'],instruction=re.sub(r'\s*\([^)]*\)','',m['turn']).strip(),distance_display=match[1],road=m['road'],original_turn=m['turn'],original_description=m['description']))
  trip=dict(status='ok',verified_source=True,start_label=d['places'][0]['name']+(' town center' if not d.get('sources') else ''),end_label=d['places'][-1]['name']+(' town center' if not d.get('sources') else ''),distance_display=distance(d['distance_m'],total=True),eta_display=f"{d['estimated_travel_s']/60:.1f} minutes",snapshot=str(d['source']['snapshot']),map_png=str(export.ART/name),maneuvers=maneuvers,source=d['source'],full_input=d.get('request',{}).get('full_input',''),endpoint_scope=d.get('endpoint_scope','Town centers snapped to car roads, not exact street addresses.'))
  validate(trip)
  if export.ART.is_symlink() or len(list(export.ART.glob('*.pdf')))>=100:raise ValueError('Storage bound')
  ident=uuid.uuid4().hex;target=export.ART/(ident+'.pdf');temporary=export.ART/(ident+'.pending')
  render(trip,temporary)
  with fitz.open(temporary) as pdf:
   assert len(pdf)>0 and all(tuple(p.rect)==(0,0,612,792) for p in pdf)
   txt='\n'.join(p.get_text() for p in pdf)
   assert all(m['distance_display'] in txt and m['instruction'] in txt for m in maneuvers)
   pdf[0].get_pixmap(matrix=fitz.Matrix(1,1)).save(export.ART/(ident+'.png'))
  os.replace(temporary,target)
  (export.ART/(ident+'.json')).write_text(json.dumps(trip,indent=2))
  answer=f"[Printable driving directions PDF]({export.BASE}{ident}.pdf) — open in a local PDF viewer to print. {trip['endpoint_scope']}"
  if len(SELECTED)>=128:SELECTED.pop(next(iter(SELECTED)))
  SELECTED[s]={'time':time.time(),'trip':trip,'answer':answer}
  return '\n\n'+answer
 except (OSError,ValueError,KeyError,TypeError,AssertionError,RuntimeError):
  clear(s);return '\n\nPrintable directions unavailable for this incomplete saved result; no substitute route was used.'
