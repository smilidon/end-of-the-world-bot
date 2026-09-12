# SPDX-License-Identifier: GPL-3.0-only
"""Bounded offline pin routes, actual OBF coverage and fuel candidates. No network."""
import bisect,hashlib,json,math,os,pathlib,re,resource,signal,subprocess,tempfile,time
import named_routing as named
from local_visuals import route_map
BASE=pathlib.Path(__file__).resolve().parent
REGIONS=('michigan','ohio','indiana','illinois','missouri')
MILE=1609.344

def run(nav,source,args,seconds=55):
 if seconds<=0:raise TimeoutError('local deadline')
 cmd=['java','-XX:ActiveProcessorCount=2','-Xmx512m','-cp',str(nav/'tools/MapCreator/OsmAndMapCreator.jar')+os.pathsep+str(nav/'tools/MapCreator/lib/*'),str(BASE/source),*map(str,args)]
 with tempfile.TemporaryDirectory(prefix='corridor-') as td,tempfile.TemporaryFile() as out:
  p=subprocess.Popen(cmd,cwd=td,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_FSIZE,(32000000,32000000)))
  try:p.wait(timeout=seconds)
  finally:
   if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
  out.seek(0);raw=out.read(16000000).decode('utf8','replace')
 if p.returncode:raise RuntimeError('offline engine exit '+str(p.returncode))
 return raw

def catalog(nav):
 entries=[]
 for region in REGIONS:
  try:e=named.select_region(region,nav)
  except ValueError:continue
  f=nav/e['obf_file']
  if f.is_symlink() or not f.resolve().is_relative_to((nav/'maps').resolve()) or f.stat().st_size!=e['unpacked_bytes']:raise ValueError('map validation')
  entries.append({'region':region,'file':str(f),'snapshot':e['version'],'recorded_sha256':e['obf_sha256'],'stat':[f.stat().st_size,f.stat().st_mtime_ns]})
 if not entries or sum(e['stat'][0] for e in entries)>4400000000:raise ValueError('map byte bound')
 key=hashlib.sha256(json.dumps(entries,sort_keys=True).encode()+ (BASE/'CorridorProbe.java').read_bytes()).hexdigest()
 cache_dir=pathlib.Path(os.environ.get('EOTWB_CACHE', 'runtime/cache')).resolve();cache_dir.mkdir(parents=True,exist_ok=True)
 cache=cache_dir/('coverage-'+key+'.json')
 if cache.is_file() and not cache.is_symlink():return json.loads(cache.read_text())
 raw=run(nav,'CorridorProbe.java',[os.pathsep.join(e['file'] for e in entries)],15)
 for e in entries:
  e['bounds31']=[list(map(int,l.split('\t')[2:])) for l in raw.splitlines() if l.startswith('COVER\t'+pathlib.Path(e['file']).name+'\t')]
  if not e['bounds31']:raise ValueError('missing actual routing coverage')
 cache.write_text(json.dumps(entries,indent=2));return entries

def select(nav,pins):
 entries=catalog(nav);xy=[route_map.mercator31(p) for p in pins]
 # Conservative actual routing-index envelopes, not administrative polygons or coverage guarantees.
 pad=2**31/360*1.0
 corridor=[min(p[0] for p in xy)-pad,max(p[0] for p in xy)+pad,min(p[1] for p in xy)-pad,max(p[1] for p in xy)+pad]
 overlap=lambda a,b:a[0]<=b[1] and b[0]<=a[1] and a[2]<=b[3] and b[2]<=a[3]
 selected=[e for e in entries if any(overlap(b,corridor) for b in e['bounds31'])]
 if not all(any(any(b[0]<=x<=b[1] and b[2]<=y<=b[3] for b in e['bounds31']) for e in selected) for x,y in xy):raise ValueError('pins outside installed coverage envelopes')
 # Keep only the adjacent envelope component containing the origin.
 def contains(e,p):return any(b[0]<=p[0]<=b[1] and b[2]<=p[1]<=b[3] for b in e['bounds31'])
 connected=[e for e in selected if contains(e,xy[0])]
 for _ in selected:
  connected += [e for e in selected if e not in connected and any(overlap(a,b) for old in connected for a in old['bounds31'] for b in e['bounds31'])]
 if not any(contains(e,xy[1]) for e in connected):raise ValueError('no adjacent installed corridor')
 return connected

def hav(a,b):
 x,y=map(math.radians,a);u,v=map(math.radians,b)
 return 2*6371008.8*math.asin(min(1,math.sqrt(math.sin((u-x)/2)**2+math.cos(x)*math.cos(u)*math.sin((v-y)/2)**2)))

def geometry(nav,entries,pins,seconds):
 raw=run(nav,'MultiRouteGeometry.java',[os.pathsep.join(e['file'] for e in entries),*pins[0],*pins[1]],seconds)
 segments=named.parse_engine(raw);groups=route_map.parse_geometry(raw,segments)
 if any(hav(a['points'][-1],b['points'][0])>3 for a,b in zip(groups,groups[1:])):raise ValueError('discontinuous route')
 totals=re.findall(r'complete_distance=([\d.]+), complete_time=([\d.]+)',raw)
 if not totals:raise ValueError('missing totals')
 return {'geometry':groups,'segments':segments,'distance_m':float(totals[-1][0]),'estimated_travel_s':float(totals[-1][1])}

def fuel(nav,d,interval,deadline):
 pts=[p for g in d['geometry'] for p in g['points']];cum=[0.0]
 for a,b in zip(pts,pts[1:]):cum.append(cum[-1]+hav(a,b))
 ratio=cum[-1]/d['distance_m']
 def at(m):
  target=min(cum[-1],max(0,m*ratio));i=max(1,min(len(pts)-1,bisect.bisect_left(cum,target)));frac=(target-cum[i-1])/max(.000001,cum[i]-cum[i-1]);return [pts[i-1][j]+frac*(pts[i][j]-pts[i-1][j]) for j in (0,1)]
 marks=[interval*i for i in range(1,min(7,math.ceil(d['distance_m']/interval))) if interval*i<d['distance_m']]
 if not marks:return {'status':'no_interval_mark','interval_miles':interval/MILE,'stops':[],'note':'Route shorter than the requested interval; no intermediate target.'}
 raw=run(nav,'CorridorProbe.java',[os.pathsep.join(e['file'] for e in d['sources']),*[v for m in marks for v in at(m)]],min(12,deadline-time.monotonic()))
 candidates=[]
 for line in raw.splitlines():
  if not line.startswith('FUEL\t'):continue
  _,idx,source,oid,lat,lon,name,private=line.split('\t');p=[float(lat),float(lon)];i=int(idx)
  if private=='true' or hav(p,at(marks[i]))>5000:continue
  candidates.append({'mark_index':i,'source':source,'obf_id':oid,'latitude':p[0],'longitude':p[1],'name':name or 'Unnamed fuel POI','target_miles':marks[i]/MILE,'mark_offset_m':hav(p,at(marks[i])),'access_status':'unchecked','services':'unknown','open_status':'unknown','type':'amenity=fuel'})
 stops=[];seen=set()
 for i,m in enumerate(marks):
  choices=sorted((p for p in candidates if p['mark_index']==i),key=lambda p:p['mark_offset_m'])
  chosen=next((p for p in choices if p['obf_id'] not in seen and all(hav([p['latitude'],p['longitude']],[s['latitude'],s['longitude']])>150 for s in stops if 'latitude' in s)),None)
  if not chosen:stops.append({'target_miles':m/MILE,'access_status':'no_candidate_within_5km'});continue
  seen.add(chosen['obf_id']);stops.append(chosen)
  if deadline-time.monotonic()<17:continue
  station=[chosen['latitude'],chosen['longitude']];before=at(m-MILE);after=at(m+MILE)
  try:
   outbound=geometry(nav,d['sources'],[before,station],min(7,deadline-time.monotonic()))
   inbound=geometry(nav,d['sources'],[station,after],min(7,deadline-time.monotonic()))
   snap=max(hav(station,outbound['geometry'][-1]['points'][-1]),hav(station,inbound['geometry'][0]['points'][0]))
   chosen.update(access_status='road_snap_checked_not_driveway',outbound_m=outbound['distance_m'],inbound_m=inbound['distance_m'],baseline_route_m=2*MILE,detour_m=outbound['distance_m']+inbound['distance_m']-2*MILE,station_road_snap_m=snap,access_geometry={'outbound':outbound['geometry'],'inbound':inbound['geometry']})
   if snap>100:chosen['access_status']='road_snap_too_far_unverified'
  except (RuntimeError,ValueError,OSError,subprocess.TimeoutExpired):chosen['access_status']='access_routing_failed_or_timed_out'
 return {'status':'sampled','interval_miles':interval/MILE,'search_radius_m':5000,'geometry_to_engine_distance_ratio':ratio,'candidate_count':len(candidates),'stops':stops,'truncated':d['distance_m']/interval>7}

def execute(r,nav):
 begin=time.monotonic();prior=r.get('_lookup_elapsed_s',0);budget=max(1,82-prior);pins=r['pins']
 if len(pins)!=2 or not all(len(p)==2 and all(math.isfinite(v) for v in p) and -85<p[0]<85 and -180<=p[1]<=180 for p in pins):raise ValueError('invalid pins')
 entries=select(nav,pins);d=geometry(nav,entries,pins,min(55,begin+budget-20-time.monotonic()))
 d.update(status='ok',sources=entries,source={**entries[0],'snapshot':', '.join(e['region']+' '+str(e['snapshot']) for e in entries)},places=[{'name':'Start pin','latitude':pins[0][0],'longitude':pins[0][1]},{'name':'End pin','latitude':pins[1][0],'longitude':pins[1][1]}],endpoint_scope='Explicit pins / exact building records snapped to car roads; not verified driveways.',request=r)
 d['maneuvers']=[dict(segment_index=i+1,**s) for i,s in enumerate(d['segments']) if s['turn']]
 for i,place in enumerate(d['places']):
  place['name']=r['endpoints'][i]['raw'];place['precision']=r.get('endpoint_precision',['explicit pin','explicit pin'])[i]
 d['endpoint_scope']='START: '+d['places'][0]['precision']+'; END: '+d['places'][1]['precision']+'. Snapped to car roads.'
 if r.get('fuel_requested'):
  f=r.get('fuel_interval') or {'value':300,'unit':'miles'};interval=f['value']*(1000 if f['unit'].lower().startswith('k') else MILE)
  if not 50*MILE<=interval<=1000*MILE:raise ValueError('fuel interval supported: 50–1000 miles')
  try:d['fuel']=fuel(nav,d,interval,begin+budget-17)
  except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired):d['fuel']={'status':'fuel_search_failed_or_timed_out','interval_miles':interval/MILE,'stops':[]}
 d['elapsed_s']=time.monotonic()-begin+prior
 return d

def answer(d):
 lines=['**Offline driving directions**',d['request'].get('full_input',''), 'From '+d['places'][0]['name']+' to '+d['places'][1]['name'],f"{d['distance_m']/MILE:.2f} mi; estimated driving time {d['estimated_travel_s']/3600:.2f} hours.",d['endpoint_scope'],'Local routing-index corridor: '+', '.join(e['region'].title() for e in d['sources'])+'. Bounds are conservative envelopes, not a guarantee of continuous road coverage.']
 f=d.get('fuel')
 if f:
  lines.append(f"Fuel targets approximately every {f['interval_miles']:g} miles; {f['status']}. Services and opening status unknown.")
  for p in f['stops']:
   if 'latitude' not in p:lines.append(f"At {p['target_miles']:g} mi: no station found within the bounded search.");continue
   detail=f"At about {p['target_miles']:g} mi: {p['name']} ({p['latitude']:.6f}, {p['longitude']:.6f}); source {p['source']}, OBF ID {p['obf_id']}; {p['access_status']}."
   if 'detour_m' in p:detail+=f" Routed added distance {p['detour_m']/MILE:.2f} mi; station-to-road snap {p['station_road_snap_m']/0.3048:.0f} ft. Road access only, not verified entrance."
   lines.append(detail)
  if f.get('truncated'):lines.append('Fuel search capped at six interval marks; later stops not searched.')
 lines.append('No live traffic, fuel stock, or road-open assurance. Sources: installed OBF snapshots with prior download/CRC receipts and current size/mtime checks, not fresh full-map hashes.')
 return '\n\n'.join(lines)+route_map.answer(d)
