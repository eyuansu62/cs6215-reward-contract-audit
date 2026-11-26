"""Public source curation only; no subject import/execution or analyzer calls."""
from pathlib import Path
from datetime import datetime,timezone
import concurrent.futures,hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parent
CANDIDATES=[
 ('EnvCommons/ReasoningGym', ['README.md','environment.py']),
 ('huggingface/OpenEnv',['envs/reasoning_gym_env/README.md','envs/reasoning_gym_env/server/reasoning_gym_environment.py']),
 ('NousResearch/atropos',['environments/reasoning_gym_environment/README.md','environments/reasoning_gym_environment/reasoning_gym_environment.py']),
 ('apple/ml-multilingual-reasoning-gym',['README.md','reasoning_gym/dataset.py','reasoning_gym/algorithmic/game_of_life_halting.py']),
 ('researchim-ai/reasoning-gym-ru',['README.md','reasoning_gym/dataset.py','reasoning_gym/algorithmic/game_of_life_halting.py']),
]
def get(url):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Codex-source-curation'}),timeout=30).read()
def task(row):
 repo,paths=row;folder=ROOT/'raw'/repo.replace('/','__');folder.mkdir(parents=True,exist_ok=True);records=[]
 try:
  commit=json.loads(get('https://api.github.com/repos/'+repo+'/commits/HEAD'));pin=commit['sha']
  (folder/'pin.json').write_text(json.dumps({'repo':repo,'commit':pin,'source':'GitHub commits/HEAD resolved before source fetch','observed_utc':datetime.now(timezone.utc).isoformat()},indent=2)+'\n')
 except Exception as error:return {'repo':repo,'status':'pin_failed','error':str(error),'records':[]}
 for path in paths:
  url='https://raw.githubusercontent.com/'+repo+'/'+pin+'/'+path
  try:
   data=get(url);dest=folder/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
   records.append({'path':path,'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'status':'fetched','local_path':str(dest.relative_to(ROOT))})
  except Exception as error:records.append({'path':path,'url':url,'status':'fetch_failed','error':str(error)})
 return {'repo':repo,'commit':pin,'records':records,'subject_executed':False}
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:records=list(pool.map(task,CANDIDATES))
 output={'created_utc':datetime.now(timezone.utc).isoformat(),'role':'RG-style external source candidate curation, not benchmark selection','records':records,'new_model_or_analyzer_calls':0,'target_executions':0}
 (ROOT/'candidate-sources.json').write_text(json.dumps(output,indent=2)+'\n')
 print(json.dumps([{'repo':r['repo'],'commit':r.get('commit'),'fetched':sum(x['status']=='fetched' for x in r['records']),'failures':sum(x['status']!='fetched' for x in r['records'])} for r in records],indent=2))
