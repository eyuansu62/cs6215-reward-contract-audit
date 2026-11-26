"""Safely extract pinned Python blobs and inventory static task metadata only."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import ast
import copy
import hashlib
import importlib.util
import json
import re
import tarfile

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[3]
COMMIT = '49b07130b3fcd12f2d064bba7c43869543a0e7e7'


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


class WithoutScores(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        if node.name == 'score_answer': return None
        return self.generic_visit(node)


def main():
    tree = read(BASE/'experiments/reward-contract-extraction-v1/collection/tree.json')
    expected = {r['path']:r['sha'] for r in tree['tree'] if r.get('type')=='blob'}
    exposed = read(BASE/'datasets/reasoning-gym-reward-v1/source-exposure-inventory.json')['sources']
    prior = {r['path'].split('/reasoning_gym/',1)[-1] for r in exposed if '/reasoning_gym/' in r['path']}
    prior |= {str(p.relative_to(BASE/'experiments/reward-contract-extraction-v1/collection/sealed-upstream/reasoning_gym')) for p in (BASE/'experiments/reward-contract-extraction-v1/collection/sealed-upstream/reasoning_gym').rglob('*.py')}
    prior |= {str(p.relative_to(ROOT.parent/'sealed-upstream/reasoning_gym')) for p in (ROOT.parent/'sealed-upstream/reasoning_gym').rglob('*.py')}
    prior_fp = read(ROOT.parent/'prior-score-fingerprints.json')['records']
    spec = importlib.util.spec_from_file_location('_source_screen_util', ROOT.parent/'screen_sources.py'); util = importlib.util.module_from_spec(spec); spec.loader.exec_module(util)
    extractions = []; excluded = []; seen = set()
    prefix = 'reasoning-gym-'+COMMIT+'/'
    with tarfile.open(ROOT/'pinned-source.tar.gz','r:gz') as archive:
        for member in archive:
            name = member.name
            if not name.startswith(prefix): continue
            path = name[len(prefix):]
            posix = PurePosixPath(path)
            if posix.is_absolute() or '..' in posix.parts: raise ValueError('Unsafe archive path')
            if not path.startswith('reasoning_gym/') or not path.endswith('.py'): continue
            if ('contrib' in posix.parts or 'data' in posix.parts or 'rearc_utils' in posix.parts
                    or any(part.startswith('generators') for part in posix.parts)):
                excluded.append({'path':path,'reason':'vendored/rearc/generator/data exclusion'});continue
            if path.endswith('__init__.py'):
                excluded.append({'path':path,'reason':'package initializer not a task source'});continue
            if not member.isfile() or member.issym() or member.islnk(): raise ValueError('Nonregular Python member')
            if path not in expected or path in seen: raise ValueError('Unpinned/duplicate Python path')
            if member.size > 5000000: raise ValueError('Unexpected huge Python blob')
            data = archive.extractfile(member).read()
            blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if blob != expected[path]: raise ValueError('Git blob mismatch: '+path)
            target=ROOT/'raw-source'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);seen.add(path)
            extractions.append({'path':path,'git_blob_sha1':blob,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'previous_content_exposed_before_census':path.split('reasoning_gym/',1)[1] in prior})
    classes=[]
    for record in extractions:
        path=record['path'];text=(ROOT/'raw-source'/path).read_text();module=ast.parse(text)
        for cls in module.body:
            if not isinstance(cls,ast.ClassDef) or not cls.name.endswith('Dataset'): continue
            own=next((n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='score_answer'),None)
            prompt_view=WithoutScores().visit(copy.deepcopy(module));fragments=[]
            for node in ast.walk(prompt_view):
                if isinstance(node,ast.Constant) and type(node.value) is str and re.search(r'\b(?:True|False|[Bb]oolean)\b',node.value):
                    fragments.append({'span':[node.lineno,node.end_lineno],'text':node.value})
            functions=[n.name for n in cls.body if isinstance(n,ast.FunctionDef)]
            rows={'path':path,'class':cls.name,'bases':[ast.unparse(x) for x in cls.bases],'owns_score_answer':own is not None,'methods':functions,'candidate_boolean_text':bool(fragments),'question_or_generator_literal_matches':fragments,'previous_content_exposed_before_census':record['previous_content_exposed_before_census']}
            if own:
                rows['score_span']=[own.lineno,own.end_lineno];rows['score_ast_sha256']=hashlib.sha256(ast.dump(own,include_attributes=False).encode()).hexdigest();rows['alpha_implementation_sha256']=util.fingerprint(own)
                rows['alpha_matches_prior_exposed_score']=any(rows['alpha_implementation_sha256']==r['alpha_implementation_sha256'] for r in prior_fp)
            classes.append(rows)
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'commit':COMMIT,'archive_sha256':sha(ROOT/'pinned-source.tar.gz'),'tree_sha256':sha(BASE/'experiments/reward-contract-extraction-v1/collection/tree.json'),'extracted_python_blobs':len(extractions),'all_git_blob_hashes_verified':True,'sources':extractions,'excluded':excluded,'source_execution':False}
    (ROOT/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    census={'created_utc':datetime.now(timezone.utc).isoformat(),'commit':COMMIT,'scope':'Static class/own-score metadata plus non-score string literals. No method/target/model/analyzer execution. Text matches are candidate hints, not domain conclusions.','task_dataset_classes':len(classes),'own_score_classes':sum(r['owns_score_answer'] for r in classes),'boolean_text_classes':sum(r['candidate_boolean_text'] for r in classes),'records':classes}
    (ROOT/'first-pass-metadata.json').write_text(json.dumps(census,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:census[k] for k in ['task_dataset_classes','own_score_classes','boolean_text_classes']}))
    for r in classes:
        if r['candidate_boolean_text']: print(json.dumps({'path':r['path'],'class':r['class'],'own_score':r['owns_score_answer'],'prior_exposed':r['previous_content_exposed_before_census'],'matches':r['question_or_generator_literal_matches']},ensure_ascii=False))


if __name__=='__main__': main()
