"""Pinned source fetch for source-grounded input-binding phase; no execution."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parent;B=ROOT/'binding_phase'
SELECTION={
'kbwal/rl-next-tokens':['README.md','grpo.py','grpo_base.py','load_data.py'],
'zzx-peter/Multiple-Solution-TTRL':['README.md','verl/utils/reward_score/boolean/__init__.py','verl/utils/reward_score/__init__.py'],
'coder-qicao/RL4GLUE':['README.md','ppo.py','prompt.py','utils.py']}
def fetch(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'course-project-source-curation'}),timeout=30) as r:return r.read()
records=[]
for repo,paths in SELECTION.items():
 dest=B/repo.replace('/','__');pin=json.loads((dest/'commit.json').read_text())['sha'];tree=json.loads((dest/'tree.json').read_text());blobs={x['path']:x['sha'] for x in tree['tree'] if x['type']=='blob'}
 for path in paths:
  row={'repo':repo,'commit':pin,'path':path,'url':'https://raw.githubusercontent.com/'+repo+'/'+pin+'/'+path}
  try:
   data=fetch(row['url']);blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert blob==blobs[path]
   file=dest/'sources'/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
   row.update(source_sha256=hashlib.sha256(data).hexdigest(),git_blob_sha1=blob,source_local=str(file.relative_to(ROOT)))
   if path.endswith('.py'):
    tree_=ast.parse(data.decode());defs=[{'name':n.name,'params':[a.arg for a in n.args.posonlyargs+n.args.args+n.args.kwonlyargs],'span':[n.lineno,n.end_lineno],'source':ast.get_source_segment(data.decode(),n)} for n in ast.walk(tree_) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(s in n.name.lower() for s in ['reward','score','correct','accuracy','extract','answer','prompt'])]
    row['relevant_definitions']=defs
   print(json.dumps({'repo':repo,'path':path,'definitions':[{k:v for k,v in d.items() if k!='source'} for d in row.get('relevant_definitions',[])]}),flush=True)
  except Exception as e:row['error']=str(e);print(json.dumps(row),flush=True)
  records.append(row)
(B/'source-records.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'records':records,'model_analyzer_target_execution':False},indent=2)+'\n')
