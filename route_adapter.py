# SPDX-License-Identifier: GPL-3.0-only
"""Existing named-route presentation bridge; no alternate routing engine."""
from local_visuals.units import distance,imperial_text
import named_routing as named
def execute(r,nav):
 if r.get("action")=="trip":
  import multistate_routing as multi
  return multi.execute(r,nav)
 try:d=named.execute(r,nav)
 except (OSError,ValueError,KeyError):
  return [],{'status':'error'},'The local map or routing runtime is unavailable or failed validation; no directions were produced.'
 source=d.get('source',{})
 sources=[{'id':'G1','source':str(source.get('file',''))+'; snapshot '+str(source.get('snapshot','unknown')),'text':d.get('scope','')}] if source else []
 if d['status']!='ok':
  if d['status']=='clarification':
   details=[]
   for p in d.get('places',[]):
    if p.get('status')=='clarification':
     details.append(p['query']+': '+p['reason'])
     details.extend(str(c['id'])+': '+c['name']+' ('+str(c['latitude'])+', '+str(c['longitude'])+')' for c in p.get('candidates',[]))
   return sources,d,'No route calculated. '+'; '.join(details)+'. Please refine the settlement name or map. Candidate-ID selection is not yet supported.'
  return sources,d,'The offline engine could not complete this request within its limits; no directions were produced.'
 places=d['places']
 lines=['**Offline Michigan '+('place lookup' if r.get('action')=='lookup' else 'driving directions')+'**']
 lines.extend(p['name']+' town center: '+str(p['latitude'])+', '+str(p['longitude']) for p in places)
 if 'distance_m' in d:
  lines.append(f"{distance(d['distance_m'],total=True)}; estimated driving time {d['estimated_travel_s']/60:.1f} minutes.")
  lines.append('Engine maneuvers (segment distances are rounded; lane/mute flags retained):')
  for m in d['maneuvers']:
   lines.append(str(m['segment_index'])+'. '+imperial_text(m['description'] or m['turn'])+(' — '+m['road'] if m['road'] else '')+' [turn: '+str(m['turn'])+']')
 lines.append('Settlement centers snapped to car roads, not exact addresses. No live traffic or assurance that roads are open.')
 lines.append('Source: local OsmAnd OBF; snapshot '+str(source['snapshot'])+' [G1]. Integrity: verified download/ZIP CRC receipt and current size; no fresh full-map hash.')
 from local_visuals.route_map import answer as route_visual_answer
 return sources,d,'\n\n'.join(lines)+(route_visual_answer(d) if d.get('geometry') else '')
