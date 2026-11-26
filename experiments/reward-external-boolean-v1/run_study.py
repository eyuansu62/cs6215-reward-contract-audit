"""Frozen native-source study runner; no model calls or analyzer extensions.

The concrete worker executes only inspected, hash-pinned extracted definitions.
It is a bounded reproduction harness, not a sandbox for arbitrary Python.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import __future__
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import resource
import string
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from native_binding import analyze_bound, check_witness_bound, validate_binding, verify_frozen
from boolean_contracts import compile_contract, evaluate_witness

SEMGREP_FILE = ROOT.parent/'reward-baselines-v1/tools/semgrep_baseline.py'
SEMGREP_SHA = '49d44d8f9a8d6691de3c4024f270fa5670fb4db0fdcf0288da839c43c78ab92e'
BINDING_SHA = 'd2a4c32e807352ead28e98d9aa73767ce2aa7d006481e8db4451dd0342a03328'
VERDICTS = {'alarm', 'no_alarm', 'unknown'}
ANALYZER_FIELDS = ('entry_name', 'source', 'score_source', 'helpers', 'stdlib_bindings',
                   'fixed_parameters', 'trusted_reference_canonical_boolean')
SAFE_BUILTINS = {name: getattr(__import__('builtins'), name) for name in (
    'str', 'set', 'len', 'bool', 'int', 'float', 'list', 'tuple', 'dict',
    'enumerate', 'zip', 'range', 'any', 'all', 'isinstance',
    'Exception', 'TypeError', 'ValueError')}
SAFE_ATTRIBUTES = {'strip', 'lower', 'split', 'join', 'startswith', 'sub', 'punctuation'}
STDLIB = {'re': re, 'string': string}


class NativeScopeError(ValueError):
    """The inspected source or input does not meet this worker's boundary."""


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def object_sha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def unit_id(unit):
    value = unit.get('id', unit.get('task_id'))
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
        raise ValueError('Unit ID must be a path-safe string')
    return value


def load_units():
    units = read(ROOT/'data/source-units.json')['units']
    ids = [unit_id(unit) for unit in units]
    if len(ids) != len(set(ids)) or not ids: raise ValueError('Unique nonempty source units required')
    return units


def load_probes():
    probes = read(ROOT/'data/probes.json')['probes']
    ids = [probe['id'] for probe in probes]
    if len(ids) != len(set(ids)) or any(type(i) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]+', i) for i in ids):
        raise ValueError('Probe IDs must be unique path-safe strings')
    for probe in probes: validate_probe(probe)
    return probes


def validate_probe(probe):
    answer, reference = probe['answer'], probe['reference']
    if answer is not None and (type(answer) is not str or len(answer) > 200):
        raise ValueError('Concrete candidate must be native str<=200 characters or None')
    if type(reference) is not str or reference not in {'True', 'False'}:
        raise ValueError('Concrete reference must be canonical native True/False string')
    return answer, reference


def applies(unit, probe):
    return 'unit_ids' not in probe or unit_id(unit) in probe['unit_ids']


def previous_integrity():
    """Verify frozen imported modules and preserved prior payload manifests."""
    verify_frozen()
    if sha(ROOT/'native_binding.py') != BINDING_SHA or sha(SEMGREP_FILE) != SEMGREP_SHA:
        raise ValueError('Frozen binding or Semgrep module changed')
    manifests = [ROOT.parent/'reward-boolean-holdout-v1/artifact-files-sha256.json']
    if not manifests[0].exists():
        manifests = [ROOT.parent/'reward-contract-e2e-v1/artifact-files-sha256.json']
    checked = 0
    records = {}
    for path in manifests:
        for name, digest in read(path)['files_sha256'].items():
            if sha(BASE/name) != digest: raise ValueError('Prior payload changed: '+name)
            checked += 1
        records[str(path.relative_to(BASE))] = sha(path)
    return {'binding_sha256': BINDING_SHA, 'semgrep_sha256': SEMGREP_SHA,
            'frozen_theory': verify_frozen(), 'previous_manifests_sha256': records,
            'previous_payloads_verified': checked}


def method_files():
    paths = [*ROOT.glob('*.py'), *(ROOT/'tests').glob('*.py'),
             *(ROOT/'protocol').glob('*'), ROOT/'binding-method-freeze.json']
    for path in (ROOT/'data').glob('*'):
        # Actual LLM condition values are sealed after the model call, not
        # available or needed when this method/input preparation is frozen.
        if path.name != 'condition-contracts.json' and path.is_file(): paths.append(path)
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(set(paths)) if path.is_file()}


def source_packet(unit):
    """Validate exact selected definition ASTs against the pinned raw source."""
    source = unit.get('all_source', unit.get('source'))
    if type(source) is not str or source != unit.get('source'):
        raise ValueError('Native all_source/source must be identical text')
    definitions = unit.get('definitions')
    if type(definitions) is not list or not definitions: raise ValueError('Exact definition records required')
    original_path = BASE/unit['original_source_file']
    if sha(original_path) != unit['original_source_sha256']:
        raise ValueError('Native original source hash mismatch')
    original = original_path.read_text(); original_tree = ast.parse(original)
    original_defs = {node.name: node for node in original_tree.body if isinstance(node, ast.FunctionDef)}
    tree = ast.parse(source)
    if any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError('Native packet contains non-definition module effects')
    packet_defs = {node.name: node for node in tree.body}
    if len(packet_defs) != len(tree.body): raise ValueError('Duplicate native function definitions')
    declared = {}
    for record in definitions:
        name, fragment = record['name'], record['source']
        if (name in declared or name not in original_defs or fragment not in original
                or source.count(fragment) != 1):
            raise ValueError('Native fragment is not one exact upstream definition')
        fragment_tree = ast.parse(fragment)
        if len(fragment_tree.body) != 1 or not isinstance(fragment_tree.body[0], ast.FunctionDef):
            raise ValueError('Invalid native fragment')
        node = fragment_tree.body[0]
        dump = ast.dump(node, include_attributes=False)
        if (node.name != name or ast.dump(original_defs[name], include_attributes=False) != dump
                or name not in packet_defs or ast.dump(packet_defs[name], include_attributes=False) != dump):
            raise ValueError('Native function AST identity mismatch')
        if record.get('ast_sha256') not in {None, hashlib.sha256(dump.encode()).hexdigest()}:
            raise ValueError('Declared native AST hash mismatch')
        declared[name] = node
    if set(declared) != set(packet_defs) or unit['entry_name'] not in declared:
        raise ValueError('Native declared source scope mismatch')
    if unit['score_source'] != next(r['source'] for r in definitions if r['name'] == unit['entry_name']):
        raise ValueError('Scorer bytes differ from exact declared fragment')
    score_tree = ast.parse(unit['score_source'])
    if (len(score_tree.body) != 1 or ast.dump(score_tree.body[0], include_attributes=False)
            != ast.dump(declared[unit['entry_name']], include_attributes=False)):
        raise ValueError('Exact scorer fragment mismatch')
    return source, tree, declared


def freeze():
    path = ROOT/'method-freeze.json'
    if path.exists(): raise ValueError('Preserve earlier method freeze')
    units, probes = load_units(), load_probes()
    for unit in units: source_packet(unit)
    reference = read(ROOT/'data/reference-contract.json')['contract']
    if reference is not None: compile_contract(reference)
    write(path, {'created_utc': datetime.now(timezone.utc).isoformat(),
        'files_sha256': method_files(), 'preserved_previous': previous_integrity(),
        'source_units_sha256': sha(ROOT/'data/source-units.json'),
        'probes_sha256': sha(ROOT/'data/probes.json'),
        'frozen_before_primary_model_and_analyzer_outputs': True,
        'units': len(units), 'probe_definitions': len(probes),
        'method_scope': 'Native binding and input packaging only; no analyzer operations or obligation predicates added'})
    return {'passed': True, 'method_freeze_sha256': verify()}


def verify():
    frozen = read(ROOT/'method-freeze.json')
    if method_files() != frozen['files_sha256']: raise ValueError('Frozen study method or data changed')
    if previous_integrity() != frozen['preserved_previous']: raise ValueError('Previous preserved payload changed')
    for unit in load_units(): source_packet(unit)
    return sha(ROOT/'method-freeze.json')


def load_conditions():
    seal = read(ROOT/'results/model-response-freeze.json')
    if seal.get('method_freeze_sha256') != verify(): raise ValueError('Model seal has a different study method')
    sealed_files = seal['files_sha256']
    if 'data/condition-contracts.json' not in sealed_files:
        raise ValueError('Condition contracts must be bound by the model-response freeze')
    for name, digest in sealed_files.items():
        if sha(ROOT/name) != digest: raise ValueError('Sealed model/condition file changed: '+name)
    conditions = read(ROOT/'data/condition-contracts.json')['conditions']
    if set(conditions) != {'reference', 'llm'}: raise ValueError('Exactly reference and llm conditions required')
    reference = read(ROOT/'data/reference-contract.json')['contract']
    if object_sha(conditions['reference']) != object_sha(reference):
        raise ValueError('Reference condition differs from pre-model freeze')
    model_folder = (ROOT/seal['model_output']).resolve()
    model_folder.relative_to(ROOT.resolve())
    def sealed_artifact(name, required=True):
        path = model_folder/name
        relative = str(path.relative_to(ROOT.resolve()))
        if relative not in sealed_files:
            if required: raise ValueError('Model artifact not covered by response seal: '+name)
            return None
        return read(path)
    metadata = sealed_artifact('metadata.json')
    status = metadata.get('status')
    if status == 'complete':
        raw = sealed_artifact('response.json'); accepted = sealed_artifact('accepted-contract.json')
        if raw.get('status') != 'extracted' or raw.get('contract') is None:
            raise ValueError('Complete model metadata does not match raw extraction')
        if (object_sha(conditions['llm']) != object_sha(raw['contract'])
                or object_sha(conditions['llm']) != object_sha(accepted.get('contract'))):
            raise ValueError('LLM condition differs from sealed raw/accepted contract')
    elif status in {'abstained', 'failed'}:
        if conditions['llm'] is not None:
            raise ValueError('Abstained or rejected model condition must remain null')
        raw = sealed_artifact('response.json', required=status == 'abstained')
        if status == 'abstained' and (raw.get('status') != 'abstain' or raw.get('contract') is not None):
            raise ValueError('Abstained model metadata does not match raw response')
        accepted = sealed_artifact('accepted-contract.json', required=False)
        if accepted is not None and accepted.get('contract') is not None:
            raise ValueError('Rejected or abstained model retains an active accepted contract')
    else:
        raise ValueError('Unrecognized sealed model status')
    for contract in conditions.values():
        if contract is not None: compile_contract(contract)
    return conditions


def guard_native_source(tree, declared, bindings):
    """Bound the vetted excerpt namespace; do not import its original module."""
    if type(bindings) is not dict or any(name not in STDLIB or target != name for name, target in bindings.items()):
        raise ValueError('Only declared native re/string standard modules are admitted')
    forbidden = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.With,
                 ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom, ast.ClassDef,
                 ast.AsyncFunctionDef, ast.Delete)
    if any(isinstance(node, forbidden) for node in ast.walk(tree)):
        raise ValueError('Native excerpt effect outside inspected execution boundary')
    bound = set(declared)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.Lambda)):
            if isinstance(node, ast.FunctionDef):
                if node.decorator_list: raise ValueError('Native excerpt decorators unsupported')
                bound.add(node.name)
            bound.update(a.arg for a in node.args.posonlyargs+node.args.args+node.args.kwonlyargs)
            if node.args.vararg or node.args.kwarg: raise ValueError('Native variadic signature unsupported')
            for default in [*node.args.defaults, *[d for d in node.args.kw_defaults if d is not None]]:
                if not isinstance(default, ast.Constant): raise ValueError('Native nonliteral default unsupported')
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store): bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name: bound.add(node.name)
    available = bound | set(SAFE_BUILTINS) | set(bindings)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id.startswith('__'): raise ValueError('Native dunder/reflection name unsupported')
            if isinstance(node.ctx, ast.Load) and node.id not in available:
                raise ValueError('Native unknown global: '+node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith('__') or node.attr not in SAFE_ATTRIBUTES:
                raise ValueError('Native attribute outside inspected whitelist: '+node.attr)
            if not isinstance(node.ctx, ast.Load): raise ValueError('Native attribute mutation unsupported')
    return {'status': 'inspected_exact_definitions', 'module_imported': False,
            'namespace_is_general_sandbox': False}


def native_arguments(function, binding, answer, reference):
    """Bind only original parameters/one-level mapping fields, with no encoding conversion."""
    values = {}
    for role, value in [('candidate', answer), ('reference', reference)]:
        selector = binding[role]; parameter, field = selector['parameter'], selector['field']
        if field is None: values[parameter] = value
        else: values.setdefault(parameter, {})[field] = value
    args, kwargs = [], {}
    for parameter in function.args.posonlyargs:
        if parameter.arg not in values: raise ValueError('Unbound native positional-only parameter')
        args.append(values.pop(parameter.arg))
    kwargs.update(values)
    return args, kwargs


def execute_native(unit, probe):
    """Execute a selected, inspected original scoring function for reproduction only."""
    try:
        answer, reference = validate_probe(probe)
        source, tree, declared = source_packet(unit)
        binding = validate_binding(unit['native_binding'], {'score_source': unit['score_source']})
        guard = guard_native_source(tree, declared, unit['stdlib_bindings'])
    except (ValueError, OSError, SyntaxError, KeyError, TypeError) as error:
        raise NativeScopeError(str(error)) from error
    env = {'__builtins__': SAFE_BUILTINS, '__name__': 'inspected_native_scalar_metric'}
    env.update({name: STDLIB[name] for name in unit['stdlib_bindings']})
    code = compile(source, str(BASE/unit['original_source_file']), 'exec',
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)
    exec(code, env, env)
    before = copy.deepcopy((answer, reference))
    args, kwargs = native_arguments(declared[unit['entry_name']], binding, answer, reference)
    value = env[unit['entry_name']](*args, **kwargs)
    if (type(value) not in (int, float)
            or type(value) is float and not math.isfinite(value)):
        raise NativeScopeError('Native scalar reward required; no result coercion or extraction')
    if (answer, reference) != before: raise ValueError('Native scalar witness changed')
    return {'kind': 'returned', 'reward': value, 'python_type': type(value).__name__,
            'source_AST_identity_verified': True, 'source_rewritten': False,
            'answer_encoding_converted': False, 'reward_coerced': False,
            'upstream_module_imported': False, 'upstream_constructor_or_generator_executed': False,
            'native_definition_names': list(declared), 'execution_guard': guard}


def worker(uid, pid):
    verify()
    resource.setrlimit(resource.RLIMIT_CPU, (2, 3))
    units, probes = load_units(), load_probes()
    unit = next(u for u in units if unit_id(u) == uid)
    probe = next(p for p in probes if p['id'] == pid)
    if not applies(unit, probe): raise ValueError('Probe not assigned to selected unit')
    try: result = execute_native(unit, probe)
    except NativeScopeError as error:
        result = {'kind': 'scope_rejected', 'exception_class': type(error).__name__, 'message': str(error)}
    except Exception as error:
        result = {'kind': 'target_exception', 'exception_class': type(error).__name__, 'message': str(error)}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


def semgrep_module():
    if sha(SEMGREP_FILE) != SEMGREP_SHA: raise ValueError('Preserved Semgrep module changed')
    spec = importlib.util.spec_from_file_location('_preserved_native_source_pattern_baseline', SEMGREP_FILE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def scan_semgrep(unit, output):
    """Unfiltered native CE search on exact selected definitions; same rules/engine."""
    output = Path(output).resolve()
    if output.exists(): raise ValueError('Preserve earlier Semgrep output')
    output.mkdir(parents=True)
    result = {'method': 'pinned_semgrep_CE_same_rules_native_source_packager',
        'verdict': 'unknown', 'status': 'error', 'errors': [],
        'source_rewritten': False, 'source_executed': False,
        'semantics_proved': False, 'source_semantics_filtering': False,
        'qualification': 'Same native CE/rules as frozen baseline; source packager accepts original native signatures and definition packets. No_alarm is no pattern, not contract proof.'}
    start = time.perf_counter()
    try:
        source, tree, _declared = source_packet(unit); sg = semgrep_module()
        path = output/'source.py'; path.write_bytes(source.encode())
        core = sg.find_core()
        proc = sg._execute([str(core), '-version'], output, 'engine', 20)
        if proc.returncode or not re.search(r'\b'+re.escape(sg.PINNED_VERSION)+r'\b', proc.stdout):
            raise ValueError('Pinned native Semgrep version invocation failed')
        result['engine'] = {'version': proc.stdout.strip(), 'sha256': sha(core), 'path': str(core)}
        coverage, command, digest = sg._scan(core, sg.coverage_rules(), path, output, 'coverage')
        functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        if len(functions) != sum(isinstance(node, ast.FunctionDef) for node in ast.walk(tree)):
            raise ValueError('Duplicate nested function names outside coverage wrapper')
        result['coverage'] = sg._coverage(tree, functions, coverage)
        result['coverage'].update(command=command, rule_sha256=digest)
        findings, command, digest = sg._scan(core, sg.risky_rules(), path, output, 'scan')
        result.update(command=command, rule_sha256=digest, source_sha256=sha(path),
                      all_findings=findings, findings=findings,
                      verdict='alarm' if findings else 'no_alarm', status='complete')
    except (ValueError, OSError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError) as error:
        result['errors'].append(type(error).__name__+': '+str(error))
    result['wall_seconds'] = round(time.perf_counter()-start, 6)
    write(output/'result.json', result)
    return result


def analyzer_unit(unit):
    return {field: copy.deepcopy(unit[field]) for field in ANALYZER_FIELDS}


def _assert_determinate_matches(source, oracle, reward):
    if source['verdict'] == 'unknown': return False
    for key in ['verdict', 'active_obligations', 'per_obligation', 'violated_obligations']:
        if source.get(key) != oracle.get(key): raise ValueError('Determinate static/actual mismatch: '+key)
    if source.get('reward') != reward: raise ValueError('Determinate static reward differs from native execution')
    return True


def compare_concrete_oracles(reference, model):
    allowed = {'full_credit_violation', 'no_violation_for_this_witness'}
    eligible = reference.get('verdict') in allowed and model.get('verdict') in allowed
    left = set(reference.get('violated_obligations', []))
    right = set(model.get('violated_obligations', []))
    return {'native_oracle_comparable': eligible,
            'same_native_oracle_violated_ids': left == right if eligible else None,
            'reference_violation_ids_not_expressed_by_model': sorted(left-right) if eligible else None,
            'extra_model_violation_ids': sorted(right-left) if eligible else None}


def run(output):
    frozen_sha = verify(); conditions = load_conditions(); units, probes = load_units(), load_probes()
    output = Path(output).resolve()
    if output.exists(): raise ValueError('Preserve earlier study output')
    output.mkdir(parents=True)
    global_rows, semgrep_rows, by_key = [], [], {}
    for unit in units:
        uid = unit_id(unit)
        sg = scan_semgrep(unit, output/'semgrep'/uid)
        semgrep_rows.append({'unit_id': uid, **sg})
        for condition, contract in conditions.items():
            # Neither data probes, observed reward, expected labels nor condition
            # provenance are part of the source analyzer's arguments.
            result = analyze_bound(analyzer_unit(unit), copy.deepcopy(contract), copy.deepcopy(unit['native_binding']))
            if result.get('verdict') not in VERDICTS: raise ValueError('Unexpected analyzer verdict')
            if contract is not None:
                if result['active_obligations'] != contract['obligations']:
                    raise ValueError('Actual analyzer obligations differ from selected contract')
                if result['compiled_contract'] != contract:
                    raise ValueError('Analyzer completed or changed selected contract')
            global_rows.append({'unit_id': uid, 'condition': condition, **result}); by_key[uid, condition] = result
            write(output/'global'/uid/(condition+'.json'), result)
    observations, witness_rows = [], []
    for unit in units:
        uid = unit_id(unit)
        for probe in probes:
            if not applies(unit, probe): continue
            pid = probe['id']; folder = output/'native'/uid/pid; folder.mkdir(parents=True)
            command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), 'worker', '--unit', uid, '--probe', pid]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=8)
            (folder/'stdout.txt').write_text(proc.stdout); (folder/'stderr.txt').write_text(proc.stderr)
            write(folder/'command.json', {'argv': command, 'returncode': proc.returncode, 'timeout_seconds': 8})
            if proc.returncode: raise ValueError('Native worker process failed: '+proc.stderr)
            observed = json.loads(proc.stdout)
            observations.append({'unit_id': uid, 'probe_id': pid, 'answer': probe['answer'], 'reference': probe['reference'], 'observed': observed})
            if observed['kind'] != 'returned':
                witness_rows.append({'unit_id': uid, 'probe_id': pid, 'native_status': observed['kind'],
                    'conditions': {}, 'classification': 'No numeric normal-return reward; not treated as full credit.'})
                continue
            decisions = {}
            for condition, contract in conditions.items():
                oracle = evaluate_witness(contract, probe['answer'], probe['reference'], observed['reward'])
                result = check_witness_bound(analyzer_unit(unit), copy.deepcopy(contract), copy.deepcopy(unit['native_binding']), probe['answer'], probe['reference'])
                supported = _assert_determinate_matches(result, oracle, observed['reward'])
                if contract is not None:
                    if oracle['active_obligations'] != contract['obligations']:
                        raise ValueError('Oracle changed selected obligations')
                    if any(r['obligation_id'] not in contract['obligations'] for r in oracle['per_obligation']):
                        raise ValueError('Oracle reports inactive obligation')
                decisions[condition] = {'source_check': result, 'native_reward_oracle': oracle,
                                       'static_determinate_verified_against_native': supported}
            ref, llm = decisions['reference'], decisions['llm']
            witness_rows.append({'unit_id': uid, 'probe_id': pid, 'answer': probe['answer'], 'reference': probe['reference'],
                'native_reward': observed['reward'], 'native_status': 'returned', 'conditions': decisions,
                'same_static_verdict': (ref['source_check']['verdict'] == llm['source_check']['verdict'])
                    if ref['source_check']['verdict'] != 'unknown' and llm['source_check']['verdict'] != 'unknown' else None,
                'both_static_determinate': ref['source_check']['verdict'] != 'unknown' and llm['source_check']['verdict'] != 'unknown',
                **compare_concrete_oracles(ref['native_reward_oracle'], llm['native_reward_oracle']),
                'interpretation': 'Strict-profile compatibility check, not a confirmed upstream reward bug or policy violation.'})
    counts = {condition: {verdict: sum(r['verdict'] == verdict for r in global_rows if r['condition'] == condition)
                         for verdict in ['alarm', 'no_alarm', 'unknown']} for condition in conditions}
    witness_counts = {condition: {verdict: sum(r['conditions'].get(condition, {}).get('source_check', {}).get('verdict') == verdict for r in witness_rows)
                                  for verdict in ['full_credit_violation', 'no_violation_for_this_witness', 'unknown']} for condition in conditions}
    oracle_eligible = sum(r.get('native_oracle_comparable', False) for r in witness_rows)
    oracle_matches = sum(r.get('same_native_oracle_violated_ids') is True for r in witness_rows)
    static_eligible = sum(r.get('both_static_determinate', False) for r in witness_rows)
    result = {'passed': True, 'method_freeze_sha256': frozen_sha,
        'model_response_freeze_sha256': sha(ROOT/'results/model-response-freeze.json'),
        'origin_output': str(output),
        'condition_contracts_sha256': sha(ROOT/'data/condition-contracts.json'),
        'global_results': global_rows, 'semgrep_results': semgrep_rows, 'witness_rows': witness_rows,
        'summary': {'source_units': len(units), 'probe_definitions': len(probes),
            'native_executions': len(observations), 'returned_native_rewards': sum(x['observed']['kind'] == 'returned' for x in observations),
            'global_verdict_counts': counts, 'witness_static_verdict_counts': witness_counts,
            'semgrep_verdict_counts': {v: sum(r['verdict'] == v for r in semgrep_rows) for v in ['alarm', 'no_alarm', 'unknown']},
            'paired_native_oracle_eligible': oracle_eligible,
            'paired_native_oracle_violated_id_matches': oracle_matches if oracle_eligible else None,
            'paired_native_oracle_violated_id_mismatches': oracle_eligible-oracle_matches if oracle_eligible else None,
            'paired_both_static_determinate': static_eligible,
            'paired_static_verdict_matches': sum(r.get('same_static_verdict') is True for r in witness_rows) if static_eligible else None},
        'bug_precision_recall': None,
        'bug_metric_reason': 'No adjudicated bug oracle: native metric leniency is a declared policy; report strict-profile incompatibilities separately.',
        'target_code_executed_by_static_analyzers': False, 'model_calls_by_runner': 0,
        'condition_origin_or_oracles_passed_to_global_analyzers': False,
        'new_analyzer_semantics': False, 'source_rewriting': False,
        'qualifications': ['One-project correlated metric policies are not multiple independent projects.',
                           'Concrete reward oracle and static witness checking share existing obligation predicates.',
                           'Unknown agreement is not detection success.',
                           'The inspected native execution worker is not a general-purpose Python sandbox.']}
    write(output/'observations.json', {'observations': observations}); write(output/'summary.json', result)
    if verify() != frozen_sha: raise ValueError('Frozen method changed during study')
    return result['summary']


def normalize(value, origin):
    if isinstance(value, dict): return {k: normalize(v, origin) for k, v in value.items() if k not in {'wall_seconds', 'command'}}
    if isinstance(value, list): return [normalize(v, origin) for v in value]
    if isinstance(value, str): return value.replace(origin, '<run>')
    return value


def replay(old, new, output):
    output = Path(output)
    if output.exists(): raise ValueError('Preserve earlier replay report')
    a, b = read(old), read(new); old_root, new_root = Path(old).resolve().parent, Path(new).resolve().parent
    old_origin, new_origin = a['origin_output'], b['origin_output']
    if normalize(a, old_origin) != normalize(b, new_origin):
        raise ValueError('Full analytical replay outputs differ')
    verified = 0
    for left, right in zip(a['semgrep_results'], b['semgrep_results']):
        if left['unit_id'] != right['unit_id']: raise ValueError('Replay unit identity mismatch')
        for record, run_root, recorded_origin in [(left, old_root, old_origin), (right, new_root, new_origin)]:
            if record['status'] != 'complete': continue
            if record['engine']['sha256'] != '8b0c1fa10fa70372ea64ca0dc9cf3de0fd53db9c2556f6af5f973e8df12d4995':
                raise ValueError('Replay engine hash mismatch')
            for part in [record, record['coverage']]:
                command = part['command']
                # Resolve archived absolute invocation paths under the supplied
                # replay directory, avoiding dependency on the original root.
                rules = run_root/Path(command[command.index('-rules')+1]).relative_to(recorded_origin)
                source = run_root/Path(command[-1]).relative_to(recorded_origin)
                if sha(rules) != part['rule_sha256'] or sha(source) != record['source_sha256']:
                    raise ValueError('Replay source or rule bytes differ')
        if left['status'] == 'complete':
            def flags(part):
                command = part['command'][:]; command[0] = '<core>'
                command[command.index('-rules')+1] = '<rules>'; command[-1] = '<source>'
                return command
            for x, y in [(left, right), (left['coverage'], right['coverage'])]:
                if flags(x) != flags(y): raise ValueError('Replay native CE flags differ')
            verified += 1
    result = {'passed': True, 'method_freeze_sha256': verify(),
              'model_response_freeze_sha256': sha(ROOT/'results/model-response-freeze.json'),
              'full_analytical_outputs_equal': True, 'completed_Semgrep_scan_pairs_verified': verified,
              'normalization': ['wall_seconds', 'run directory paths', 'commands checked separately for flags and source/rule bytes'],
              'new_model_calls': 0, 'same_machine_only': True}
    write(output, result); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['freeze', 'verify', 'run', 'worker', 'replay'])
    parser.add_argument('--output', type=Path); parser.add_argument('--unit'); parser.add_argument('--probe')
    parser.add_argument('--old', type=Path); parser.add_argument('--new', type=Path)
    args = parser.parse_args()
    if args.operation == 'freeze': result = freeze()
    elif args.operation == 'verify': result = {'passed': True, 'method_freeze_sha256': verify()}
    elif args.operation == 'run': result = run(args.output)
    elif args.operation == 'worker': worker(args.unit, args.probe); return
    else: result = replay(args.old, args.new, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
