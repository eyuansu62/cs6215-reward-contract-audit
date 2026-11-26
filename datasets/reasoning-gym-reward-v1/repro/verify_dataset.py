"""Offline integrity/AST verification; does not execute scoring methods."""
from pathlib import Path
import ast,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from source_extract import extract_function
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 manifest=read(ROOT/'dataset-freeze.json')
 for name,expected in manifest['files_sha256'].items():
  path=(ROOT/name).resolve();assert path.is_relative_to(ROOT) and path.is_file(),name
  assert sha(path)==expected,name
 inputs=read(ROOT/'repro/replay-inputs.json');methods=0
 for s in inputs['subjects']:
  path=ROOT/s['source_file'];assert sha(path)==s['source_sha256']
  for m in s['extracted_methods']:
   text,proof=extract_function(path.read_text(),s['class']+'.'+m['name'])
   assert proof['ast_identity_verified'] and text==(ROOT/m['source_path']).read_text()
   assert sha(ROOT/m['source_path'])==m['source_sha256'];methods+=1
 sources=read(ROOT/'source-exposure-inventory.json')
 refs=read(ROOT/'collection/refs.json')['refs']
 for s in sources['sources']:
  p=ROOT/s['path'];raw=p.read_bytes();assert sha(p)==s['sha256']
  assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==s['git_blob_sha1']
  tree=read(ROOT/'collection'/f"{s['snapshot']}-tree.json")
  prefix='upstream/'+s['snapshot']+'/'
  relative=s['path'][len(prefix):];assert any(x['path']==relative and x['sha']==s['git_blob_sha1'] for x in tree['tree'])
  assert refs[s['snapshot']]['commit']==s['commit']
 summary=read(ROOT/'results/replay-02/summary.json');assert summary['all_source_expectations_matched'] and summary['known_bug_originals_reproduced']==3 and not summary['unexpected_worker_outcomes']
 assert summary['reproducer_sha256']==sha(ROOT/'repro/reproduce.py')
 for n in [561,562]:
  pr=read(ROOT/'collection'/f'pr-{n}.json');assert pr['merged'] is False and pr['merged_at'] is None
 d=read(ROOT/'dataset.json');assert d['counts']['primary_source_versions']==7 and len(d['qualified_subject_ids'])==1
 diagnostic=read(ROOT/'results/schema-boundary-diagnostic.json');assert diagnostic['observed']['reward']==1.0 and not diagnostic['strict_list_of_lists_predicate_satisfied']
 print(json.dumps({'passed':True,'frozen_files':len(manifest['files_sha256']),'source_files':len(sources['sources']),'exact_method_ASTs':methods,'primary_versions':7,'qualified_versions':1,'canonical_probes':63,'extra_diagnostic':1,'scoring_methods_executed_by_this_verify':False,'new_dependencies_or_network':False},indent=2))
if __name__=='__main__':main()
