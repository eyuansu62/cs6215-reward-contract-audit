"""Static task-domain/own-scorer inventory. Never imports or executes upstream."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[2]
COMMIT = '49b07130b3fcd12f2d064bba7c43869543a0e7e7'


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


class AlphaNormalize(ast.NodeTransformer):
    def __init__(self): self.names = {}
    def name(self, value):
        if value not in self.names: self.names[value] = 'v'+str(len(self.names))
        return self.names[value]
    def visit_FunctionDef(self, node):
        node.name = 'FUNCTION'; node.returns = None; node.type_comment = None
        for argument in node.args.posonlyargs+node.args.args+node.args.kwonlyargs:
            argument.annotation = None; argument.arg = self.name(argument.arg)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and type(node.body[0].value.value) is str:
            node.body = node.body[1:]
        return self.generic_visit(node)
    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id=self.name(node.id), ctx=node.ctx), node)


def fingerprint(node):
    normalized = AlphaNormalize().visit(copy.deepcopy(node))
    return hashlib.sha256(ast.dump(normalized, include_attributes=False).encode()).hexdigest()


def score_record(path, cls, node, text):
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    closure = {}; pending = [node]
    external = set()
    while pending:
        current = pending.pop()
        if current.name in closure: continue
        closure[current.name] = current
        for child in ast.walk(current):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and isinstance(child.func.value, ast.Name) and child.func.value.id in {'self', cls.name}:
                target = child.func.attr
                if target in methods: pending.append(methods[target])
                else: external.add(target)
    source = ast.get_source_segment(text, node)
    return {'source_span': [node.lineno, node.end_lineno], 'exact_score_source': source,
            'score_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'score_ast_sha256': hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
            'alpha_implementation_sha256': fingerprint(node),
            'self_helper_closure': [{'name': name, 'span': [n.lineno, n.end_lineno], 'alpha_sha256': fingerprint(n)} for name, n in sorted(closure.items())],
            'unresolved_self_calls': sorted(external)}


def main():
    decisions = {
        'reasoning_gym/logic/syllogisms.py': ('Yes/No', 'No own score_answer; previously exposed default scorer is inherited. Native answer tokens Yes/No also fail unchanged True/False interface.', [('answer', "'Yes' if is_valid else 'No'")]),
        'reasoning_gym/logic/propositional_logic.py': ('propositional_expression', 'Answer is a proposed logical conclusion/expression, not a scalar True/False task; entry.answer is None. Own scorer uses expression validity/triviality.', [('answer', 'None')]),
        'reasoning_gym/logic/circuit_logic.py': ('0/1', 'Own scorer exists, but generated output is str(final_result) with final_result in integer 0/1. Unchanged interface requires canonical True/False; no encoding translation allowed.', [('answer', 'answer_str')]),
        'reasoning_gym/logic/self_reference.py': ('integer_solution_count', 'Question asks number of possible solutions and answer=str(len(solutions)); scalar truth values of puzzle statements are not the requested answer.', [('answer', 'answer')]),
        'reasoning_gym/logic/knights_knaves.py': ('name_role_assignment_set', 'Answer is names/knight-knave role assignments, not one Boolean token; scorer normalizes a set of assignments.', [('answer', 'answer')]),
        'reasoning_gym/induction/acre/acre.py': ('on/off/undetermined', 'Three-way detector status, not canonical Boolean tokens; also inherits previously exposed default scorer.', [('answer', 'answer')]),
    }
    prior = read(ROOT/'prior-score-fingerprints.json')['records']
    prior_hashes = {r['alpha_implementation_sha256'] for r in prior}
    records = []
    for path in read(ROOT/'screening-plan.json')['candidate_paths']:
        local = ROOT/'sealed-upstream'/path; text = local.read_text(); module = ast.parse(text)
        cls = next(c for c in module.body if isinstance(c, ast.ClassDef) and c.name.endswith('Dataset'))
        score = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='score_answer'), None)
        domain, reason, fields = decisions[path]
        field_evidence = []
        for node in ast.walk(cls):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == 'answer':
                        field_evidence.append({'span': [value.lineno, value.end_lineno], 'expression': ast.get_source_segment(text, value)})
        record = {'path': path, 'commit': COMMIT, 'source_sha256': sha(local),
                  'class': cls.name, 'bases': [ast.unparse(x) for x in cls.bases],
                  'native_answer_domain': domain, 'canonical_True_False': False,
                  'owns_score_answer': score is not None, 'eligible': False, 'reason': reason,
                  'answer_field_evidence': field_evidence, 'prior_full_content_exposed_before_screen': False,
                  'filename_previously_listed': True}
        if score:
            record['score'] = score_record(path, cls, score, text)
            record['score']['alpha_matches_prior'] = record['score']['alpha_implementation_sha256'] in prior_hashes
        else:
            record['inherited_scorer'] = 'Previously exposed ProceduralDataset.score_answer in reasoning_gym/dataset.py'
        records.append(record)
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'commit': COMMIT,
              'candidate_module_contents_screened': len(records), 'eligible_distinct_new_TrueFalse_scorers': 0,
              'selected': [], 'records': records, 'selection_status': 'infeasible_within_six_fixed_candidates',
              'scope_limit': 'Not an exhaustive claim about all Reasoning Gym versions/tasks; no additional module inspected yet.',
              'model_requests': 0, 'analyzer_runs': 0, 'upstream_execution': False,
              'no_encoding_translation_or_function_rewriting': True,
              'next_step': 'Parent decides whether bounded screening should use remaining two candidates; no replacement or broadened experiment has occurred.'}
    (ROOT/'screening-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (ROOT/'source-exposure-inventory.json').write_text(json.dumps({'purpose': 'All saved candidate modules are now exposed; exclude in future fresh-content studies, even rejected modules.',
        'sources': [{'path': r['path'], 'sha256': r['source_sha256'], 'commit': COMMIT, 'disposition': 'excluded_from_current_fixed_interface'} for r in records],
        'prior_filename_exposure': True, 'model_pretraining_novelty_not_established': True}, indent=2)+'\n')
    print(json.dumps({'screened': len(records), 'eligible': 0, 'selected': [], 'source_executed': False}))


if __name__=='__main__': main()
