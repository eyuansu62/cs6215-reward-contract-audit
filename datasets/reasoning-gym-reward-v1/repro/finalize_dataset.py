"""Seal a data-curation snapshot; no analyzer/model is run."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,x):
 if p.exists():raise ValueError('Preserve existing dataset evidence: '+str(p))
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 freeze=ROOT/'dataset-freeze.json';archive=ROOT.with_suffix('.zip')
 if freeze.exists() or archive.exists():raise ValueError('Dataset already sealed; do not overwrite')
 d=read(ROOT/'dataset.json');inputs=read(ROOT/'repro/replay-inputs.json')
 current=read(ROOT/'results/replay-02/summary.json');prior=read(ROOT/'results/replay-01/summary.json')
 assert current['all_source_expectations_matched'] and current['known_bug_originals_reproduced']==3
 assert current['proposed_repairs_without_observed_full_credit_violation']==2 and current['violating_probes']==9
 assert not current['unexpected_worker_outcomes'] and current['probe_count']==63
 assert current['reproducer_sha256']==sha(ROOT/'repro/reproduce.py')
 review=read(ROOT/'audit/independent-review.json');assert not review['blocking_findings']
 obs=0;changes=[]
 for s in inputs['subjects']:
  a=read(ROOT/'results/replay-01'/(s['id']+'.json'));b=read(ROOT/'results/replay-02'/(s['id']+'.json'))
  assert len(a['probes'])==len(b['probes'])
  for x,y in zip(a['probes'],b['probes']):
   assert x['id']==y['id'] and x['answer']==y['answer'] and x['entry']==y['entry'] and x['observed']==y['observed']
   obs+=1
   if x['full_credit_contract_violation_observed']!=y['full_credit_contract_violation_observed']:changes.append(s['id']+'/'+x['id'])
 assert obs==63 and len(changes)==2 and all('equivalent-parentheses' in x for x in changes)
 refs=read(ROOT/'collection/refs.json')['refs'];sources=read(ROOT/'source-exposure-inventory.json')['sources']
 for alias,ref in refs.items():
  commitfile={'main':'main-commit.json','issue_snapshot':'issue-commit.json'}.get(alias,alias+'-commit.json')
  c=read(ROOT/'collection'/commitfile);t=read(ROOT/'collection'/(alias+'-tree.json'))
  assert c['sha']==ref['commit'] and c['commit']['tree']['sha']==ref['tree'] and not t.get('truncated')
 for s in sources:
  p=ROOT/s['path'];raw=p.read_bytes();assert sha(p)==s['sha256']
  assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==s['git_blob_sha1']
  tree=read(ROOT/'collection'/(s['snapshot']+'-tree.json'))
  relative=s['path'].split('upstream/'+s['snapshot']+'/',1)[1]
  assert any(n['path']==relative and n['sha']==s['git_blob_sha1'] for n in tree['tree'])
 for n in [561,562]:
  p=read(ROOT/'collection'/f'pr-{n}.json');assert not p['merged'] and p['merged_at'] is None
  files=read(ROOT/'collection'/f'pr-{n}-files.json');assert len(files)==p['changed_files']
 # Source registration/import graph is evidence, not an actual package import.
 rootinit=(ROOT/'upstream/main/reasoning_gym/__init__.py').read_text();registry=[]
 for family,category in [('CoinFlipDataset','probability'),('GameOfLifeHaltingDataset','algorithmic'),('ComplexArithmeticDataset','algebra'),('PalindromeDataset','algorithmic'),('PrimeFactorizationDataset','arithmetic'),('GroupAnagramsDataset','algorithmic')]:
  assert category in rootinit
  path=ROOT/f'upstream/main/reasoning_gym/{category}/__init__.py';assert family in path.read_text()
  subject=next(s for s in inputs['subjects'] if s['class']==family)
  tree=ast.parse((ROOT/subject['source_file']).read_text())
  calls=[n.value for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='register_dataset']
  assert any(len(n.args)>1 and isinstance(n.args[1],ast.Name) and n.args[1].id==family for n in calls)
  registry.append({'class':family,'category_import':str(path.relative_to(ROOT)),'source_registration_checked':True,'package_import_executed':False})
 v10=WORKSPACE/'outputs/main-experiment-v10';method=read(v10/'method-freeze.json')
 assert sha(v10/'method-freeze.json')=='56c4a850fbf9440e5356eaf3571d3a2a98434da105769d1cf078b239eed6ef11'
 for name,expected in method['files_sha256'].items():assert sha(v10/name)==expected
 assert sha(WORKSPACE/'outputs/main-experiment-v10.zip')=='1ec556817897134f2c9f46f53ef9771caf251ef2394998c604aa00f9a391ed32'
 now=datetime.now(timezone.utc).isoformat()
 write_new(ROOT/'audit/final-curation-checks.json',{'created_utc':now,'passed':True,'primary_versions':7,'qualified_versions':1,'primary_function_families':5,'archived_function_families':6,
 'canonical_version_probe_evaluations':63,'separate_schema_diagnostic_evaluations':1,'prior_validation_round_evaluations':63,
 'actual_rewards_unchanged_across_validation_rounds':63,'corrected_contract_flags':changes,'reported_bug_families_reproduced':3,
 'open_upstream_repair_candidates':2,'source_blobs_verified':len(sources),'source_import_registration_evidence':registry,
 'no_full_package_import_generators_training_or_analyzer_calls':True,'new_dependencies_installed':False,'v10_method_files_unchanged':len(method['files_sha256']),
 'v10_archive_unchanged':True,'all_current_source_is_development_exposed':True,'normal_scope':'Only named contracts; GroupAnagrams excluded from general schema-safety negatives; no global clean claim.',
 'fix_scope':'Unmerged proposals with closure of covered witnesses, not released fixes or complete correctness proof.'})
 paths=sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='.DS_Store')
 files={str(p.relative_to(ROOT)):sha(p) for p in paths}
 write_new(freeze,{'created_utc':now,'files_sha256':files,'file_count':len(files),'scope':'Single-project source-exposed reward-method development/feasibility corpus; no classifier results or generalization claim.',
 'contains_reviewed_contracts_labels_and_witnesses':True,'not_a_model_request_projection':True,'primary_versions':7,'qualified_versions':1,'no_analyzer_changes':True})
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in [*paths,freeze]:z.write(p,ROOT.name+'/'+str(p.relative_to(ROOT)))
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None and len(z.namelist())==len(files)+1
  for name,expected in files.items():assert hashlib.sha256(z.read(ROOT.name+'/'+name)).hexdigest()==expected,name
  assert z.read(ROOT.name+'/dataset-freeze.json')==freeze.read_bytes()
 result={'archive':str(archive),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'manifest_sha256':sha(freeze),'manifest_files':len(files),'all_hashes_and_zip_CRC_verified':True,
 'primary_versions':7,'qualified_versions':1,'canonical_probes':63,'extra_diagnostic':1,'analyzer_changed':False,'v10_unchanged':True}
 archive.with_suffix('.zip.sha256').write_text(result['archive_sha256']+'  '+archive.name+'\n')
 write_new(archive.with_suffix('.package-check.json'),result)
 print(json.dumps(result))
if __name__=='__main__':main()
