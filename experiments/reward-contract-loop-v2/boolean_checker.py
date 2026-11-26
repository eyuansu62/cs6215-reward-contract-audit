"""Two explicit Boolean obligations over the preserved source-path theory.

The imported legacy module supplies parsing, Terms, path collection, native
Boolean/string evaluation and conservative unsupported exits. This adapter only
changes which full-credit predicate is checked and names that predicate in the
evidence. It adds no Python operations or target execution.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

from boolean_contracts import ContractError, compile_contract, evaluate_witness, fingerprint

ROOT = Path(__file__).resolve().parent
LEGACY_PATH = ROOT.parent/'reward-baselines-v1/tools/symbolic_baseline.py'
LEGACY_SHA256 = 'dfd7e9489b339c71f801b8b5d8cb2ac9721fd1fb2296c2d8e01c2d8242bae95c'
SOURCE_FIELDS = ('entry_name', 'source', 'score_source', 'helpers', 'stdlib_bindings', 'fixed_parameters')


def verify_legacy():
    actual = hashlib.sha256(LEGACY_PATH.read_bytes()).hexdigest()
    if actual != LEGACY_SHA256:
        raise ValueError('preserved_symbolic_source_changed')
    return actual


def _load_legacy():
    verify_legacy()
    name = '_preserved_boolean_source_path_theory_v1'
    spec = importlib.util.spec_from_file_location(name, LEGACY_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_base = _load_legacy()


def _hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _source_input(unit):
    """Validate the single pure scorer envelope; no new helper support."""
    if type(unit) is not dict or any(key not in unit for key in SOURCE_FIELDS):
        raise ValueError('source_fields_missing')
    if (type(unit['source']) is not str or type(unit['score_source']) is not str
            or type(unit['entry_name']) is not str or not unit['entry_name'].isidentifier()
            or type(unit['helpers']) is not list or type(unit['stdlib_bindings']) is not dict
            or type(unit['fixed_parameters']) is not dict):
        raise ValueError('source_field_types_unsupported')
    if unit['helpers'] or unit['fixed_parameters']:
        raise ValueError('helpers_or_fixed_parameters_outside_minimal_boolean_scope')
    if any(type(k) is not str or type(v) is not str for k, v in unit['stdlib_bindings'].items()):
        raise ValueError('stdlib_binding_metadata_unsupported')
    try:
        full = ast.parse(unit['source'])
        fragment = ast.parse(unit['score_source'])
    except (SyntaxError, ValueError, TypeError) as error:
        raise ValueError('source_parse_failed: '+str(error)) from error
    if (len(full.body) != 1 or len(fragment.body) != 1
            or not isinstance(full.body[0], ast.FunctionDef)
            or not isinstance(fragment.body[0], ast.FunctionDef)
            or full.body[0].name != unit['entry_name']
            or ast.dump(full.body[0]) != ast.dump(fragment.body[0])):
        raise ValueError('score_fragment_does_not_match_exact_source')
    if any(isinstance(node, ast.Name) and node.id == 'self' and isinstance(node.ctx, ast.Load)
           for node in ast.walk(fragment.body[0])):
        raise ValueError('self_state_outside_minimal_boolean_scope')
    return {key: copy.deepcopy(unit[key]) for key in SOURCE_FIELDS}


def _prepare_source(unit, compiled):
    verify_legacy()
    source = _source_input(unit)
    actual = {**source, 'contract': compiled}
    return source, _hash(actual)


def _unknown(reason, compiled=None, input_fingerprint=None):
    return {'verdict': 'unknown', 'active_obligations': copy.deepcopy(compiled['obligations']) if compiled else None,
            'per_obligation': [], 'violated_obligations': [], 'alarm_obligations': [],
            'compiled_contract': copy.deepcopy(compiled), 'input_fingerprint': input_fingerprint,
            'contract_fingerprint': fingerprint(compiled) if compiled else None,
            'unsupported_reason': reason, 'source_spans': [],
            'target_source_executed': False, 'legacy_source_sha256': LEGACY_SHA256}


class _ObligationChecker(_base.Checker):
    """Reuse old paths; replace the old combined obligation at both decision hooks."""
    def __init__(self, source, compiled, obligation):
        # This internal profile selects only the legacy native canonical-string
        # field/truthiness model. Both full-credit decision hooks are overridden.
        # The actual stored/hashed contract remains the explicit obligation IR.
        native = {**copy.deepcopy(source), 'contract': {
            'id': 'C_BOOLEAN_FULL', 'candidate_arg': compiled['candidate_arg'],
            'reference_arg': compiled['reference_arg']}}
        super().__init__(native)
        self.unit = {**copy.deepcopy(source), 'contract': copy.deepcopy(compiled)}
        self.contract = copy.deepcopy(compiled)
        self.compiled = compiled
        self.obligation = obligation

    def certificate(self, path):
        reward = path.value.value if path.value.op == 'const' else None
        if (type(reward) not in (int, float)
                or type(reward) is float and not math.isfinite(reward)):
            return None
        implication = super().certificate(path)
        if implication:
            return {'kind': 'source_guard_implies_active_boolean_obligation',
                    'obligation_id': self.obligation, 'source_proof': implication,
                    'argument': 'The source equality guard and trusted canonical reference imply only the requested obligation; no omitted obligation is required.'}
        if self.obligation == 'valid_boolean_token' and not path.state.issues:
            for a, b in self.equal_pairs(path.state):
                for left, right in ((a, b), (b, a)):
                    if (self.normalized(left) == _base.Term('candidate')
                            and right.op == 'const' and type(right.value) is str
                            and right.value.strip().lower() in {'true', 'false'}):
                        return {'kind': 'source_literal_token_guard', 'obligation_id': self.obligation,
                                'argument': 'Equality of the native candidate, after only strip/lower, to a literal Boolean token implies token validity; no reference equality is required.'}
        return None

    def path_feasible(self, path, candidate, reference):
        """True/False/None from only the preserved Term evaluator."""
        if path.state.issues:
            return None
        uncertain = False
        for term, required, *_ in path.state.facts:
            value = self.witness_value(term, candidate, reference)
            if value is _base._RAISE:
                return False
            if value is _base._UNKNOWN:
                uncertain = True
            elif bool(value) != required:
                return False
        for term in path.state.evaluated:
            value = self.witness_value(term, candidate, reference)
            if value is _base._RAISE:
                return False
            if value is _base._UNKNOWN:
                uncertain = True
        return None if uncertain else True

    def boolean_counterexample(self, path, source):
        if path.state.issues:
            return None
        literals = sorted({node.value for node in ast.walk(source)
                           if isinstance(node, ast.Constant) and type(node.value) is str and len(node.value) <= 128})
        fresh = '__not_a_boolean_token__'
        while fresh in literals:
            fresh += '_'
        canonical = ['False', 'True', 'false', 'true']
        candidates = canonical+[fresh, None, ''] if self.obligation == 'equals_reference' else [fresh, None, '']+canonical
        candidates.extend(literals)
        single = {**copy.deepcopy(self.compiled), 'obligations': [self.obligation]}
        reward = path.value.value if path.value.op == 'const' else None
        for candidate in candidates:
            for reference in ('True', 'False'):
                decision = evaluate_witness(single, candidate, reference, reward)
                if decision['verdict'] != 'full_credit_violation':
                    continue
                if self.path_feasible(path, candidate, reference) is True:
                    return {'kind': 'native_boolean_obligation_path_counterexample',
                            'obligation_id': self.obligation, 'candidate': candidate,
                            'candidate_class': 'source/contract-derived native string or None value',
                            'trusted_reference': reference, 'reward': reward,
                            'violated_obligations': [self.obligation],
                            'argument': 'This native value satisfies every supported path fact and intermediate-definedness condition and reaches the literal full reward while the active obligation is false. No scorer was executed.'}
        return None


def analyze(unit, contract):
    """Analyze each explicit obligation globally; no gold/observed reward input."""
    compiled = None
    try:
        compiled = compile_contract(contract, unit)
        source, input_sha = _prepare_source(unit, compiled)
    except (ContractError, ValueError, OSError) as error:
        return _unknown(str(error), compiled)
    rows = []
    for obligation in compiled['obligations']:
        result = _ObligationChecker(source, compiled, obligation).run()
        rows.append({'obligation_id': obligation, **result})
    alarms = [row['obligation_id'] for row in rows if row['verdict'] == 'alarm']
    verdict = 'alarm' if alarms else 'unknown' if any(row['verdict'] == 'unknown' for row in rows) else 'no_alarm'
    return {'verdict': verdict, 'active_obligations': copy.deepcopy(compiled['obligations']),
            'per_obligation': rows, 'alarm_obligations': alarms,
            'compiled_contract': compiled, 'contract_fingerprint': fingerprint(compiled),
            'input_fingerprint': input_sha, 'legacy_source_sha256': LEGACY_SHA256,
            'source_spans': [span for row in rows for span in row.get('source_spans', [])],
            'target_source_executed': False,
            'unsupported_reason': '; '.join(row['obligation_id']+': '+str(row.get('unsupported_reason'))
                                            for row in rows if row['verdict'] == 'unknown') or None,
            'method': 'explicit_boolean_obligations_over_preserved_paths_v2',
            'qualification': 'Only the declared obligation is checked in each result. Unproved paths stay Unknown; bounded counterexample search does not prove absence.'}


def check_witness(unit, contract, answer, reference):
    """Validate a supplied concrete input against modeled paths, never its reward.

    The reward is established from the same source Terms, then active predicates
    are applied to it. No observed reward, expected label or target execution is
    accepted by this API.
    """
    compiled = None
    try:
        compiled = compile_contract(contract, unit)
        source, input_sha = _prepare_source(unit, compiled)
    except (ContractError, ValueError, OSError) as error:
        return _unknown(str(error), compiled)
    if answer is not None and type(answer) is not str:
        return _unknown('candidate_domain_violation', compiled, input_sha)
    if type(reference) is not str or reference not in {'True', 'False'}:
        return _unknown('reference_domain_violation', compiled, input_sha)
    checker = _ObligationChecker(source, compiled, compiled['obligations'][0])
    checker.run()  # Same preserved validation and complete path collection.
    if checker.budget_exceeded:
        return _unknown('static_path_budget_exceeded', compiled, input_sha)
    rewards = []
    possible_unknown = False
    for path in checker.exits:
        feasible = checker.path_feasible(path, answer, reference)
        if feasible is False:
            continue
        if feasible is None:
            possible_unknown = True
            continue
        reward = checker.witness_value(path.value, answer, reference)
        if (type(reward) not in (int, float)
                or type(reward) is float and not math.isfinite(reward)):
            possible_unknown = True
            continue
        rewards.append((reward, path.span))
    if possible_unknown:
        return _unknown('witness_has_an_unsupported_or_exceptional_possible_path', compiled, input_sha)
    if not rewards:
        return _unknown('no_proved_normal_numeric_return_for_witness', compiled, input_sha)
    if len({reward for reward, _ in rewards}) != 1:
        return _unknown('witness_has_ambiguous_modeled_returns', compiled, input_sha)
    reward = rewards[0][0]
    decision = evaluate_witness(compiled, answer, reference, reward)
    decision.pop('observed_reward', None)
    return {**decision, 'reward': reward, 'reward_origin': 'preserved_source_term_path',
            'source_spans': [span for _, span in rewards], 'compiled_contract': compiled,
            'contract_fingerprint': fingerprint(compiled), 'input_fingerprint': input_sha,
            'target_source_executed': False, 'legacy_source_sha256': LEGACY_SHA256}
