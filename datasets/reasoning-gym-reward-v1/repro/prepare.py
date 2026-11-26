"""Prepare real scoring-source excerpts and explicit witness inputs; no scoring."""
from pathlib import Path
import ast
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from source_extract import extract_function
ROOT=Path(__file__).resolve().parents[1]

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 text=json.dumps(x,ensure_ascii=False,indent=2)+'\n'
 if p.exists() and p.read_text()!=text:raise ValueError('Preserve previous preparation: '+str(p))
 p.write_text(text)

def normalize():
 subjects=[]
 for record in read(ROOT/'records/bugs.json'):
  s=record['source'];helpers=[]
  for h in record['extraction']['necessary_helpers']:
   helpers.append(h['qualified_name'].split('.')[-1] if isinstance(h,dict) else h)
  globs=record['extraction']['required_globals']
  probes=[]
  for kind in ['counterexamples','normal_controls']:
   for p in record[kind]:
    expectation=p.get('expected_current_reward')
    if expectation is None:expectation={'equals':p['source_review_predicted_reward']}
    probes.append({'id':kind+'/'+p['id'],'role':kind,'answer':p['candidate_answer'],'entry':p['entry'],
      'source_behavior_expectation':expectation,'contract_expectation':p.get('contract_expected_reward'),
      'intended_original_bug_probe':kind=='counterexamples' and record['record_kind']=='reported_bug_original',
      'upstream_probe_metadata':p})
  subjects.append({'id':record['id'],'family_id':record['family_id'],'kind':record['record_kind'],'split':'development_source_exposed',
   'source_file':s['source_file'],'source_sha256':s['source_file_sha256'],'class':s['class'],'method':s['method'],'helpers':helpers,
   'globals':globs,'record_file':'records/bugs.json','probes':probes,'contract':record['contract']})
 controls=read(ROOT/'records/controls.json')
 for record in controls['controls']:
  s=record['source'];probes=[]
  for p in record['probes']:
   probes.append({'id':p['id'],'role':'normal_control_probe','answer':p['answer'],
    'entry':record['native_inputs']['entries'][p['entry_id']], 'source_behavior_expectation':{'equals':p['expected_reward']},
    'contract_expectation':None,'intended_original_bug_probe':False,'upstream_probe_metadata':p})
  subjects.append({'id':record['id'],'family_id':record['grouping']['independent_function_family'],'kind':'normal_control',
   'split':'development_source_exposed','source_file':s['source_file'],'source_sha256':s['sha256'],'class':s['class'],'method':s['method'],
   'helpers':[h['name'] for h in s['required_helpers']],'globals':s['stdlib_dependencies'],
   'record_file':'records/controls.json','probes':probes,'contract':record['contract']})
 return subjects

def main():
 subjects=normalize();excerpts=[]
 for s in subjects:
  path=ROOT/s['source_file'];assert sha(path)==s['source_sha256']
  module=path.read_text();methods=[]
  for name in [*s['helpers'],s['method']]:
   source,proof=extract_function(module,s['class']+'.'+name)
   dest=ROOT/'extracted'/s['id']/(name+'.py');dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists() and dest.read_text()!=source:raise ValueError('Preserve extracted source')
   dest.write_text(source)
   methods.append({'name':name,'source_path':str(dest.relative_to(ROOT)),'source_sha256':sha(dest),'ast_sha256':hashlib.sha256(ast.dump(ast.parse(source).body[0],include_attributes=False).encode()).hexdigest(),'extraction':proof})
  s['extracted_methods']=methods;excerpts.extend(methods)
 write(ROOT/'repro/replay-inputs.json',{'scope':'Curated native-input witnesses/controls, not generator samples, model prompts, static predictions or an unseen dataset.','subjects':subjects,'subject_count':len(subjects),'function_families':len({s['family_id'] for s in subjects}),'probe_count':sum(len(s['probes']) for s in subjects),'all_scoring_asts_identical_to_pinned_source':True})
 print(json.dumps({'subjects':len(subjects),'probes':sum(len(s['probes']) for s in subjects),'excerpts':len(excerpts)}))
if __name__=='__main__':main()
