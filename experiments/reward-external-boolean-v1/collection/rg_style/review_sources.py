"""Static curation of RG-style external source candidates; no subject execution."""
from pathlib import Path
from datetime import datetime,timezone
import ast,copy,hashlib,json
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[3]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def norm(node):
 node=copy.deepcopy(node)
 for item in ast.walk(node):
  if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)):
   item.returns=None;item.type_comment=None
   if item.body and isinstance(item.body[0],ast.Expr) and isinstance(item.body[0].value,ast.Constant) and type(item.body[0].value.value) is str:item.body=item.body[1:]
  elif isinstance(item,ast.arg):item.annotation=None;item.type_comment=None
 return ast.dump(node,include_attributes=False)

def methods(path):
 text=path.read_text();tree=ast.parse(text)
 return [{'name':node.name,'span':[node.lineno,node.end_lineno],
          'arguments':[x.arg for x in node.args.posonlyargs+node.args.args],
          'async':isinstance(node,ast.AsyncFunctionDef),
          'source':ast.get_source_segment(text,node),
          'full_ast_sha256':hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),
          'without_docs_annotations_ast_sha256':hashlib.sha256(norm(node).encode()).hexdigest()}
         for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(x in node.name for x in ('score','reward','submit_answer'))]

def main():
 originals=[]
 for folder in [BASE/'experiments/reward-boolean-holdout-v1/collection/census/raw-source', BASE/'datasets/reasoning-gym-reward-v1/upstream/pr561']:
  for path in folder.rglob('*.py'):
   for node in ast.walk(ast.parse(path.read_text())):
    if isinstance(node,ast.FunctionDef) and node.name=='score_answer':
     originals.append({'path':str(path.relative_to(BASE)),'normalized':norm(node)})
 provenance=read(ROOT/'candidate-sources.json')['records'];rows=[]
 for rec in provenance:
  repo=rec['repo'];folder=ROOT/'raw'/repo.replace('/','__');sources=[]
  for path in sorted(folder.rglob('*.py')):
   functions=methods(path)
   for f in functions:
    # Exact doc/annotation-insensitive comparison only; no global-name alpha rewrite.
    tree=ast.parse(f['source']);n=tree.body[0]
    f['exact_implementation_matches_previous']=[r['path'] for r in originals if r['normalized']==norm(n)]
   sources.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'functions':functions})
  reasons={
    'EnvCommons/ReasoningGym':['Real binary_score wrapper has dataset,answer,entry, but returns (reward,raw_score), invokes dataset scorer and text/number helper; extracting reward component would change boundary.','submit_answer is async/self-stateful and returns ToolOutput. Isomorphic task class delegates to inherited framework; no independent scalar callback selected.'],
    'huggingface/OpenEnv':['step(action,timeout_s) is a stateful environment method, obtains score from self._dataset.score_answer; no independent answer/entry Boolean scorer.'],
    'NousResearch/atropos':['Environment scoring wraps reasoning_gym.create_dataset plus dataset.score_answer and tag parsing; async/stateful orchestration, not an independent native scalar True/False callback.'],
    'apple/ml-multilingual-reasoning-gym':['Default scorer and reseeding delegator match previous RG implementation after removing docs/annotations.','GoL normalization implementation differs in source but is the already-exposed same task/scorer family; language-localized answer domain also cannot be assumed canonical True/False across configurations.'],
    'researchim-ai/reasoning-gym-ru':['Modified default scorer adds strip/0.01 branches but remains the forked known generic scorer family; not counted as an independent task scorer.','Reseeding delegator exactly matches previously exposed implementation; GoL path absent at pinned commit.']}
  rows.append({'repository':repo,'commit':rec['commit'],'eligible':False,'selection':'excluded','reasons':reasons[repo],'source_records':sources})
 result={'created_utc':datetime.now(timezone.utc).isoformat(),'lane':'RG-style external callbacks','repositories':5,'initial_path_attempts':12,'path_correction_fetches':2,'successful_text_files':12,'failed_initial_paths':2,
         'selected':[],'eligible_functions':0,'records':rows,'subject_imports_or_execution':False,'model_or_analyzer_calls':0,
         'dedup_note':'Doc/annotation-insensitive AST equality preserves all identifiers. It establishes some exact copies, not general semantic equivalence. Remaining known-family/wrapper exclusions are source-reviewed.',
         'snapshot_note':'Each repository HEAD resolved to a commit before content fetch. No release/current-state guarantee beyond observed pins.'}
 (ROOT/'source-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'repositories':5,'selected':0,'actual_python_source_files':sum(len(x['source_records']) for x in rows),'subject_execution':False}))
if __name__=='__main__':main()
