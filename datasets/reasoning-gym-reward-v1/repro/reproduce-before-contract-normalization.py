"""Replay exact extracted scoring methods on curated witnesses, without installing RG.

This is dataset label validation, not a static analyzer or RL experiment. A small
AST/namespace guard and subprocess timeout restrict these inspected excerpts; this
is not a general-purpose sandbox for arbitrary upstream Python.
"""
from pathlib import Path
import __future__
import argparse
import ast
import builtins
import collections
import copy
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from source_extract import extract_function
ROOT=Path(__file__).resolve().parents[1]

class ScopeError(BaseException):pass
SAFE_NAMES=('abs','all','any','bool','complex','dict','enumerate','float','int','isinstance','len','list','max','min','range','reversed','set','sorted','str','sum','tuple','zip','staticmethod','classmethod','Exception','ValueError','TypeError','ZeroDivisionError','IndexError','KeyError')
SAFE_BUILTINS={n:getattr(builtins,n) for n in SAFE_NAMES}
SAFE_ATTRIBUTES={'strip','lower','replace','startswith','endswith','split','append','extend','join','exp','isfinite','prod','loads','dumps'}
GLOBAL_VALUES={'math':math,'json':json,'Fraction':Fraction}

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def normalized(value):
 if type(value) is float and not math.isfinite(value):return {'nonfinite_float':'nan' if math.isnan(value) else 'inf' if value>0 else '-inf'}
 if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [normalized(v) for v in value]
 return value

def inspect_excerpt(text,globals_,helper_names):
 node=ast.parse(text).body[0]
 if not isinstance(node,ast.FunctionDef):raise ScopeError('Not a synchronous method')
 if any(not isinstance(d,ast.Name) or d.id not in {'staticmethod','classmethod'} for d in node.decorator_list):raise ScopeError('Unapproved decorator')
 for arg in [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]:
  if arg.annotation and any(isinstance(n,(ast.Call,ast.Lambda,ast.NamedExpr)) for n in ast.walk(arg.annotation)):raise ScopeError('Effectful annotation')
 defaults=[*node.args.defaults,*[v for v in node.args.kw_defaults if v is not None]]
 if any(not isinstance(v,ast.Constant) for v in defaults):raise ScopeError('Nonliteral defaults')
 body=ast.Module(body=node.body,type_ignores=[])
 forbidden=(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.With,ast.AsyncWith,ast.Await,ast.Yield,ast.ClassDef)
 if any(isinstance(n,forbidden) for n in ast.walk(body)):raise ScopeError('Unsupported inspected excerpt effect')
 bound={a.arg for n in ast.walk(node) if isinstance(n,(ast.FunctionDef,ast.Lambda)) for a in [*n.args.posonlyargs,*n.args.args,*n.args.kwonlyargs]}
 bound.update(n.id for n in ast.walk(body) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store))
 bound.update(n.name for n in ast.walk(body) if isinstance(n,ast.ExceptHandler) and n.name)
 for n in ast.walk(body):
  if isinstance(n,ast.Name) and n.id.startswith('__'):raise ScopeError('Reflection/dunder namespace')
  if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id not in bound|set(SAFE_BUILTINS)|set(globals_):raise ScopeError('Unbound global: '+n.id)
  if isinstance(n,ast.Attribute) and n.attr not in SAFE_ATTRIBUTES|set(helper_names):raise ScopeError('Unapproved attribute: '+n.attr)
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id not in set(SAFE_BUILTINS)|set(globals_)|bound:raise ScopeError('Unapproved call')
 return node

def score(subject,probe):
 source_path=ROOT/subject['source_file'];assert sha(source_path)==subject['source_sha256']
 module=source_path.read_text();env={'__builtins__':SAFE_BUILTINS,'__name__':'inspected_scoring_excerpt'}
 for name in subject['globals']:
  if name not in GLOBAL_VALUES:raise ScopeError('Global is not an allowed stdlib object: '+name)
  env[name]=GLOBAL_VALUES[name]
 cls=type(subject['class'],(),{});env[subject['class']]=cls
 for record in subject['extracted_methods']:
  path=ROOT/record['source_path'];assert sha(path)==record['source_sha256']
  text,proof=extract_function(module,subject['class']+'.'+record['name'])
  assert text==path.read_text() and proof['ast_identity_verified']
  inspect_excerpt(text,env,subject['helpers'])
  code=compile(text,str(path),'exec',flags=__future__.annotations.compiler_flag,dont_inherit=True)
  exec(code,env,env)
  setattr(cls,record['name'],env[record['name']])
 instance=cls.__new__(cls) # No upstream constructor/generator or class body.
 entry=copy.deepcopy(probe['entry']);before=copy.deepcopy(entry)
 value=getattr(instance,subject['method'])(probe['answer'],entry)
 if type(value) not in {float,int}:raise ScopeError('Scorer did not return a native numeric reward')
 return {'kind':'returned','reward':normalized(value),'python_type':type(value).__name__,
         'entry_unchanged':entry==before,'source_AST_identity_verified':True,
         'upstream_module_imported':False,'upstream_constructor_or_generator_executed':False}

def relation(reward,expectation):
 if expectation is None:return None
 if type(reward) not in {int,float} or not math.isfinite(reward):return False
 checks=[]
 if 'equals' in expectation:checks.append(math.isclose(reward,expectation['equals'],rel_tol=0,abs_tol=1e-12))
 if 'less_than' in expectation:checks.append(reward<expectation['less_than'])
 if 'strictly_between' in expectation:
  low,high=expectation['strictly_between'];checks.append(low<reward<high)
 if 'formula' in expectation:
  if expectation['formula']!='exp(-1)':raise ValueError('Unknown independently stated formula')
  checks.append(math.isclose(reward,math.exp(-1),rel_tol=0,abs_tol=1e-12))
 if not checks:raise ValueError('Empty reward expectation')
 return all(checks)

def full_credit_allowed(subject,probe):
 """Independent, narrow task predicates. Never calls the target score/helper."""
 family=subject['family_id'];answer=probe['answer'];entry=probe['entry']
 if family=='rg-issue-544':
  normalized_answer=answer.strip().lower() if isinstance(answer,str) else None
  return normalized_answer in {'true','false'} and normalized_answer==entry['answer'].strip().lower()
 if family=='rg-issue-543':
  try:
   a=float(Fraction(answer.replace(',','')));g=float(Fraction(entry['answer'].replace(',','')))
   return math.isfinite(a) and math.isfinite(g) and abs(a-g)<=1e-4
  except (ValueError,ZeroDivisionError,TypeError,AttributeError):return False
 if family=='rg-issue-545':
  # This family's primary contract is nonfinite-answer rejection, not a claim
  # of exact real-arithmetic equivalence for every finite partial score.
  try:
   z=complex(answer.replace(' ','').replace('i','j'))
   return math.isfinite(z.real) and math.isfinite(z.imag)
  except (ValueError,TypeError,AttributeError):return False
 if 'PalindromeDataset' in family:
  if not isinstance(answer,str):return False
  a=answer.strip().lower()
  return bool(a) and a==a[::-1] and collections.Counter(a)==collections.Counter(entry['metadata']['letters'])
 if 'GroupAnagramsDataset' in family:
  try:
   a=json.loads(answer);g=entry['metadata']['solution']
   if not isinstance(a,list) or not all(isinstance(group,list) and all(type(w)is str for w in group) for group in a):return False
   canon=lambda groups:collections.Counter(tuple(sorted(group)) for group in groups)
   return canon(a)==canon(g)
  except (ValueError,TypeError):return False
 if 'PrimeFactorizationDataset' in family:
  try:
   values=[int(t.strip()) for t in answer.split('×') if t.strip()]
   expected=[int(t.strip()) for t in entry['answer'].split('×') if t.strip()]
   def prime(n):return n>=2 and all(n%d for d in range(2,math.isqrt(n)+1))
   return bool(values) and all(prime(n) for n in values) and math.prod(values)==math.prod(expected)
  except (ValueError,TypeError,AttributeError):return False
 raise ValueError('No independent declared predicate for family '+family)

def worker(case,probe_id):
 resource.setrlimit(resource.RLIMIT_CPU,(2,3))
 data=read(ROOT/'repro/replay-inputs.json');s=next(s for s in data['subjects'] if s['id']==case);p=next(p for p in s['probes'] if p['id']==probe_id)
 try:result=score(s,p)
 except ScopeError as error:result={'kind':'scope_rejected','error':str(error)}
 except Exception as error:result={'kind':'target_exception','exception_class':type(error).__name__,'message':str(error)}
 print(json.dumps(normalized(result),ensure_ascii=False,allow_nan=False))

def replay(output):
 if output.exists():raise ValueError('Preserve previous replay; use a new directory')
 output.mkdir(parents=True)
 data=read(ROOT/'repro/replay-inputs.json');rows=[]
 env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0','PYTHONNOUSERSITE':'1','LC_ALL':'C.UTF-8'}
 for s in data['subjects']:
  results=[]
  for p in s['probes']:
   argv=[sys.executable,'-I','-B',str(Path(__file__).resolve()),'worker','--case',s['id'],'--probe',p['id']]
   result=subprocess.run(argv,capture_output=True,text=True,timeout=8,env=env)
   if result.returncode:raise RuntimeError('Worker failed: '+s['id']+'/'+p['id']+': '+result.stderr[:500])
   observed=json.loads(result.stdout);reward=observed.get('reward');source_match=relation(reward,p['source_behavior_expectation'])
   allowed=full_credit_allowed(s,p)
   violates=observed['kind']=='returned' and type(reward) in {float,int} and reward>=1 and not allowed
   row={'id':p['id'],'role':p['role'],'answer':p['answer'],'entry':p['entry'],'observed':observed,
        'expected_source_behavior':p['source_behavior_expectation'],'source_behavior_matches':source_match,
        'declared_contract_expectation':p['contract_expectation'],'declared_expectation_satisfied':relation(reward,p['contract_expectation']),
        'independent_full_credit_predicate_satisfied':allowed,'full_credit_contract_violation_observed':violates,
        'original_bug_probe':p['intended_original_bug_probe'],'command':argv,'stderr':result.stderr}
   results.append(row)
  record={'id':s['id'],'family_id':s['family_id'],'kind':s['kind'],'source_file':s['source_file'],'source_sha256':s['source_sha256'],
          'extracted_methods':s['extracted_methods'],'evidence_level':'extracted_real_method_executed',
          'all_source_expectations_matched':all(p['source_behavior_matches'] for p in results),
          'full_credit_violating_probes':sum(p['full_credit_contract_violation_observed'] for p in results),'probes':results}
  (output/(s['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n');rows.append(record)
 summary={'created_utc':datetime.now(timezone.utc).isoformat(),'purpose':'Dataset evidence validation only; no analyzer, Semgrep, LLM, RL training or full RG package execution.',
  'python':sys.version,'platform':platform.platform(),'subjects':len(rows),'function_families':len({r['family_id'] for r in rows}),
  'probe_count':sum(len(r['probes']) for r in rows),'all_source_expectations_matched':all(r['all_source_expectations_matched'] for r in rows),
  'known_bug_originals_reproduced':sum(r['kind']=='reported_bug_original' and r['full_credit_violating_probes']>0 for r in rows),
  'proposed_repairs_without_observed_full_credit_violation':sum(r['kind']!='reported_bug_original' and r['kind']!='normal_control' and r['full_credit_violating_probes']==0 for r in rows),
  'normal_control_subjects':sum(r['kind']=='normal_control' for r in rows),
  'violating_probes':sum(r['full_credit_violating_probes'] for r in rows),'unexpected_worker_outcomes':[{'subject':r['id'],'probe':p['id'],'outcome':p['observed']} for r in rows for p in r['probes'] if p['observed']['kind']!='returned'],
  'assurance':'Exact real scoring/helper ASTs in an isolated, AST/namespace-scoped stdlib harness; not full-package/generator reproduction, exhaustive proof or a general secure code sandbox.',
  'annotations_deferred':True,'upstream_constructors_modules_and_generators_executed':False,'new_dependencies':False,
  'new_analyzer_or_model_runs':0,'replay_inputs_sha256':sha(ROOT/'repro/replay-inputs.json'),'reproducer_sha256':sha(Path(__file__)),'subjects_results':[{'id':r['id'],'probes':len(r['probes']),'source_expectations_match':r['all_source_expectations_matched'],'full_credit_violations':r['full_credit_violating_probes']} for r in rows]}
 (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
 if not summary['all_source_expectations_matched'] or summary['unexpected_worker_outcomes']:sys.exit(1)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['worker','replay']);p.add_argument('--case');p.add_argument('--probe');p.add_argument('--output',type=Path)
 a=p.parse_args()
 if a.operation=='worker':worker(a.case,a.probe)
 else:
  if a.output is None:p.error('replay requires --output new directory')
  replay(a.output.resolve())
