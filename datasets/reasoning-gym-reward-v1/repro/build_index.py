"""Consolidate source curation and executed evidence; no analyzer is invoked."""
from pathlib import Path
from datetime import datetime,timezone
import ast,csv,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 data=read(ROOT/'repro/replay-inputs.json');refs=read(ROOT/'collection/refs.json');summary=read(ROOT/'results/replay-02/summary.json')
 bugs={r['id']:r for r in read(ROOT/'records/bugs.json')}
 controls={r['id']:r for r in read(ROOT/'records/controls.json')['controls']}
 subjects=[];contracts=[];evidence=[]
 property_ids={'rg-issue-543':'C_PROBABILITY_FULL','rg-issue-544':'C_BOOLEAN_FULL','rg-issue-545':'C_COMPLEX_FINITE',
 'PalindromeDataset.score_answer':'C_PALINDROME_FULL','PrimeFactorizationDataset.score_answer':'C_PRIME_FACTORS_FULL',
 'GroupAnagramsDataset.score_answer':'C_ANAGRAM_ORDER_CONDITIONAL'}
 for s in data['subjects']:
  raw=bugs.get(s['id'],controls.get(s['id']));result=read(ROOT/'results/replay-02'/(s['id']+'.json'))
  qualified='group-anagrams' in s['id'];property_id=property_ids[s['family_id']]
  disposition='qualified_semantic_order_control_not_general_safety_negative' if qualified else s['kind']
  common={'id':s['id'],'function_family':s['family_id'],'contract_id':property_id,'disposition':disposition,
   'primary_eligible':not qualified,'split':'development_source_exposed','project':'open-thought/reasoning-gym',
   'source_file':s['source_file'],'source_sha256':s['source_sha256'],'class':s['class'],'method':s['method'],
   'helpers':s['helpers'],'extracted_methods':s['extracted_methods'],'review_record':s['record_file'],
   'execution_evidence':'results/replay-02/'+s['id']+'.json'}
  subjects.append(common)
  contracts.append({'subject_id':s['id'],'contract_id':property_id,'reviewed_contract':s['contract'],
   'normative_source_evidence':raw.get('normative_evidence',raw.get('reference_evidence',[])),
   'usage':'Reviewed task-contract evidence/gold for future specification experiments; do not silently supply it as LLM-inferred output.',
   'qualification':'For GroupAnagrams, only order/content semantics on valid list-of-lists; not schema-safety negative.' if qualified else 'Specific declared contract only; not a global bug-free-function proof.'})
  issue=raw.get('issue');repair=raw.get('repair')
  observations=[]
  for p in result['probes']:
   observations.append({'id':p['id'],'answer':p['answer'],'entry':p['entry'],'actual_reward':p['observed'].get('reward'),
    'source_behavior_matches':p['source_behavior_matches'],'full_credit_contract_violation':p['full_credit_contract_violation_observed'],
    'declared_contract_expectation':p['declared_contract_expectation'],'declared_expectation_satisfied':p['declared_expectation_satisfied'],
    'input_origin':'Explicit minimal source-shaped fixture; no generator/seed sample claimed.'})
  evidence.append({'subject_id':s['id'],'function_family':s['family_id'],'primary_eligible':not qualified,
   'evidence_levels':['source_reviewed','exact_scoring_AST_executed_in_isolated_harness'],
   'upstream_report':issue,'upstream_repair':repair,'source_review_snapshot':s['record_file'],
   'execution_status':'executed_real_method_with_source_identity_and_declared_native_context',
   'full_package_or_generator_execution':False,'observations':observations,
   'global_cleanliness_proved':False,'actual_RL_exploitation_or_training_effect_established':False,
   'schema_diagnostic':'results/schema-boundary-diagnostic.json' if qualified else None})
 primary=[s for s in subjects if s['primary_eligible']]
 write(ROOT/'subjects.json',{'subjects':subjects,'source_only_index':True,'analyzer_predictions_exist':False})
 write(ROOT/'contracts.json',{'role':'AI-assisted reviewed task contracts, separate from future model outputs or analyzer predictions.','contracts':contracts})
 write(ROOT/'evidence.json',{'canonical_replay':'results/replay-02','subjects':evidence,'additional_diagnostic':read(ROOT/'results/schema-boundary-diagnostic.json'),
 'validator_correction':'audit/contract-validator-correction.json','prior_replay_retained':'results/replay-01','curator_snapshot_status_note':'Pending execution fields in raw records reflect authorship before root replay; this consolidated evidence is authoritative for current execution status.'})
 write(ROOT/'dataset.json',{'name':'Reasoning Gym reward-contract curation v1','created_utc':datetime.now(timezone.utc).isoformat(),
 'source_repository':refs['repository'],'pinned_source_refs':refs['refs'],
 'indices':{'source_subjects':'subjects.json','reviewed_contracts':'contracts.json','executed_witnesses_and_repair_status':'evidence.json'},
 'counts':{'archived_source_versions':len(subjects),'archived_function_families':len({s['function_family'] for s in subjects}),
  'primary_source_versions':len(primary),'primary_function_families':len({s['function_family'] for s in primary}),
  'reported_bug_originals':3,'unmerged_upstream_repair_candidates':2,'primary_property_scoped_normal_controls':2,
  'qualified_nonprimary_semantic_order_controls':1,'canonical_version_probe_evaluations':summary['probe_count'],
  'extra_schema_diagnostic_evaluations':1,'earlier_validation_replay_evaluations':63},
 'primary_subject_ids':[s['id'] for s in primary],
 'qualified_subject_ids':[s['id'] for s in subjects if not s['primary_eligible']],
 'scope':'Source-version reward-method dataset and evidence, not RL training data, analyzer results, whole-package replay or an unseen generalization benchmark.',
 'selection':'Three upstream reported bugs and two linked open repair heads; eight source-reviewed control modules yielded two primary controls and one qualified semantic-order control. Other candidates retained with rejection reasons.',
 'no_analyzer_change_or_model_run':True,'source_exposure':'All currently read source is development/exposed. Record exposure before designing an independent holdout.',
 'label_unit':'Function-contract pair; version pairs/probes correlated. Never count repaired variants or63probes as that many independent bugs.',
 'repair_scope':'PR561/562 are open and unmerged; relevant counterexamples pass, not global correctness proofs. No coin-flip scoring repair verified.',
 'group_anagrams_qualification':'List-of-dict groups receive full reward in a separate diagnostic; exclude from unqualified schema-safety negatives. This is contract-sensitive, not claimed as a confirmed newly reported upstream bug.'})
 with (ROOT/'case-table.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['id','function_family','primary_eligible','disposition','contract_id','source_file','probes','full_credit_violating_probes','evidence'])
  w.writeheader()
  for s in subjects:
   x=read(ROOT/s['execution_evidence']);w.writerow({k:s[k] for k in ['id','function_family','primary_eligible','disposition','contract_id','source_file']}|{'probes':len(x['probes']),'full_credit_violating_probes':x['full_credit_violating_probes'],'evidence':s['execution_evidence']})
 sources=[]
 for p in sorted((ROOT/'collection/source-provenance').rglob('*.json')):
  x=read(p);path=ROOT/x['local_path'];raw=path.read_bytes()
  assert sha(path)==x['sha256'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==x['git_blob_sha1']
  methods=[]
  if path.suffix=='.py':
   tree=ast.parse(path.read_text())
   def walk(nodes,prefix=''):
    for n in nodes:
     if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
      methods.append({'qualified_name':prefix+n.name,'ast_sha256':hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()});walk(n.body,prefix+n.name+'.')
     elif isinstance(n,ast.ClassDef):walk(n.body,prefix+n.name+'.')
   walk(tree.body)
  sources.append({'path':x['local_path'],'snapshot':x['snapshot'],'commit':x['commit'],'sha256':x['sha256'],'git_blob_sha1':x['git_blob_sha1'],'source_url':x['source_url'],'functions':methods})
 write(ROOT/'source-exposure-inventory.json',{'purpose':'Future studies must regard all these raw sources/callables and saved issue/PR snippets as exposed, including exclusions. No pretrained-model novelty claim.','sources':sources,'files':len(sources),'callable_occurrences':sum(len(s['functions']) for s in sources),'metadata_snippet_exposure':'collection/*commit.json,pr-*-files.json and issue/comment bodies may contain additional source snippets; retain them in exposure accounting.'})
 print(json.dumps({'archived_versions':len(subjects),'primary_versions':len(primary),'primary_normal_controls':2,'qualified_controls':1,'canonical_probes':63,'extra_diagnostic':1,'source_files':len(sources)}))
if __name__=='__main__':main()
