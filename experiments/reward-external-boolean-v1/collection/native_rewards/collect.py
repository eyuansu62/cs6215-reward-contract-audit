"""Read-only fixed-commit source collection; no target imports or execution."""
from pathlib import Path
from datetime import datetime, timezone
import ast,hashlib,json,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
REPOS=['volcengine/verl','hiyouga/EasyR1','OpenRLHF/OpenRLHF','NousResearch/atropos']

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'course-project-source-curation','Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read(),dict(r.headers)

def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
def main():
 records=[]
 for repo in REPOS:
  try:
   info,_=fetch('https://api.github.com/repos/'+repo);metadata=json.loads(info);branch=metadata['default_branch']
   raw,_=fetch('https://api.github.com/repos/'+repo+'/commits/'+branch);commit=json.loads(raw);sha=commit['sha']
   tree_raw,_=fetch('https://api.github.com/repos/'+repo+'/git/trees/'+sha+'?recursive=1');tree=json.loads(tree_raw)
   prefix=ROOT/'repos'/repo.replace('/','__');write(prefix/'repo.json',metadata);write(prefix/'commit.json',commit);write(prefix/'tree.json',tree)
   candidates=[r['path'] for r in tree.get('tree',[]) if r.get('type')=='blob' and r['path'].endswith('.py') and any(x in r['path'].lower() for x in ['reward','score','bool','logic'])]
   row={'repo':repo,'branch':branch,'commit':sha,'tree_truncated':tree.get('truncated'),'candidate_paths':candidates};records.append(row)
   print(json.dumps(row),flush=True)
  except Exception as e:
   row={'repo':repo,'error':type(e).__name__+': '+str(e)};records.append(row);print(json.dumps(row),flush=True)
 write(ROOT/'repo-inventory.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'role':'Primary metadata discovery before up to twelve selected source reads','records':records,'target_execution':False})
if __name__=='__main__':main()
