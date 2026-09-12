# SPDX-License-Identifier: GPL-3.0-only
from local_visuals.units import distance,imperial_text
"""Read-only downloaded-library retrieval; no generated code, shell, or model tools."""
import contextlib, collections, importlib.util, json, os, pathlib, re, sqlite3, sys, time
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent
FORMATS={'.pdf','.html','.htm','.zim','.txt','.md','.mdx'}
STOP=set('a an the is are of to for in on how what should can i my me do does from local library downloaded according reference search tell about please read file use using and with says say'.split())
SECRET=re.compile(r'(^[.]|(?:^|[-_.])(credentials?|secrets?|tokens?|passwords?|private[-_]?key|config|settings|cookies|auth|environment)(?:$|[-_.]))',re.I)
def safe(root,name):
 p=pathlib.Path(name)
 if p.is_absolute():p=p.relative_to(root)
 if '..' in p.parts or any(SECRET.search(x) for x in p.parts):raise ValueError('Protected path')
 f=root/p
 for parent in [f,*f.parents]:
  if parent==root.parent:break
  if parent.is_symlink():raise ValueError('Symlink forbidden')
 f.resolve().relative_to(root.resolve())
 if not f.is_file():raise ValueError('File unavailable')
 return f

def load(root):
 import reference_helpers
 return reference_helpers.for_root(root)

def catalog(root):
 out=[]
 for base,dirs,files in os.walk(root,followlinks=False):
  dirs[:]=[d for d in dirs if not SECRET.search(d) and not (pathlib.Path(base)/d).is_symlink()]
  for name in files:
   p=pathlib.Path(base)/name
   if p.suffix.lower() in FORMATS or p.suffix.lower()=='.obf':
    try:safe(root,p);out.append(str(p.relative_to(root)))
    except (ValueError,OSError):pass
 return sorted(out)

# Query normalization is lexical, shared by every subject; no authored answers.
STOP.update('would could explain describe have has be it its we you your there some article articles document documents information want know getting get'.split())
ALIASES={'pv':'photovoltaic','photovoltaics':'photovoltaic','batteries':'battery','crops':'crop','gardens':'garden','medicines':'medicine'}
def words(q):
 q=re.sub(r'\bmicro[ -]+hydro\b','microhydro',q.lower())
 return list(dict.fromkeys(ALIASES.get(w,w) for w in re.findall(r'[a-z0-9]+',q) if w not in STOP))[:16]
def navigation(title):
 return bool(re.search(r'(?:^|[/ :])(category|tag|tags|special|portal|user|template|file):|questions/tagged/|(?:highest voted|newest|unanswered|recently active).*questions|(?:^|/)index(?:[._ /]|$)|(?:^|/)categories(?:/|$)',title,re.I))
def relevance(text,keys):
 tokens=set(words_unbounded(text))
 return sum(w in tokens for w in keys)
def words_unbounded(text):
 text=re.sub(r'\bmicro[ -]+hydro\b','microhydro',text.lower())
 return [ALIASES.get(w,w) for w in re.findall(r'[a-z0-9]+',text)]
def title_rank(title,keys,exact=''):
 n=relevance(title,keys);density=n/max(1,len(words(title)))
 normalized=' '.join(words_unbounded(title))
 return 12*n+18*density+(100 if exact and exact in normalized else 0)-(160 if navigation(title) else 0)

def excerpt(text,keys,n=1000):
 text=' '.join(text.split())
 windows=[text[i:i+n] for i in range(0,len(text),max(1,n//2))]
 return max(windows,key=lambda s:relevance(s,keys)*20+sum(min(3,words_unbounded(s).count(w)) for w in keys)-25*len(re.findall(r'https?://|www[.]',s))-15*len(re.findall(r'(?i)external links|page data|cite as|retrieved|resources|references',s)),default='')
def record(file,loc,text):return {'source':file+' '+loc,'text':text,'kind':'external reference'}
def retrieve(q,root):
 if q.lower() in ('hello','hi','thanks') or re.match(r'(?i)remember\s*:',q):return [],None,None
 start=time.monotonic()
 if not root.is_dir():return [],{'status':'library unavailable'},'Configured library directory is unavailable. No local reference was read.'
 try:return _retrieve(q,root,start)
 except (ValueError,OSError,sqlite3.Error):return [],{'status':'read unavailable'},'Requested library data could not be read safely. No reference answer is established.'
def _retrieve(q,root,start):
 files=catalog(root);counts=dict(collections.Counter(pathlib.Path(f).suffix.lower() for f in files))
 status={'status':'bounded search','catalog_files':len(files),'formats':counts,'semantic_index':False}
 helper=load(root);keys=words(q);sources=[]
 quoted=re.search(r'[\"“]([^\"”]{3,180})[\"”]',q)
 exact=' '.join(words_unbounded(quoted[1])) if quoted else ''
 if quoted:keys=words(quoted[1])
 if q.lower().startswith('files:'):
  query=q.split(':',1)[1].strip();m=re.search(r'\s+page\s+(\d+)$',query,re.I);page=int(m[1]) if m else 1
  if m:query=query[:m.start()]
  matches=[f for f in files if query.lower() in f.lower()];page=max(1,page)
  return [],status,(f'{len(matches)} files; page {page}.\n'+'\n'.join(matches[(page-1)*3:page*3]))[:490]
 # Map commands and natural-language map requests never fall through to invented coordinates.
 if q.lower().startswith('map:') or (not q.lower().startswith(('read:','search:','reference:')) and re.search(r'\b(coordinates|route|navigate|find .* on .*map)\b',q,re.I)):
  return map_lookup(q,root,files,status)
 read=re.match(r'(?i)^read:\s*(.+?)(?:\s+page\s+(\d+)|\s+article\s+(\d+))?$',q)
 if read:
  name=read[1].strip();f=safe(root,name)
  if str(f.relative_to(root)) not in files:raise ValueError('Not a document')
  if f.suffix=='.zim':
   if not read[3]:return [],status,'For a ZIM direct read use Read: collections/name.zim article NUMBER. Ordinary questions search archives automatically.'
   idx=read[3];path=helper.run([helper.HERE/'bin/zimdump','list','--idx='+idx,f],2,1500).strip()
   raw=helper.run([helper.HERE/'bin/zimdump','show','--idx='+idx,f],3,1000000)
   sources=[record(name,'article '+idx+': '+path,excerpt(helper.clean(raw),keys))]
  elif f.suffix=='.pdf':
   page=int(read[2] or 1);raw=helper.run(['pdftotext','-f',str(page),'-l',str(page),'-layout',f,'-'],3,100000)
   if not raw.strip():return [],status,'End of file or no readable text on that page; no next page content established.'
   sources=[record(name,'PDF page '+str(page),excerpt(raw,keys))]
  else:
   with f.open('rb') as stream:raw=stream.read(2000000).decode('utf8','replace')
   offset=(int(read[2] or 1)-1)*1000;text=helper.clean(raw) if f.suffix in ('.html','.htm') else raw
   if offset>=len(text):return [],status,'End of file; no more text pages.'
   sources=[record(name,'text page '+str(int(read[2] or 1))+' offset '+str(offset),text[offset:offset+1000])]
 else:
  indexed=set()
  with contextlib.closing(sqlite3.connect(safe(root,'local-qa/guides.sqlite').as_uri()+'?mode=ro',uri=True)) as c:
   indexed={x[0] for x in c.execute('select distinct file from chunks')}
   status['guide_index_files']=len(indexed)
   if keys:
    for join in (' AND ',' OR '):
     rows=c.execute('select file,location,text from chunks where chunks match ? order by rank limit 6',(join.join('"'+w+'"' for w in keys),)).fetchall()
     if rows:break
    for file,loc,text in rows:
     safe(root,file);sources.append(record(file,loc,excerpt(text,keys)))
  # Scan unindexed documents read-only, bounded per file and total time; no filename/topic exclusions.
  scanned=0
  for name in sorted(files,key=lambda f:-sum(w in f.lower() for w in keys)):
   if time.monotonic()-start>3:break
   f=safe(root,name)
   if name in indexed or f.suffix not in FORMATS-{'.zim'}:continue
   if f.suffix=='.pdf':raw=helper.run(['pdftotext','-layout',f,'-'],.5,500000)
   else:
    with f.open('rb') as stream:raw=stream.read(500000).decode('utf8','replace')
   if f.suffix in ('.html','.htm'):raw=helper.clean(raw)
   scanned+=1
   if keys and any(w in raw.lower() for w in keys):sources.append(record(name,'bounded text excerpt',excerpt(raw,keys)))
  status['unindexed_documents_scanned']=scanned
  # Existing embedded indexes, bounded candidate pool and shared extraction deadline.
  hits=[];searched=0;seen=set();demoted=0;per_archive=collections.Counter()
  zims=sorted([f for f in files if f.endswith('.zim')],key=lambda f:-sum(w in f.lower() for w in keys))
  for name in zims:
   remaining=18-(time.monotonic()-start)
   if remaining<=0 or not keys:break
   raw=helper.run([helper.HERE/'bin/zimsearch',safe(root,name),' '.join(keys)],min(1.1,remaining),40000);searched+=1
   candidates=[]
   for idx,score,title in re.findall(r'article (\d+)\s+score ([0-9.]+)\s*:\s*([^\n]+)',raw)[:240]:
    if (name,idx) in seen:continue
    seen.add((name,idx))
    demoted+=int(navigation(title))
    candidates.append((title_rank(title,keys,exact)+float(score)/100,name,idx,title))
   hits.extend(sorted(candidates,reverse=True)[:8])
  status.update(zim_indexes_attempted=searched,zim_count=len(zims),zim_candidates_considered=len(seen),navigation_titles_demoted=demoted)
  read_count=0;rejected=0
  while hits and read_count<12 and time.monotonic()-start<26:
   hit=max(hits,key=lambda h:h[0]-per_archive[h[1]]*18);hits.remove(hit)
   score,name,idx,title=hit
   if navigation(title):rejected+=1;continue
   per_archive[name]+=1;read_count+=1;f=safe(root,name)
   remaining=26-(time.monotonic()-start)
   path=helper.run([helper.HERE/'bin/zimdump','list','--idx='+idx,f],min(.6,remaining),2000).strip()
   if not path or navigation(title+' '+path):rejected+=1;continue
   remaining=26-(time.monotonic()-start)
   if remaining<=0:break
   raw=helper.run([helper.HERE/'bin/zimdump','show','--idx='+idx,f],min(1,remaining),500000)
   body=helper.clean(raw)
   if len(body)<180 or not relevance(body,keys):continue
   src=record(name,'article '+idx+': '+path.splitlines()[0]+' ('+title+')',excerpt(body,keys))
   src['_title']=title;sources.append(src)
  status.update(zim_articles_sampled=read_count,navigation_candidates_rejected=rejected)
  def rank(s):
   title=s.get('_title',s['source'])
   return relevance(s['text'],keys)*20+title_rank(title,keys,exact)
  # Prefer distinct relevant documents; never fill with an irrelevant source for diversity.
  pool=sorted([s for s in sources if relevance(s['text'],keys)],key=rank,reverse=True)
  sources=[];documents=set();texts=set()
  while pool and len(sources)<2:
   best=max(pool,key=lambda s:rank(s)-(12 if s['source'].split(' article ')[0].split(' PDF page ')[0] in documents else 0))
   pool.remove(best)
   identity=best['source'].split(': ',1)[0] if ' article ' in best['source'] else best['source'].split(' PDF page ')[0]
   fingerprint=' '.join(best['text'].lower().split())
   if identity in texts or fingerprint in texts:continue
   texts.update((identity,fingerprint));documents.add(best['source'].split(' article ')[0].split(' PDF page ')[0])
   best.pop('_title',None);sources.append(best)
 sources=[s for s in sources if s['text'].strip()]
 for i,s in enumerate(sources):s['id']='R'+str(i+1);s['source']=' '.join(s['source'].split())[:500]
 status['seconds']=round(time.monotonic()-start,3)
 return sources,status,None if sources else 'No matching readable excerpt found in this bounded library search; this does not prove the library has no relevant content.'

def map_lookup(q,root,files,status):
 return [],status,'Routing is optional. Use named_routing.py with an explicitly configured navigation directory; no route was calculated.'
