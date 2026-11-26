"""Prepare exact static scorer units after description/model freezes. No imports of targets."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
OLD_DATA = WORKSPACE / 'datasets/reasoning-gym-reward-v1'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    if path.exists():
        raise ValueError(f'Preserve earlier preparation output: {path}')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def named_class(tree, name):
    matches = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name]
    if len(matches) != 1:
        raise ValueError(f'Class not unique: {name}')
    return matches[0]


def methods(cls):
    return {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def fragment(source, node):
    # Only the declaration's leading indentation is omitted. Interior bytes,
    # including string/docstring values, are untouched. Verify full AST identity.
    text = ast.get_source_segment(source, node)
    parsed = ast.parse(text)
    if len(parsed.body) != 1 or ast.dump(parsed.body[0]) != ast.dump(node):
        raise ValueError('Extraction would alter the function AST')
    return text


def bindings(tree):
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in sys.stdlib_module_names:
                    out[alias.asname or alias.name.split('.')[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            if node.module.split('.')[0] in sys.stdlib_module_names:
                for alias in node.names:
                    if alias.name != '*':
                        out[alias.asname or alias.name] = f'{node.module}.{alias.name}'
    return out


def self_calls(fn):
    return sorted({n.func.attr for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and isinstance(n.func.value, ast.Name) and n.func.value.id == 'self'})


def returns_without_nested(fn):
    out = []
    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not fn:
            return
        if isinstance(node, ast.Return):
            out.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)
    visit(fn)
    return out


def bool_expr(expr):
    if isinstance(expr, ast.Constant):
        return type(expr.value) is bool
    if isinstance(expr, ast.Compare):
        return True
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        return True
    return False


def canonical_boolean_evidence(task_id, source, cls):
    if task_id not in {'T01', 'T02', 'T03'}:
        return {'confirmed': False, 'reason': 'Task is not a Boolean-output family.'}
    meth = methods(cls)
    getitem = meth.get('__getitem__')
    if not getitem:
        return {'confirmed': False, 'reason': 'Missing native generator.'}
    body = getitem.body
    returned = [n for n in body if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)]
    if len(returned) != 1 or body[-1] is not returned[0]:
        return {'confirmed': False, 'reason': 'Generator reference schema not simple and total at tail.'}
    pairs = list(zip(returned[0].value.keys, returned[0].value.values))
    value = next((v for k, v in pairs if isinstance(k, ast.Constant) and k.value == 'answer'), None)
    if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'str'
            and len(value.args) == 1 and isinstance(value.args[0], ast.Name) and not value.keywords):
        return {'confirmed': False, 'reason': 'Reference is not native str of generator Boolean.'}
    local = value.args[0].id
    assignments = [n for n in body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == local for t in n.targets)]
    if len(assignments) != 1:
        return {'confirmed': False, 'reason': 'Generator reference local has ambiguous bindings.'}
    call = assignments[0].value
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name) and call.func.value.id == 'self'
            and call.func.attr in meth):
        return {'confirmed': False, 'reason': 'Generator reference producer not a declared method.'}
    producer = meth[call.func.attr]
    exits = returns_without_nested(producer)
    if (not exits or not isinstance(producer.body[-1], ast.Return)
            or not all(bool_expr(n.value) for n in exits)
            or any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(producer))):
        return {'confirmed': False, 'reason': 'Producer lacks a complete Boolean normal-return certificate.'}
    # Native str and parameters must not be lexically rebound in this generator.
    stores = {n.id for n in ast.walk(getitem) if isinstance(n, ast.Name)
              and isinstance(n.ctx, (ast.Store, ast.Del))}
    if 'str' in stores or 'str' in bindings(ast.parse(source)) or 'str' in meth:
        return {'confirmed': False, 'reason': 'Native str binding is not established.'}
    return {'confirmed': True,
            'argument': 'Generator entry.answer is native str(answer); answer is the result of the displayed helper. Every helper normal return is a native Boolean expression and a final unconditional Boolean return excludes implicit None. Thus generated reference strings are exactly True or False, conditional on normal generation. This does not prove the task solver itself correct.',
            'generator_assignment_span': [assignments[0].lineno, assignments[0].end_lineno],
            'generator_assignment_source': ast.get_source_segment(source, assignments[0]),
            'entry_answer_span': [value.lineno, value.end_lineno],
            'entry_answer_source': ast.get_source_segment(source, value),
            'producer_name': producer.name,
            'producer_span': [producer.lineno, producer.end_lineno],
            'producer_exact_source': fragment(source, producer),
            'producer_return_spans': [[n.lineno, n.end_lineno] for n in exits]}


def main():
    if not (ROOT.parent / 'results/model-response-freeze.json').is_file():
        raise ValueError('Model outputs must be sealed before scorer source preparation')
    frozen = read(ROOT / 'description-packet-freeze.json')
    for name, expected in frozen['files_sha256'].items():
        assert sha(ROOT / name) == expected, name
    records = read(ROOT / 'description-source-fragments.json')['records']
    private = read(ROOT / 'task-provenance-private.json')['tasks']
    by_path = {r['path']: r for r in records}
    old_inventory = read(OLD_DATA / 'source-exposure-inventory.json')['sources']
    base_record = next(x for x in old_inventory if x['path'] == 'upstream/main/reasoning_gym/dataset.py')
    base_path = OLD_DATA / base_record['path']
    assert sha(base_path) == base_record['sha256']
    base_source = base_path.read_text()
    base_tree = ast.parse(base_source)
    base_cls = named_class(base_tree, 'ProceduralDataset')
    base_methods = methods(base_cls)
    units, provenance, evidence = [], [], []
    for item in private:
        record = by_path[item['path']]
        local = ROOT / 'sealed-upstream' / item['path']
        assert sha(local) == record['source_sha256']
        source = local.read_text()
        tree = ast.parse(source)
        class_name = next(f['class'] for f in record['safe_description_fragments']
                          if f['kind'] == 'task_class_docstring')
        cls = named_class(tree, class_name)
        own = methods(cls)
        inherited = 'score_answer' not in own
        errors = []
        if inherited and [ast.unparse(b) for b in cls.bases] != ['ProceduralDataset']:
            errors.append('Unsupported inherited scorer resolution')
        available = {name: (node, base_source, base_path, base_tree, 'ProceduralDataset')
                     for name, node in base_methods.items()}
        available.update({name: (node, source, local, tree, class_name) for name, node in own.items()})
        resolved = available.get('score_answer')
        if resolved is None:
            raise ValueError(f'No exact native scorer for {item["task_id"]}')
        score, score_module, score_path, score_tree, owner = resolved
        visited, visiting, ordered = set(), set(), []
        def collect(name):
            if name in visiting:
                errors.append('Recursive self-helper call graph is outside preparation support')
                return
            if name in visited:
                return
            if name not in available:
                errors.append('Unresolved self helper: ' + name)
                return
            visiting.add(name)
            node, module, path, module_tree, origin = available[name]
            for callee in self_calls(node):
                collect(callee)
            visiting.remove(name)
            visited.add(name)
            if name != 'score_answer':
                ordered.append((name, node, module, path, module_tree, origin))
        collect('score_answer')
        score_text = fragment(score_module, score)
        helpers = [{'name': name, 'source': fragment(module, node)}
                   for name, node, module, *_ in ordered]
        full = '\n'.join([h['source'] for h in helpers] + [score_text])
        env = {}
        participating = [(score, score_tree)] + [(x[1], x[4]) for x in ordered]
        for node, module_tree in participating:
            for alias, target in bindings(module_tree).items():
                if alias in env and env[alias] != target:
                    errors.append('Conflicting inherited/helper standard-library binding: ' + alias)
                env[alias] = target
            if node.decorator_list or isinstance(node, ast.AsyncFunctionDef):
                errors.append('Decorated/asynchronous callable is unsupported')
            for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
                if isinstance(call.func, ast.Name) and call.func.id in {'eval', 'exec', 'getattr', 'setattr', 'delattr'}:
                    errors.append('Dynamic callable semantics retained without execution: ' + call.func.id)
        args = score.args.posonlyargs + score.args.args
        fixed = {}
        for arg, default in zip(args[-len(score.args.defaults):], score.args.defaults):
            if arg.arg not in {'self', 'answer', 'entry'}:
                if isinstance(default, ast.Constant) and type(default.value) in {str, int, float, bool, type(None)}:
                    fixed[arg.arg] = default.value
                else:
                    errors.append('Nonliteral public default parameter: ' + arg.arg)
        proof = canonical_boolean_evidence(item['task_id'], source, cls)
        evidence.append({'task_id': item['task_id'], 'source_path': item['path'],
                         'source_sha256': record['source_sha256'], **proof})
        errors = list(dict.fromkeys(errors))
        units.append({'task_id': item['task_id'], 'entry_name': 'score_answer',
                      'source': full, 'score_source': score_text, 'helpers': helpers,
                      'stdlib_bindings': env, 'fixed_parameters': fixed,
                      'trusted_reference_canonical_boolean': proof['confirmed'],
                      'source_preparation': {'status': 'unknown' if errors else 'complete',
                                             'unsupported_reasons': errors}})
        provenance.append({'task_id': item['task_id'], 'task_class': class_name,
                           'task_source_path': item['path'], 'task_source_sha256': sha(local),
                           'scorer_qualified_name': owner + '.score_answer',
                           'scorer_inherited': inherited,
                           'scorer_previously_exposed': inherited,
                           'scorer_origin_path': str(score_path.relative_to(WORKSPACE)),
                           'scorer_origin_sha256': sha(score_path),
                           'scorer_span': [score.lineno, score.end_lineno],
                           'scorer_ast_sha256': hashlib.sha256(ast.dump(score).encode()).hexdigest(),
                           'score_fragment_sha256': hashlib.sha256(score_text.encode()).hexdigest(),
                           'combined_source_sha256': hashlib.sha256(full.encode()).hexdigest(),
                           'helpers': [{'name': name, 'origin_class': origin,
                                        'source_path': str(path.relative_to(WORKSPACE)),
                                        'source_span': [node.lineno, node.end_lineno],
                                        'fragment_sha256': hashlib.sha256(fragment(module, node).encode()).hexdigest()}
                                       for name, node, module, path, _, origin in ordered],
                           'source_preparation': units[-1]['source_preparation']})
    dump(ROOT / 'source-units.json', {'units': units, 'target_sources_executed': False,
                                     'scorer_ast_identity_verified': True})
    dump(ROOT / 'source-unit-provenance.json', {'units': provenance,
         'distinct_scorer_bodies': len({p['scorer_ast_sha256'] for p in provenance}),
         'previously_exposed_shared_scorer_units': sum(p['scorer_inherited'] for p in provenance),
         'source_units_sha256': sha(ROOT / 'source-units.json')})
    dump(ROOT / 'canonical-reference-evidence.json', {'units': evidence,
        'normal_generation_only': True, 'task_solver_correctness_not_proved': True,
        'not_provided_to_description_extractor': True})
    print(json.dumps({'units': len(units), 'distinct_scorer_bodies': len({p['scorer_ast_sha256'] for p in provenance}),
                      'inherited_previously_exposed_scorer_units': sum(p['scorer_inherited'] for p in provenance),
                      'canonical_boolean_confirmed': [e['task_id'] for e in evidence if e['confirmed']],
                      'source_preparation_unknown': [u['task_id'] for u in units if u['source_preparation']['status'] == 'unknown'],
                      'target_code_executed': False}, indent=2))


if __name__ == '__main__':
    main()
