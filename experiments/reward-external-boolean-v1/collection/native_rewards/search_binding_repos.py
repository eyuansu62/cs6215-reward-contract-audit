"""Public repository metadata search for native Boolean task reward users."""
from pathlib import Path
from datetime import datetime,timezone
import json,urllib.request,urllib.parse
ROOT=Path(__file__).resolve().parent
queries=['boolq grpo','boolean_expressions reinforcement','bbh reinforcement learning','boolean reward reinforcement']
rows=[]
for q in queries:
 url='https://api.github.com/search/repositories?'+urllib.parse.urlencode({'q':q,'per_page':10})
 req=urllib.request.Request(url,headers={'User-Agent':'course-project-source-curation','Accept':'application/vnd.github+json'})
 try:
  with urllib.request.urlopen(req,timeout=30) as r:d=json.load(r)
  out={'query':q,'total_count':d.get('total_count'),'items':[{'repo':x['full_name'],'description':x.get('description'),'default_branch':x['default_branch'],'url':x['html_url']} for x in d.get('items',[])]}
 except Exception as e:out={'query':q,'error':type(e).__name__+': '+str(e)}
 rows.append(out);print(json.dumps(out),flush=True)
(ROOT/'binding-repository-search.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'searches':rows,'source_content_read':False,'model_analyzer_or_target_execution':False},indent=2)+'\n')
