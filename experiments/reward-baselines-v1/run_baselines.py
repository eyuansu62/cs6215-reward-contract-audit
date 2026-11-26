"""Fixed-contract source-only baseline study. No LLM or scorer execution."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,sys,time
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def method_files():
 paths=[*ROOT.glob('*.py'),*(ROOT/'tools').glob('*.py'),*(ROOT/'protocol').glob('*.json'),ROOT/'tools/tool-release.json']
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def verify():
 f=read(ROOT/'method-freeze.json');assert method_files()==f['files_sha256'],'Frozen method/protocol changed'
 for n,h in f['inputs_sha256'].items():assert sha(ROOT/n)==h,n
 contract=read(ROOT/'protocol/contracts-evaluation-freeze.json')
 for n,h in contract['files_sha256'].items():assert sha(ROOT/'protocol'/n)==h
 return sha(ROOT/'method-freeze.json')
def freeze():
 p=ROOT/'method-freeze.json'
 if p.exists():raise ValueError('Preserve existing method freeze')
 write(p,{'created_utc':datetime.now(timezone.utc).isoformat(),'files_sha256':method_files(),
  'inputs_sha256':{n:sha(ROOT/n) for n in ['inputs.json','diagnostic-inputs.json','evaluation/unit-map.json','evaluation/diagnostics.json']},
  'oracle_sha256':sha(ROOT/'evaluation/oracle.json'),'diagnostic_oracle_sha256':sha(ROOT/'evaluation/diagnostic-oracle.json'),
  'frozen_before_primary_predictions':True,'source_exposed_development':True,'LLM_runs':0})
 return {'method_freeze_sha256':verify(),'files':len(read(p)['files_sha256'])}
def predict(output,diagnostic=False):
 from semgrep_baseline import run as semgrep
 from symbolic_baseline import analyze as symbolic
 method=verify();inp=ROOT/('diagnostic-inputs.json' if diagnostic else 'inputs.json');data=read(inp)
 output=Path(output).resolve()
 if output.exists():raise ValueError('Preserve earlier predictions; use new output')
 output.mkdir(parents=True);rows=[]
 for u in data['units']:
  methods={};artifacts={}
  for name,fn in [('semgrep',semgrep),('symbolic',symbolic)]:
   started=time.perf_counter();dest=output/'raw'/u['unit_id']/name
   try:
    result=fn(copy.deepcopy(u),dest) if name=='semgrep' else fn(copy.deepcopy(u))
    if result.get('verdict') not in {'alarm','no_alarm','unknown'}:raise ValueError('Invalid verdict')
   except Exception as error:result={'verdict':'unknown','unexpected_error':type(error).__name__+': '+str(error),'source_executed':False}
   result['wall_seconds']=round(time.perf_counter()-started,6);methods[name]=result
   dest.mkdir(parents=True,exist_ok=True);write(dest/'record.json',result)
   if name=='semgrep' and result.get('status')=='complete':
    cmd=result['command'];coverage=result['coverage']['command']
    for key,path in [('source',cmd[-1]),('rules',cmd[cmd.index('-rules')+1]),('coverage_rules',coverage[coverage.index('-rules')+1])]:
     artifacts[key]=str(Path(path).resolve().relative_to(output))
  rows.append({'unit_id':u['unit_id'],'contract_id':u['contract']['id'],'source_sha256':hashlib.sha256(u['source'].encode()).hexdigest(),'methods':methods,'semgrep_artifacts':artifacts})
 assert verify()==method
 result={'status':'complete','method_freeze_sha256':method,'inputs_sha256':sha(inp),'diagnostic':diagnostic,
  'origin_output':str(output),'oracle_read_by_prediction':False,'LLM_runs':0,'target_scorer_executed':False,'units':rows}
 write(output/'predictions.json',result)
 return {'cases':len(rows),'methods':len(rows)*2,'unknown':{m:sum(r['methods'][m]['verdict']=='unknown' for r in rows) for m in ['semgrep','symbolic']}}
def metric(rows,m):
 c={k:0 for k in ['tp','fp','fn','tn','unknown_positive','unknown_negative']}
 for r in rows:
  v=r['methods'][m]['verdict'];y=r['expected_violation']
  if v not in {'alarm','no_alarm','unknown'}:raise ValueError('Invalid prediction verdict')
  k=('unknown_positive' if y else'unknown_negative') if v=='unknown' else ('tp' if y else'fp') if v=='alarm' else ('fn' if y else'tn')
  c[k]+=1
 n=len(rows);u=c['unknown_positive']+c['unknown_negative'];tp=c['tp'];fp=c['fp'];fn=c['fn'];pos=tp+fn+c['unknown_positive']
 return {**c,'total':n,'unknown':u,'correct':tp+c['tn'],'accuracy':(tp+c['tn'])/n if n else None,'coverage':(n-u)/n if n else None,
  'precision':tp/(tp+fp) if tp+fp else None,'recall_with_unknown':tp/pos if pos else None,
  'f1_with_unknown':2*tp/(2*tp+fp+fn+c['unknown_positive']) if 2*tp+fp+fn+c['unknown_positive'] else None}
def score(predictions,output):
 p=Path(predictions).resolve();pred=read(p);current=verify();f=read(ROOT/'method-freeze.json');diag=pred['diagnostic']
 assert pred['method_freeze_sha256']==current,'Prediction method does not match freeze'
 inp=ROOT/('diagnostic-inputs.json' if diag else 'inputs.json')
 assert pred['inputs_sha256']==sha(inp),'Prediction input does not match freeze'
 expected={u['unit_id']:u for u in read(inp)['units']}
 ids=[u['unit_id'] for u in pred['units']]
 assert len(ids)==len(set(ids)) and set(ids)==set(expected),'Missing/duplicate/unexpected prediction units'
 for unit in pred['units']:
  original=expected[unit['unit_id']]
  assert unit['contract_id']==original['contract']['id']
  assert unit['source_sha256']==hashlib.sha256(original['source'].encode()).hexdigest()
  assert set(unit['methods'])=={'semgrep','symbolic'}
 oracle=ROOT/'evaluation'/('diagnostic-oracle.json' if diag else 'oracle.json')
 assert sha(oracle)==f['diagnostic_oracle_sha256' if diag else'oracle_sha256']
 labels=read(oracle)['labels'];mapping={x['unit_id']:x for x in read(ROOT/'evaluation/unit-map.json')['mapping']} if not diag else {x['unit_id']:x for x in labels}
 by_id={x['id']:x for x in labels};rows=[]
 for x in pred['units']:
  identity=mapping[x['unit_id']];gold=by_id[identity['id']]
  row={'id':gold['id'],'function_family':gold.get('family',gold['id']),'contract_id':x['contract_id'],'expected_violation':gold['expected_violation'],'methods':{}}
  for name,result in x['methods'].items():
   v=result['verdict'];row['methods'][name]={'verdict':v,'correct':v!='unknown' and (v=='alarm')==gold['expected_violation'],
    'reason':result.get('unsupported_reason') or result.get('explanation') or result.get('reason'),
    'unexpected_error':result.get('unexpected_error'),'evidence':result.get('certificate')}
  rows.append(row)
 assert len(rows)==len(labels)
 paired={'gain_ids':[],'loss_ids':[]}
 for row in rows:
  a=row['methods']['semgrep']['correct'];b=row['methods']['symbolic']['correct']
  if b and not a:paired['gain_ids'].append(row['id'])
  if a and not b:paired['loss_ids'].append(row['id'])
 result={'method_freeze_sha256':verify(),'predictions_sha256':sha(p),'oracle_sha256':sha(oracle),'diagnostic':diag,
  'overall':{m:metric(rows,m) for m in ['semgrep','symbolic']},'symbolic_paired_vs_semgrep':paired,'cases':rows,
  'source_exposed_development':True,'LLM_tested':False,'qualification':'NoAlarm is operational no-warning/source-certificate status, not arbitrary-Python safety. Unknowns remain in denominators; synthetic diagnostics separate.'}
 output=Path(output)
 if output.exists():raise ValueError('Preserve previous scores')
 write(output,result);return result['overall']
def normalize(value,origin,core):
 if isinstance(value,dict):return {k:normalize(v,origin,core) for k,v in value.items() if k not in {'wall_seconds','command'}}
 if isinstance(value,list):return [normalize(v,origin,core) for v in value]
 if isinstance(value,str):
  if core:value=value.replace(core,'<core>')
  return value.replace(origin,'<run>')
 return value
def compare(oldpath,newpath,oldscore,newscore,output):
 oldpath,newpath=Path(oldpath),Path(newpath);a,b=read(oldpath),read(newpath)
 def core(p):return next((u['methods']['semgrep'].get('engine',{}).get('path') for u in p['units'] if u['methods']['semgrep'].get('engine')),None)
 assert normalize(a,a['origin_output'],core(a))==normalize(b,b['origin_output'],core(b)),'Analytical predictions differ'
 checks=[]
 for old,new in zip(a['units'],b['units']):
  assert old['unit_id']==new['unit_id']
  for record,path in [(old,oldpath.parent),(new,newpath.parent)]:
   sg=record['methods']['semgrep']
   if sg.get('status')!='complete':continue
   assert sg['engine']['sha256']=='8b0c1fa10fa70372ea64ca0dc9cf3de0fd53db9c2556f6af5f973e8df12d4995'
   for key in ['source','rules','coverage_rules']:
    local=path/record['semgrep_artifacts'][key];assert local.is_file()
    expected=record['source_sha256'] if key=='source' else sg['rule_sha256'] if key=='rules' else sg['coverage']['rule_sha256']
    assert sha(local)==expected
  def flags(sg,coverage=False):
   cmd=(sg['coverage'] if coverage else sg)['command'][:];i=cmd.index('-rules')+1
   cmd[0]='<core>';cmd[i]='<verified-rule>';cmd[-1]='<verified-source>';return cmd
  if old['methods']['semgrep'].get('status')=='complete':
   for c in [False,True]:assert flags(old['methods']['semgrep'],c)==flags(new['methods']['semgrep'],c)
   checks.append(old['unit_id'])
 sa,sb=read(oldscore),read(newscore)
 assert sa['predictions_sha256']==sha(oldpath) and sb['predictions_sha256']==sha(newpath)
 clean=lambda s:{k:v for k,v in s.items() if k not in {'predictions_sha256'}}
 assert clean(sa)==clean(sb),'Scores differ'
 assert not Path(output).exists(),'Preserve prior comparison'
 result={'passed':True,'method_freeze_sha256':verify(),'cases':len(a['units']),'method_results':len(a['units'])*2,
  'full_analytical_outputs_equal':True,'all_score_metrics_equal':True,'semgrep_taint_or_pattern_commands_verified':len(checks),
  'semgrep_function_return_coverage_commands_verified':len(checks),'normalization_only':['wall_seconds','command fields with flags/bytes checked separately','recorded run/core paths'],
  'new_LLM_or_target_runs':0,'same_machine_replay':True}
 write(output,result);return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['freeze','verify','predict','score','compare']);p.add_argument('--output',type=Path);p.add_argument('--diagnostic',action='store_true');p.add_argument('--predictions',type=Path);p.add_argument('--old',type=Path);p.add_argument('--new',type=Path);p.add_argument('--old-scores',type=Path);p.add_argument('--new-scores',type=Path)
 a=p.parse_args()
 if a.operation=='freeze':r=freeze()
 elif a.operation=='verify':r={'method_freeze_sha256':verify(),'passed':True}
 elif a.operation=='predict':r=predict(a.output,a.diagnostic)
 elif a.operation=='score':r=score(a.predictions,a.output)
 else:r=compare(a.old,a.new,a.old_scores,a.new_scores,a.output)
 print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
