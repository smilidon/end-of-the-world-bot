# SPDX-License-Identifier: GPL-3.0-only
"""Isolated offline settlement-center routing. No network or model dependency."""
import argparse,json,os,pathlib,re,signal,subprocess,tempfile,time,hashlib,resource
BASE=pathlib.Path(__file__).resolve().parent
DEFAULT_NAV=pathlib.Path(os.environ.get('EOTWB_NAV', 'library/navigation')).resolve()
def normalize(s): return re.sub(r'[^\w]+',' ',s.casefold()).strip()
def maps(nav):
    result=[]
    for e in json.loads((nav/'manifest.json').read_text())['items']:
        if e.get('status')!='verified_download' or not e.get('zip_crc_verified') or not e.get('obf_file'): continue
        name=pathlib.Path(e['obf_file']).stem
        region=re.sub(r'_(?:northamerica|centralamerica)_\d+$','',name,flags=re.I)
        region=re.sub(r'^Us_','',region,flags=re.I).replace('_',' ')
        result.append((normalize(region),e))
    return result

def select_region(region,nav):
    found=[e for r,e in maps(nav) if normalize(region)==r or normalize(region)==normalize(pathlib.Path(e['obf_file']).name)]
    if len(found)!=1: raise ValueError('Region unavailable or ambiguous: '+region)
    return found[0]

def parse_request(text,nav=DEFAULT_NAV,pending=None):
    """Pending is structured per-conversation state, not arbitrary old assistant prose."""
    known=[r for r,e in maps(nav)]
    # State abbreviations are geographic only inside explicit map intent/pending slots.
    geographic = pending or re.search(r'\b(map|directions|route|drive|driving|navigate)\b|where is|look up|how do i get',text,re.I)
    if geographic:
        text=re.sub(r'(?<=[a-z])MI\b', ' Michigan', text)
        text=re.sub(r'\bmi\b\.?|\bm\.i\.(?=\W|$)', 'Michigan', text, flags=re.I)
    text=text.strip().rstrip('?.!').strip()
    if pending and pending.get('awaiting')=='region':
        if normalize(text) in known:
            return {**pending,'region':normalize(text),'awaiting':None}
    endpoint_reply = bool(pending and pending.get('awaiting')=='endpoints')
    if not endpoint_reply and not re.search(r'\b(directions|route|drive|driving|navigate)\b|how do i get',text,re.I):
        m=re.search(r'(?:where is|look up(?: the town of)?|find)\s+(.+?)[?.!]*$',text,re.I)
        if m:
            regions=[r for r in known if re.search(r'(?<!\w)'+re.escape(r)+r'(?!\w)',normalize(text))]
            region=regions[0] if len(regions)==1 else None
            query=m[1].strip()
            if region:query=re.sub(r'(?:,?\s+|\s+in\s+)'+re.escape(region)+r'\s*$','',query,flags=re.I)
            return {'action':'lookup','query':query,'region':region,'awaiting':None if region else 'region'}
        if pending and pending.get('awaiting')=='region' and len(text.split())<=3:
            return {**pending,'message':'That region is not a unique completed local map; specify an available region.'}
        return None
    m=re.search(r'\bfrom\s+(.+?)\s+to\s+(.+?)[?.!]*$',text,re.I)
    if not m:m=re.search(r'\bbetween\s+(.+?)\s+and\s+(.+?)[?.!]*$',text,re.I)
    if not m and endpoint_reply:
        m=re.fullmatch(r"([\w .,'’-]+?)\s+(?:and|to)\s+([\w .,'’-]+)",text,re.I)
    if not m:
        if endpoint_reply:return None
        return {'awaiting':'endpoints','message':'Which origin and destination settlements?'}
    regions=[r for r in known if re.search(r'(?<!\w)'+re.escape(r)+r'(?!\w)',normalize(text))]
    region=regions[0] if len(regions)==1 else None
    def clean(s):
        s=s.strip(' ,.!?')
        if region:s=re.sub(r'(?:[,\s]+)'+re.escape(region)+r'\s*$','',s,flags=re.I)
        return s.strip(' ,')
    return {'origin':clean(m[1]),'destination':clean(m[2]),'region':region,'profile':'car','awaiting':None if region else 'region','scope':'settlement centers, not exact addresses'}

def parse_engine(raw):
    blocks=re.findall(r'<test\s+(.*?)</test>',raw,re.S)
    detailed=[b for b in blocks if 'route_base="false"' in b.split('>',1)[0]]
    if not detailed:raise RuntimeError('No final detailed route block')
    block=detailed[-1]
    segments=[]
    for line in re.findall(r'<segment\s+([^\n]+)',block):
        attrs=dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"',line))
        segments.append({'road_id':attrs['id'],'road':attrs.get('name',''), 'distance_m_rounded':float(attrs['distance']), 'turn':attrs.get('turn'), 'description':attrs.get('description','')})
    count=re.findall(r'Route is (\d+) segments',raw)
    if not count or len(segments)!=int(count[-1]):raise RuntimeError('Incomplete final segment output')
    return segments

def choose(candidates,query):
    if len(candidates)!=1:
        return {'status':'clarification','query':query,'reason':'no exact settlement match' if not candidates else 'ambiguous settlement name','candidates':candidates}
    return candidates[0]

def route(origin,destination,region,nav=DEFAULT_NAV,deadline_s=80,lookup_only=False):
    begin=time.monotonic(); e=select_region(region,nav); obf=nav/e['obf_file']
    if not obf.resolve().is_relative_to((nav/'maps').resolve()):raise ValueError('Map outside catalog map directory')
    if obf.stat().st_size!=e['unpacked_bytes'] or obf.stat().st_size>2*1024**3:raise ValueError('Map size mismatch or exceeds 2 GiB budget')
    if any(not x.strip() or len(x)>120 for x in (origin,destination)):raise ValueError('Settlement names must be 1–120 characters')
    java=['java','-Djava.awt.headless=true','-XX:ActiveProcessorCount=2','-Xmx768m','-cp',str(nav/'tools/MapCreator/OsmAndMapCreator.jar')+os.pathsep+str(nav/'tools/MapCreator/lib/*')]
    evidence={'status':'error','source':{'file':str(obf),'url':e['url'],'snapshot':e['version'],'recorded_sha256':e['obf_sha256'],'integrity':'existing verified download / ZIP CRC receipt plus current extracted size; no fresh full OBF hash'},'engine':'bundled OsmAnd Java master-snapshot','scope':'settlement centers snapped by engine to car roads; not exact addresses; no live traffic or road-open claim','commands':[]}
    with tempfile.TemporaryDirectory(prefix='run-',dir=BASE) as td:
        java.insert(1,'-Djava.io.tmpdir='+td)
        def run(cmd):
            evidence['commands'].append(cmd)
            with tempfile.TemporaryFile(dir=td) as f:
                p=subprocess.Popen(cmd,cwd=td,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_FSIZE,(128_000_000,128_000_000)))
                try:p.wait(timeout=max(.1,deadline_s-(time.monotonic()-begin)))
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid,signal.SIGKILL);p.wait();raise TimeoutError('90-second total backend deadline exceeded')
                finally:
                    if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
                f.seek(0);raw=f.read(2_000_000).decode('utf8','replace')
            if p.returncode:raise RuntimeError(raw[-8000:])
            return raw
        try:
            raw=run(java+[str(BASE/'NamedPlaces.java'),str(obf),origin,destination]); evidence['lookup_raw']=raw
            groups={1:[],2:[]}
            for line in raw.splitlines():
                if line.startswith('OBF_VERSION\t'):evidence['source']['obf_format_version']=int(line.split('\t')[1])
                if line.startswith('PLACE\t'):
                    _,idx,oid,lat,lon,name=line.split('\t',5)
                    groups[int(idx)].append({'id':oid,'latitude':float(lat),'longitude':float(lon),'name':name})
            centers=[choose(groups[i],q) for i,q in [(1,origin),(2,destination)]]
            evidence['places']=centers
            if any(x.get('status')=='clarification' for x in centers):evidence['status']='clarification';return evidence
            if lookup_only:
                evidence.update(status='ok',places=centers[:1]);return evidence
            os.symlink(obf,pathlib.Path(td)/obf.name)
            coords=lambda c:str(c['latitude'])+';'+str(c['longitude'])
            raw=run(java+[str(BASE/'local_visuals/RouteGeometry.java'),str(obf),str(centers[0]['latitude']),str(centers[0]['longitude']),str(centers[1]['latitude']),str(centers[1]['longitude'])]);evidence['route_raw']=raw
            totals=re.findall(r'complete_distance=([\d.]+), complete_time=([\d.]+)',raw)
            if not totals:raise RuntimeError('Engine returned no route totals')
            evidence['segments']=parse_engine(raw)
            from local_visuals.route_map import parse_geometry
            evidence['geometry']=parse_geometry(raw,evidence['segments'])
            evidence['maneuvers']=[dict(segment_index=i+1,**s) for i,s in enumerate(evidence['segments']) if s['turn']]
            evidence.update(status='ok',distance_m=float(totals[-1][0]),estimated_travel_s=float(totals[-1][1]))
        except (TimeoutError,RuntimeError) as ex:evidence['error']=str(ex)
        finally:evidence['elapsed_s']=round(time.monotonic()-begin,3)
    return evidence
def execute(request,nav=DEFAULT_NAV):
    if request.get('awaiting'):return {'status':'clarification','pending':request}
    if request.get('action')=='lookup':return route(request['query'],request['query'],request['region'],nav,lookup_only=True)
    return route(request['origin'],request['destination'],request['region'],nav)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',required=True);p.add_argument('--origin',required=True);p.add_argument('--destination',required=True);p.add_argument('--nav',type=pathlib.Path,default=DEFAULT_NAV);a=p.parse_args()
    try:r=route(a.origin,a.destination,a.region,a.nav)
    except (ValueError,OSError,KeyError) as e:r={'status':'error','error':str(e)}
    print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='ok' else 1)
