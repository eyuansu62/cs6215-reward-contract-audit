"""Collect twelve pinned official source files, parse definitions, never import them."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parent
PATHS={
'volcengine/verl':['verl/utils/reward_score/gsm8k.py','verl/utils/reward_score/search_r1_like_qa_em.py','verl/utils/reward_score/math_verify.py'],
'hiyouga/EasyR1':['examples/reward_function/math.py','examples/reward_function/dapo.py','examples/reward_function/r1v.py'],
'OpenRLHF/OpenRLHF':['examples/python/reward_func.py','examples/python/math_reward_func.py'],
'NousResearch/atropos':['environments/eval_environments/boolq_eval.py','atroposlib/envs/reward_fns/accuracy_reward.py','atroposlib/envs/reward_fns/format_reward.py','atroposlib/envs/reward_fns/r1_reward.py']}

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'course-project-source-curation'})
 with urllib.request.urlopen(req,timeout=30) as r:return r.read()

def main():
 repos={r['repo']:r for r in json.loads((ROOT/'repo-inventory.json').read_text())['records'] if 'commit' in r}
 out=[]
 for repo,paths in PATHS.items():
  for path in paths:
   item={'repo':repo,'commit':repos[repo]['commit'],'path':path}
   url='https://raw.githubusercontent.com/'+repo+'/'+item['commit']+'/'+path;item['source_url']=url
   try:
    data=fetch(url);dest=ROOT/'sources'/repo.replace('/','__')/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    tree=json.loads((ROOT/'repos'/repo.replace('/','__')/'tree.json').read_text());blob=next(r['sha'] for r in tree['tree'] if r['path']==path)
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
    item.update(source_sha256=hashlib.sha256(data).hexdigest(),git_blob_sha1=blob,source_local=str(dest.relative_to(ROOT)))
    module=ast.parse(data.decode());defs=[]
    for node in ast.walk(module):
     if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
      args=[a.arg for a in node.args.posonlyargs+node.args.args+node.args.kwonlyargs]
      relevant=any(t in node.name.lower() for t in ['score','reward','evaluate','extract','prompt','completion'])
      if relevant:defs.append({'name':node.name,'async':isinstance(node,ast.AsyncFunctionDef),'parameters':args,'vararg':node.args.vararg.arg if node.args.vararg else None,'kwarg':node.args.kwarg.arg if node.args.kwarg else None,'line_span':[node.lineno,node.end_lineno],'return_annotation':ast.unparse(node.returns) if node.returns else None,'has_exact_answer_entry_parameters':{'answer','entry'}<=set(args)})
    item['definitions']=defs;item['has_any_native_exact_candidate']=any(d['has_exact_answer_entry_parameters'] for d in defs)
    print(json.dumps({'repo':repo,'path':path,'defs':defs}),flush=True)
   except Exception as e:item['error']=type(e).__name__+': '+str(e);print(json.dumps(item),flush=True)
   out.append(item)
 (ROOT/'candidate-sources.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'fixed_source_files':len(out),'records':out,'target_execution':False,'model_or_analyzer_runs':0},indent=2)+'\n')
if __name__=='__main__':main()
