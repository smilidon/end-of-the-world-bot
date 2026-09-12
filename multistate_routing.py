# SPDX-License-Identifier: GPL-3.0-only
"""Structured US trip requests and bounded offline exact-building lookup. No network."""
import re,subprocess,os,json,pathlib,time,signal,tempfile
STATES=dict(zip('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split(),'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'.split('|')))
COUNTRY=r'\b(?:United States|USA|U\.S\.|US)\b'
def endpoint(raw):
 raw=raw.strip(' ,.!?');state=None;place=raw
 pin=re.fullmatch(r'\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?',raw)
 if pin:return {'raw':raw,'state':None,'place':raw,'house':None,'street':None,'city':None,'address':False,'pin':[float(pin[1]),float(pin[2])]}
 place=re.sub(r'\s+\d{5}(?:-\d{4})?$','',place);raw_state=place
 for abbr,name in STATES.items():
  m=re.search(r'(?:,?\s+)('+re.escape(name)+'|'+abbr+r')\.?$',raw_state,re.I)
  if m:state=name.lower();place=raw_state[:m.start()].strip(' ,');break
 m=re.fullmatch(r'(?:(\d+[\w-]*)\s+)?(.+?)(?:\s+in\s+|,\s*)(.+)',place,re.I)
 return {'raw':raw,'state':state,'place':place,'house':m[1] if m else None,'street':m[2] if m else None,'city':m[3] if m else None,'address':bool(m) or bool(re.match(r'^\d+\s',place))}
def parse(q,pending=None):
 if pending:
  state=next((name.lower() for abbr,name in STATES.items() if q.strip(' .!?').casefold() in (abbr.casefold(),name.casefold())),None)
  missing=[i for i,e in enumerate(pending['endpoints']) if not e['state'] and not e.get('pin')]
  if state and len(missing)==1:
   ends=[dict(e) for e in pending['endpoints']];ends[missing[0]]['state']=state
   return {**pending,'endpoints':ends}
 if pending and re.search(COUNTRY,q,re.I) and not re.search(r'\bfrom\b|\bbetween\b',q,re.I):
  return {**pending,'map_preference':q.strip(),'awaiting':'trip'}
 if not re.search(r'\b(map|directions|route|drive|driving|navigate)\b',q,re.I):return None
 m=re.search(r'\bfrom\s+(.+?)\s+to\s+(.+)',q,re.I) or re.search(r'\bbetween\s+(.+?)\s+and\s+(.+)',q,re.I)
 if not m:return None
 origin=m[1];tail=m[2];end=re.split(r'\s+(?:with\s+(?:gas|fuel)|(?:use|using)\s+(?:the |a )?(?:United States|USA|US)|gas stations|fuel stops)',tail,maxsplit=1,flags=re.I)[0]
 ends=[endpoint(origin),endpoint(end)]
 fuel=bool(re.search(r'\b(?:gas stations|fuel(?: stops| stations)?)\b',q,re.I));interval=re.search(r'(?:every|approximately|about)\s*(\d+(?:\.\d+)?)\s*(miles?|mi\b|km|kilometers?)',q,re.I)
 # Preserve established Michigan settlement flow; intercept addresses, fuel and other states.
 if not (any(e.get('pin') for e in ends) or any(e['address'] for e in ends) or fuel or len({e['state'] for e in ends if e['state']})>1 or any(e['state'] not in (None,'michigan') for e in ends)):return None
 return {'full_input':q,'origin':ends[0]['raw'],'destination':ends[1]['raw'],'endpoints':ends,'profile':'car','fuel_requested':fuel,'fuel_interval':{'value':float(interval[1]),'unit':interval[2]} if interval else None,'map_preference':q[re.search(COUNTRY,q,re.I).start():] if re.search(COUNTRY,q,re.I) else None,'awaiting':'trip','action':'trip'}
def probe(e,nav,seconds=18):
 import named_routing as named
 entry=named.select_region(e['state'],nav);f=nav/entry['obf_file']
 if not f.resolve().is_relative_to((nav/'maps').resolve()) or f.stat().st_size!=entry['unpacked_bytes'] or f.stat().st_size>2*1024**3:raise ValueError('map validation')
 cmd=['java','-XX:ActiveProcessorCount=2','-Xmx512m','-cp',str(nav/'tools/MapCreator/OsmAndMapCreator.jar')+os.pathsep+str(nav/'tools/MapCreator/lib/*'),str(pathlib.Path(__file__).with_name('AddressProbe.java')),str(f),e['city'],e['street'],e['house'] or '']
 with tempfile.TemporaryDirectory(prefix='address-') as td, tempfile.TemporaryFile() as log:
  p=subprocess.Popen(cmd,cwd=td,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:p.wait(timeout=seconds)
  finally:
   if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
  log.seek(0);raw=log.read(200000).decode('utf8','replace')
 if p.returncode:raise ValueError('address engine failed')
 counts=next((list(map(int,x.split('\t')[1:])) for x in raw.splitlines() if x.startswith('COUNTS\t')),None)
 matches=[x.split('\t')[1:] for x in raw.splitlines() if x.startswith('MATCH\t')]
 return {'counts':counts,'matches':matches,'interpolation':[x.split('\t')[1:] for x in raw.splitlines() if x.startswith('INTERPOLATION\t')],'streets':[x.split('\t')[1:] for x in raw.splitlines() if x.startswith('STREET\t')],'source':entry['obf_file'],'snapshot':entry['version']}
def resolve(e,d):
 c=d.get('counts') or [0,0]
 if c[0]!=1 or c[1]!=1:
  options=['%s at %s, %s'%tuple(v) for v in d.get('streets',[])]
  return None, ('Ambiguous endpoint. Choose a specific map pin: '+ '; '.join(options) if options else 'No exact '+('city' if not c[0] else 'street')+' match. Verify spelling or provide a pin; no town center substituted.')
 for key,label in [('matches','exact downloaded building record; entrance unverified'),('interpolation','approximate house-number interpolation; not an actual door'),('streets','approximate street location; not an actual door')]:
  values=d.get(key,[])
  if len(values)>1:return None,'Ambiguous '+key+'. Choose a specific pin: '+'; '.join('%s at %s, %s'%tuple(v) for v in values)
  if len(values)==1:return list(map(float,values[0][1:3])),label
 return None,'Matched street has no usable location; provide a pin.'

def respond(r,nav):
 return 'No route calculated. Keep both street/city/state endpoints explicit; a missing street is never replaced by a town center.'

def execute(r,nav):
 from corridor_routing import execute as route,answer
 started=time.monotonic();pins=[];precision=[];issues=[]
 for e in r['endpoints']:
  if e.get('pin') is not None:pins.append(e['pin']);precision.append('explicit coordinate pin; entrance unverified');continue
  if not(e.get('address') and e.get('city') and e.get('state')):
   issues.append(e['raw']+': please supply street, city, and state.');continue
  try:
   d=probe(e,nav);pin,label=resolve(e,d)
  except (OSError,ValueError,subprocess.TimeoutExpired):pin=None;label='Local address lookup failed or exceeded its limit; no substitute.'
  if pin is None:issues.append(e['raw']+': '+label)
  else:pins.append(pin);precision.append(label)
 if issues:return [],{'status':'incomplete','request':r},'No route calculated. '+' '.join(issues)
 try:
  d=route({**r,'pins':pins,'endpoint_precision':precision,'_lookup_elapsed_s':time.monotonic()-started},nav);text=answer(d)
  return [{'id':'G'+str(i+1),'source':s['file']+'; snapshot '+str(s['snapshot']),'text':'Local routing snapshot; entrance and opening status unverified.'} for i,s in enumerate(d['sources'])],d,text
 except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired,TimeoutError) as ex:
  return [],{'status':'error','request':r,'error_code':type(ex).__name__},'No route calculated: resolved endpoints could not be routed within installed coverage and local limits. No town center substituted.'
