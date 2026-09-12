# SPDX-License-Identifier: GPL-3.0-only
"""Full engine point geometry; bounded, offline, north-up geometry-only previews."""
import base64,hashlib,html,json,math,os,pathlib,subprocess,tempfile,time,signal
from local_visuals import artifact_config as export
from local_visuals.units import MILE,distance
R=6371008.8

def parse_geometry(raw,segments):
 groups=[]
 for line in raw.splitlines():
  if line.startswith('GEOMSEG\t'):
   _,n,road,a,b=line.split('\t');assert int(n)==len(groups)
   groups.append({'road_id':road,'start_index':int(a),'end_index':int(b),'points':[],'indices':[]})
  elif line.startswith('POINT\t'):
   _,n,i,lat,lon=line.split('\t');g=groups[int(n)];p=[float(lat),float(lon)]
   if not all(math.isfinite(v) for v in p) or not -85<p[0]<85 or not -180<=p[1]<=180:raise ValueError('Coordinate bounds')
   g['points'].append(p);g['indices'].append(int(i))
 if len(groups)!=len(segments) or not groups:raise ValueError('Geometry incomplete')
 for g,s in zip(groups,segments):
  a,b=g['start_index'],g['end_index'];step=1 if b>=a else -1
  if g['indices']!=list(range(a,b+step,step)) or str(int(g['road_id'])>>6)!=s['road_id']:raise ValueError('Geometry order mismatch')
 if sum(len(g['points']) for g in groups)>100000:raise ValueError('Geometry bound')
 return groups

def layout(d):
 groups=d['geometry'];points=[p for g in groups for p in g['points']]
 lat0=sum(p[0] for p in points)/len(points);lon0=sum(p[1] for p in points)/len(points)
 def project(p):return (R*math.radians(p[1]-lon0)*math.cos(math.radians(lat0)),R*math.radians(p[0]-lat0))
 xy=[project(p) for p in points];xs,ys=zip(*xy);bbox=[min(xs),min(ys),max(xs),max(ys)]
 spanx=max(1,bbox[2]-bbox[0]);spany=max(1,bbox[3]-bbox[1]);scale=min(760/spanx,650/spany)
 cx=(bbox[0]+bbox[2])/2;cy=(bbox[1]+bbox[3])/2
 def pixel(p):x,y=project(p);return [450+(x-cx)*scale,470-(y-cy)*scale]
 bar=max(v for v in [.01,.02,.05,.1,.2,.5,1,2,5,10,20,50,100] if v*MILE*scale<=210)
 return {'paths':[[pixel(p) for p in g['points']] for g in groups],'bbox_latlon':[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)],'projection':'local equirectangular, spherical R=6371008.8 m; scale at reference latitude','reference_latitude':lat0,'px_per_m':scale,'scale_miles':bar,'scale_px':bar*MILE*scale,'point_count':len(points),'snapped_start':points[0],'snapped_end':points[-1]}

def mercator31(p):
 lat,lon=p
 return [(lon+180)/360*2**31,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**31]

def native_layout(d):
 L=layout(d);points=[p for g in d['geometry'] for p in g['points']]
 xy=[mercator31(p) for p in points];xs,ys=zip(*xy)
 zoom=min(17,math.floor(math.log2(min(760/max(1,max(xs)-min(xs)),650/max(1,max(ys)-min(ys)))*2**23)))
 if zoom<6:raise ValueError('Native viewport exceeds supported bounds')
 step=2**(23-zoom);left=round((min(xs)+max(xs))/2-425*step);top=round((min(ys)+max(ys))/2-350*step)
 bounds=[left,left+850*step,top,top+700*step]
 if min(bounds)<0 or max(bounds)>=2**31:raise ValueError('Native viewport outside world')
 def pixel(p):x,y=mercator31(p);return [25+(x-left)/step,120+(y-top)/step]
 lat0=math.degrees(math.atan(math.sinh(math.pi*(1-2*(top+350*step)/2**31))))
 scale=2**31/step/(2*math.pi*R*math.cos(math.radians(lat0)))
 bar=max(v for v in [.01,.02,.05,.1,.2,.5,1,2,5,10,20,50,100] if v*MILE*scale<=210)
 L.update(paths=[[pixel(p) for p in g['points']] for g in d['geometry']],projection='Web Mercator, exact native 31-bit bounds',reference_latitude=lat0,px_per_m=scale,scale_miles=bar,scale_px=bar*MILE*scale,native_bounds31=bounds,zoom=zoom,step31=step)
 return L

def native_background(d,L):
 nav=pathlib.Path(d['source']['file']).parent.parent
 cp=str(nav/'tools/MapCreator/OsmAndMapCreator.jar')+os.pathsep+str(nav/'tools/MapCreator/lib/*')
 samples=[d['geometry'][0]['points'][0],d['geometry'][len(d['geometry'])//2]['points'][0],d['geometry'][-1]['points'][-1]]
 budget=min(25,max(.1,84-d.get('elapsed_s',0)))
 with tempfile.TemporaryDirectory(prefix='native-route-') as td:
  target=pathlib.Path(td)/'map.png'
  cmd=['java','-Deotwb.fonts='+os.environ.get('EOTWB_FONTS','fonts'),'-Djava.awt.headless=true','-Djava.io.tmpdir='+td,'-XX:ActiveProcessorCount=2','-Xmx512m','-cp',cp,str(pathlib.Path(__file__).with_name('NativeMap.java')),os.pathsep.join(s['file'] for s in d.get('sources',[d['source']])),str(target),*map(str,L['native_bounds31']),str(L['zoom']),*[str(v) for p in samples for v in p]]
  with tempfile.TemporaryFile() as log:
   proc=subprocess.Popen(cmd,cwd=td,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:proc.wait(timeout=budget)
   finally:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   log.seek(0);output=log.read(100000).decode('utf8','replace')
  if proc.returncode or not target.is_file():raise RuntimeError('Native renderer failed')
  from PIL import Image
  with Image.open(target) as im:
   if im.size!=(850,700):raise ValueError('Native dimensions mismatch')
   if len(im.convert('RGB').getcolors(850*700) or [])<20:raise ValueError('Empty native background')
  actual=[list(map(float,line.split('\t')[1:])) for line in output.splitlines() if line.startswith('SAMPLE\t')]
  assert len(actual)==3
  errors=[]
  for p,a in zip(samples,actual):
   x,y=mercator31(p);errors.append(max(abs(a[0]-(x-L['native_bounds31'][0])/L['step31']),abs(a[1]-(y-L['native_bounds31'][2])/L['step31'])))
  if max(errors)>.01:raise ValueError('Native alignment mismatch')
  L['native_sample_max_error_px']=max(errors);L['native_samples']=actual
  L['labels_registered']='Fonts are not registered' not in output
  return target.read_bytes()

def generate(d):
 import cairosvg
 export.ART.mkdir(parents=True,exist_ok=True)
 if export.ART.is_symlink():raise ValueError('Invalid storage')
 inputs={'native_source_sha256':hashlib.sha256(pathlib.Path(__file__).with_name('NativeMap.java').read_bytes()).hexdigest(),'geometry':d['geometry'],'places':d['places'],'source':d['source'],'distance_m':d['distance_m'],'renderer_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'units_sha256':hashlib.sha256(pathlib.Path(__file__).with_name('units.py').read_bytes()).hexdigest()}
 source=pathlib.Path(d['source']['file']);st=source.stat();inputs['source_stat']=[st.st_size,st.st_mtime_ns];inputs['engine_source_sha256']=hashlib.sha256(pathlib.Path(__file__).with_name('RouteGeometry.java').read_bytes()).hexdigest()
 inputs['native_runtime']=[(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted((source.parent.parent/'tools/MapCreator/lib').glob('*.jar'))];inputs['fonts']=[(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(pathlib.Path(os.environ.get('EOTWB_FONTS', 'fonts')).glob('*.ttf'))]
 inputs['sources']=[dict(s,stat=[pathlib.Path(s['file']).stat().st_size,pathlib.Path(s['file']).stat().st_mtime_ns]) for s in d.get('sources',[d['source']])]
 inputs['fuel']=d.get('fuel');inputs['endpoint_scope']=d.get('endpoint_scope');inputs['multi_exporter_hash']=hashlib.sha256(pathlib.Path(__file__).parent.parent.joinpath('MultiRouteGeometry.java').read_bytes()).hexdigest() if d.get('sources') else None
 digest=hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest();ident=digest[:32]
 meta=export.ART/(ident+'.json')
 if meta.is_file() and not meta.is_symlink() and all((export.ART/(ident+'.'+e)).is_file() and not (export.ART/(ident+'.'+e)).is_symlink() for e in export.FORMATS):return json.loads(meta.read_text())
 if len(list(export.ART.glob('*.pdf')))>=100:raise ValueError('Export storage full')
 background=None;failure=None
 try:
  L=native_layout(d);background=native_background(d,L)
 except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired,AssertionError) as e:
  L=layout(d);failure=type(e).__name__
 esc=lambda s:html.escape(str(s),quote=True)
 svg=['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="900" height="1020" viewBox="0 0 900 1020">','<rect width="900" height="1020" fill="#f5f7f7"/><g font-family="sans-serif" fill="#183541">',f'<text x="35" y="40" font-size="16" textLength="825" lengthAdjust="spacingAndGlyphs">{esc(d["places"][0]["name"])} to {esc(d["places"][1]["name"])}</text>',f'<text x="35" y="72" font-size="18">{distance(d["distance_m"],total=True)} · Actual offline OsmAnd route</text>',f'<text x="35" y="101" font-size="16">{"Local OBF roads, water and land · exact route overlay" if background else "GEOMETRY ONLY — native basemap unavailable; no roads shown"}</text>','<rect x="25" y="120" width="850" height="700" fill="#e7eeee"/>']
 if background:svg.append('<image x="25" y="120" width="850" height="700" xlink:href="data:image/png;base64,'+base64.b64encode(background).decode()+'"/>')
 for path in L['paths']:
  svg.append('<polyline points="'+' '.join(f'{x:.3f},{y:.3f}' for x,y in path)+'" fill="none" stroke="#0064d8" stroke-opacity="0.8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
 for station in d.get('fuel',{}).get('stops',[]):
  if 'latitude' not in station:continue
  if background:
   sx,sy=mercator31([station['latitude'],station['longitude']]);sx=25+(sx-L['native_bounds31'][0])/L['step31'];sy=120+(sy-L['native_bounds31'][2])/L['step31']
   if 30<sx<870 and 125<sy<815:svg.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="8" fill="#e19400" stroke="white"/><text x="{sx+10:.3f}" y="{sy:.3f}" font-size="14">Fuel ~{station["target_miles"]:g} mi</text>')
 for p,label,color in [(L['paths'][0][0],'START'+(' ~' if 'approximate' in d['places'][0].get('precision','') else ''),'#17734a'),(L['paths'][-1][-1],'END'+(' ~' if 'approximate' in d['places'][1].get('precision','') else ''),'#a43d36')]:
  x,y=p;svg.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{color}" stroke="white" stroke-width="2"/><text x="{min(max(x+12,45),660)}" y="{y-14}" font-size="17">{esc(label)}</text>')
 svg += ['<path d="M825 205V150M825 150L816 168M825 150L834 168" stroke="#183541" stroke-width="3" fill="none"/><text x="818" y="141" font-size="18">N</text>',f'<path d="M50 855v-8m0 4h{L["scale_px"]:.6f}m0 -4v8" stroke="#183541" stroke-width="3" fill="none"/><text x="50" y="882" font-size="17">{L["scale_miles"]:g} mi (at {L["reference_latitude"]:.2f}° N)</text>',f'<text x="35" y="917" font-size="14">Engine-snapped endpoints · {L["point_count"]} original segment points · north up</text>',f'<text x="35" y="942" font-size="13">Local OBF snapshot {esc(str(d["source"]["snapshot"])[:75])} · {esc(L["projection"])}</text>',f'<text x="35" y="970" font-size="13" textLength="825" lengthAdjust="spacingAndGlyphs">{esc(d.get("endpoint_scope","Settlement centers, not exact addresses. No live traffic or road-open assurance."))}</text>',f'<text x="35" y="995" font-size="12" textLength="825" lengthAdjust="spacingAndGlyphs">{esc(d.get("request",{}).get("full_input",""))}</text>','</g></svg>']
 raw=''.join(svg).encode();(export.ART/(ident+'.svg')).write_bytes(raw)
 cairosvg.svg2png(bytestring=raw,write_to=str(export.ART/(ident+'.png')))
 cairosvg.svg2pdf(bytestring=raw,write_to=str(export.ART/(ident+'.pdf')))
 data={'id':ident,'cache_sha256':digest,'layout':L,'source':d['source'],'files':{e:export.BASE+ident+'.'+e for e in export.FORMATS},'kind':'native local OBF basemap with exact route' if background else 'actual route geometry only; no basemap','native_background':bool(background),'native_failure':failure}
 if background:meta.write_text(json.dumps(data,indent=2))
 return data

def answer(d):
 try:m=generate(d)
 except (OSError,ValueError,RuntimeError):return '\n\nRoute preview unavailable; engine directions above remain valid.'
 d['route_visual']=m;u=m['files']
 label='Offline route map — local roads, water and land.' if m.get('native_background') else 'Actual route geometry only — native basemap unavailable.'
 return f'\n\n**{label}**\n\n[Route PDF]({u["pdf"]}) · [Route SVG]({u["svg"]}) · [Route PNG]({u["png"]})\n\n![{label}]({u["png"]})'
