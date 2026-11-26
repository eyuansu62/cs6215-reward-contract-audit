from pathlib import Path
from datetime import datetime,timezone
import json,urllib.request
ROOT=Path(__file__).resolve().parent/'binding_phase'
REPOS=['kbwal/rl-next-tokens','lew624/novelty_rl','zzx-peter/Multiple-Solution-TTRL','coder-qicao/RL4GLUE','Shekswess/tiny-reasoning-language-model']
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'course-project-source-curation'}),timeout=30) as r:return json.load(r)
rows=[]
for repo in REPOS:
 try:
  meta=get('https://api.github.com/repos/'+repo);commit=get('https://api.github.com/repos/'+repo+'/commits/'+meta['default_branch']);tree=get('https://api.github.com/repos/'+repo+'/git/trees/'+commit['sha']+'?recursive=1')
  dest=ROOT/repo.replace('/','__');dest.mkdir(parents=True,exist_ok=True)
  for name,value in [('repo.json',meta),('commit.json',commit),('tree.json',tree)]: (dest/name).write_text(json.dumps(value,indent=2)+'\n')
  paths=[x['path'] for x in tree.get('tree',[]) if x['type']=='blob' and (x['path'].endswith(('.py','.md','.json','.yaml','.yml')))]
  row={'repo':repo,'commit':commit['sha'],'truncated':tree.get('truncated'),'paths':paths};rows.append(row);print(json.dumps(row),flush=True)
 except Exception as e:rows.append({'repo':repo,'error':str(e)});print(json.dumps(rows[-1]),flush=True)
(ROOT/'project-inventory.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'records':rows,'metadata_only':True},indent=2)+'\n')
