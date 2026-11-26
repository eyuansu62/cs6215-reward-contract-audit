"""Project fixed source/contracts for detectors; never supplies labels or probes."""
from pathlib import Path
import ast,hashlib,json
ROOT=Path(__file__).resolve().parent
DATA=ROOT.parents[1]/'datasets/reasoning-gym-reward-v1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 frozen=read(ROOT/'protocol/contracts-evaluation-freeze.json')
 for name,expected in frozen['files_sha256'].items():assert sha(ROOT/'protocol'/name)==expected
 contracts=read(ROOT/'protocol/contracts.json');subjects=read(DATA/'subjects.json')['subjects']
 units=[];mapping=[]
 for s in subjects:
  if s['id'] not in contracts['primary_subject_ids']:continue
  fragments={m['name']:(DATA/m['source_path']).read_text() for m in s['extracted_methods']}
  for m in s['extracted_methods']:assert sha(DATA/m['source_path'])==m['source_sha256']
  source=(DATA/s['source_file']).read_text();module=ast.parse(source);bindings={}
  for n in module.body:
   if isinstance(n,ast.Import):
    for a in n.names:
     if a.name in {'math','json','re','cmath','string'}:bindings[a.asname or a.name]=a.name
   elif isinstance(n,ast.ImportFrom) and n.level==0 and n.module in {'fractions','collections','decimal'}:
    for a in n.names:bindings[a.asname or a.name]=n.module+'.'+a.name
  score=fragments[s['method']];fn=ast.parse(score).body[0]
  params=fn.args.posonlyargs+fn.args.args;fixed={}
  for a,default in zip(params[-len(fn.args.defaults):],fn.args.defaults):
   if a.arg not in {'self','answer','entry'}:
    if not isinstance(default,ast.Constant):raise ValueError('Unproved public configuration default')
    fixed[a.arg]=default.value
  helpers=[{'name':name,'source':fragments[name]} for name in s['helpers']]
  combined='\n'.join([h['source'] for h in helpers]+[score])
  contract={'id':s['contract_id'],'candidate_arg':'answer','reference_arg':'entry','full_credit_threshold':1.0,**contracts['contracts'][s['contract_id']]}
  if contract['id']=='C_PROBABILITY_FULL':assert fixed.get('tol')==contract['absolute_tolerance']
  body={'entry_name':s['method'],'source':combined,'score_source':score,'helpers':helpers,'contract':contract,'stdlib_bindings':bindings,'fixed_parameters':fixed}
  identifier=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  units.append({'unit_id':identifier,**body});mapping.append({'id':s['id'],'unit_id':identifier,'function_family':s['function_family'],'contract_id':s['contract_id']})
 # Diagnostic predictions are kept separate and receive no expected labels.
 diagnostic_units=[];diagnostic_map=[]
 for case in read(ROOT/'evaluation/diagnostics.json')['cases']:
  cid=case['contract_id'];body={'entry_name':'score_answer','source':case['source'],'score_source':case['source'],'helpers':[],
    'contract':{'id':cid,'candidate_arg':'answer','reference_arg':'entry','full_credit_threshold':1.0,**contracts['contracts'][cid]},
    'stdlib_bindings':{'math':'math'} if 'math.' in case['source'] else {},'fixed_parameters':{}}
  uid=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  diagnostic_units.append({'unit_id':uid,**body});diagnostic_map.append({'id':case['id'],'unit_id':uid,'expected_violation':case['expected_violation'],'rationale':case['rationale']})
 (ROOT/'diagnostic-inputs.json').write_text(json.dumps({'units':diagnostic_units,'synthetic':True},indent=2)+'\n')
 (ROOT/'evaluation/diagnostic-oracle.json').write_text(json.dumps({'labels':diagnostic_map,'separate_from_primary':True},indent=2)+'\n')
 output={'detector_input_scope':'Exact score/helper source, source-derived stdlib import aliases and literal default parameters, fixed reviewed contracts only. No curated probes, rewards, issues, status, source disposition or labels.','units':units}
 (ROOT/'inputs.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'evaluation/unit-map.json').write_text(json.dumps({'mapping':mapping,'not_passed_to_detectors':True},indent=2)+'\n')
 print(json.dumps({'units':len(units),'same_fixed_contracts_both_methods':True,'probability_tolerance_fixed_at_source_default':True}))
if __name__=='__main__':main()
