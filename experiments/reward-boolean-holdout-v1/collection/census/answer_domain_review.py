"""Second static pass: answer-field traces and conservative implementation hashes."""
from pathlib import Path
from datetime import datetime,timezone
import ast,copy,hashlib,json
ROOT=Path(__file__).resolve().parent

def read(p):return json.loads(p.read_text())
def digest(n):return hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()

class Strip(ast.NodeTransformer):
 def visit_FunctionDef(self,n):
  n.returns=None;n.type_comment=None
  for a in n.args.posonlyargs+n.args.args+n.args.kwonlyargs:a.annotation=None
  if n.body and isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Constant) and type(n.body[0].value.value)is str:n.body=n.body[1:]
  return self.generic_visit(n)

class Locals(ast.NodeVisitor):
 def __init__(self,fn):self.bound={a.arg for a in fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs};self.external=set()
 def visit_Name(self,n):
  if isinstance(n.ctx,(ast.Store,ast.Del)):self.bound.add(n.id)
 def visit_Global(self,n):self.external.update(n.names)
 def visit_Nonlocal(self,n):self.external.update(n.names)
 def visit_FunctionDef(self,n):self.bound.add(n.name)
 def visit_AsyncFunctionDef(self,n):self.bound.add(n.name)
 def visit_ClassDef(self,n):self.bound.add(n.name)
 def visit_Lambda(self,n):pass
 def visit_ListComp(self,n):pass
 def visit_SetComp(self,n):pass
 def visit_DictComp(self,n):pass
 def visit_GeneratorExp(self,n):pass
 def visit_ExceptHandler(self,n):
  if n.name:self.bound.add(n.name)
  self.generic_visit(n)

class AlphaLocal(ast.NodeTransformer):
 def __init__(self,names):self.names={};self.allowed=names
 def rename(self,name):
  if name not in self.allowed:return name
  if name not in self.names:self.names[name]='LOCAL'+str(len(self.names))
  return self.names[name]
 def visit_Name(self,n):return ast.copy_location(ast.Name(id=self.rename(n.id),ctx=n.ctx),n)
 def visit_arg(self,n):n.arg=self.rename(n.arg);return n
 def visit_FunctionDef(self,n):return n # Do not claim nested-scope alpha-equivalence.
 def visit_ClassDef(self,n):return n
 def visit_Lambda(self,n):return n
 def visit_ListComp(self,n):return n
 def visit_SetComp(self,n):return n
 def visit_DictComp(self,n):return n
 def visit_GeneratorExp(self,n):return n
 def visit_ExceptHandler(self,n):
  if n.name:n.name=self.rename(n.name)
  return self.generic_visit(n)

def fingerprints(fn):
 normalized=Strip().visit(copy.deepcopy(fn));normalized.name='FUNCTION'
 scope=Locals(normalized)
 for stmt in normalized.body:scope.visit(stmt)
 local=AlphaLocal(scope.bound-scope.external);alpha=copy.deepcopy(normalized)
 for a in alpha.args.posonlyargs+alpha.args.args+alpha.args.kwonlyargs:local.visit_arg(a)
 alpha.body=[local.visit(stmt) for stmt in alpha.body]
 return {'doc_annotation_removed_ast_sha256':digest(normalized),'alpha_lexical_local_sha256':digest(alpha),'preserves_global_builtin_attribute_names':True}

def main():
 metadata=read(ROOT/'first-pass-metadata.json');rows=[]
 for r in metadata['records']:
  text=(ROOT/'raw-source'/r['path']).read_text();module=ast.parse(text);cls=next(c for c in module.body if isinstance(c,ast.ClassDef)and c.name==r['class']);methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
  getter=methods.get('__getitem__');assignments={};answers=[]
  if getter:
   for n in ast.walk(getter):
    if isinstance(n,ast.Assign):
     for t in n.targets:
      if isinstance(t,ast.Name):assignments.setdefault(t.id,[]).append(n.value)
   for n in ast.walk(getter):
    if isinstance(n,ast.Dict):
     for k,v in zip(n.keys,n.values):
      if isinstance(k,ast.Constant)and k.value=='answer':answers.append(v)
  traces=[]
  def trace(n,depth=0):
   entry={'expression':ast.unparse(n),'span':[n.lineno,n.end_lineno]}
   if depth>3:return entry
   if isinstance(n,ast.Name)and n.id in assignments:entry['assignments']=[trace(v,depth+1)for v in assignments[n.id]]
   if isinstance(n,ast.Call):
    if isinstance(n.func,ast.Name)and n.func.id=='str'and len(n.args)==1:entry['stringifies']=trace(n.args[0],depth+1)
    if isinstance(n.func,ast.Attribute)and isinstance(n.func.value,ast.Name)and n.func.value.id=='self'and n.func.attr in methods:
     f=methods[n.func.attr];entry['self_producer']={'name':f.name,'return_annotation':ast.unparse(f.returns)if f.returns else None,'return_expressions':[ast.unparse(x.value)for x in ast.walk(f)if isinstance(x,ast.Return)]}
   return entry
  traces=[trace(n)for n in answers]
  row={'path':r['path'],'class':r['class'],'owns_score_answer':r['owns_score_answer'],'previous_content_exposed_before_census':r['previous_content_exposed_before_census'],'answer_field_traces':traces}
  if 'score_answer'in methods:row['conservative_implementation_fingerprints']=fingerprints(methods['score_answer'])
  rows.append(row)
 result={'created_utc':datetime.now(timezone.utc).isoformat(),'purpose':'Answer-field structural trace to supplement text-hint pass, not runtime type inference or proof. No functions executed.','records':rows,'dedup_limit':'Conservative hashes preserve global/builtin/member names; alpha-equivalence is heuristic and any eligible collision requires source/helper review.'}
 (ROOT/'answer-field-traces.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'task_classes_traced':len(rows),'own_scoring_fingerprints':sum('conservative_implementation_fingerprints'in r for r in rows)}))
 for r in rows:
  text=json.dumps(r['answer_field_traces'])
  if any(token in text for token in ['True','False',"\"return_annotation\": \"bool\"",'not should_oscillate']):print(json.dumps(r,ensure_ascii=False))

if __name__=='__main__':main()
