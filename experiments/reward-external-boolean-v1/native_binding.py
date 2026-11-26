"""Explicit parameter/one-level-field bindings over frozen Boolean path models.

This module never rewrites native scorer source or converts answer encodings.
It maps only declared scalar reads into existing candidate/reference Terms.
Bare/aliased containers, mutation, helpers and unsupported operations stay Unknown.
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

ROOT = Path(__file__).resolve().parent
V2 = ROOT.parent/'reward-contract-loop-v2'
V2_CHECKER_SHA256 = 'a0218e6474606af3841dd96212fad7c3327dee9a14f8940a7184b13e95dd7705'
V2_CONTRACTS_SHA256 = 'b832098bb832b56d2bd100bc5b66d02546820bdabfac51fff22eaa395c58f257'
LEGACY_SHA256 = 'dfd7e9489b339c71f801b8b5d8cb2ac9721fd1fb2296c2d8e01c2d8242bae95c'


def _sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen():
    checker = _sha(V2/'boolean_checker.py')
    contracts = _sha(V2/'boolean_contracts.py')
    legacy = _sha(ROOT.parent/'reward-baselines-v1/tools/symbolic_baseline.py')
    if (checker, contracts, legacy) != (V2_CHECKER_SHA256, V2_CONTRACTS_SHA256, LEGACY_SHA256):
        raise ValueError('preserved_Boolean_source_changed')
    return {'v2_checker_sha256': checker, 'v2_contracts_sha256': contracts,
            'legacy_source_sha256': legacy}


verify_frozen()
sys.path.insert(0, str(V2))
import boolean_contracts as _contracts
if Path(_contracts.__file__).resolve() != (V2/'boolean_contracts.py').resolve():
    raise ValueError('unexpected_Boolean_contract_module')
_spec = importlib.util.spec_from_file_location('_preserved_v2_for_native_bindings', V2/'boolean_checker.py')
_v2 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _v2
_spec.loader.exec_module(_v2)
_base = _v2._base


def _hash(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def validate_binding(binding, source):
    """Require exact selectors and source parameters; never infer a selector."""
    if type(binding) is not dict or set(binding) != {'candidate', 'reference'}:
        raise ValueError('binding_roles_must_be_exact')
    selectors = []
    for role in ('candidate', 'reference'):
        selector = binding[role]
        if type(selector) is not dict or set(selector) != {'parameter', 'field'}:
            raise ValueError('binding_selector_fields_must_be_exact')
        parameter, key = selector['parameter'], selector['field']
        if type(parameter) is not str or not parameter.isidentifier() or parameter == 'self':
            raise ValueError('binding_parameter_must_be_native_named_argument')
        if key is not None and (type(key) is not str or not key):
            raise ValueError('binding_field_must_be_nonempty_native_string_or_null')
        selectors.append((parameter, key))
    if selectors[0] == selectors[1]:
        raise ValueError('candidate_and_reference_selectors_must_differ')
    if selectors[0][0] == selectors[1][0] and any(key is None for _, key in selectors):
        raise ValueError('shared_parameter_requires_distinct_mapping_fields')
    tree = ast.parse(source['score_source'])
    fn = tree.body[0]
    if fn.args.vararg or fn.args.kwarg:
        raise ValueError('variadic_native_signature_unsupported')
    parameters = {a.arg for a in fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs}
    if any(parameter not in parameters for parameter, _ in selectors):
        raise ValueError('binding_parameter_not_in_native_signature')
    containers = {parameter for parameter, key in selectors if key is not None}
    # Old path seeds use scalar Terms. Never let a rebound container masquerade
    # as its initial binding because a later assigned scalar has the same Term.
    if any(isinstance(node, ast.Name) and node.id in containers
           and isinstance(node.ctx, (ast.Store, ast.Del)) for node in ast.walk(fn)):
        raise ValueError('rebound_native_mapping_parameter_unsupported')
    return copy.deepcopy(binding)


def _unknown(reason, compiled=None, binding=None, input_sha=None, source=None):
    result = _v2._unknown(reason, compiled, input_sha)
    return {**result, 'native_binding': copy.deepcopy(binding),
            'binding_fingerprint': _hash(binding) if binding is not None else None,
            'source_sha256': hashlib.sha256(source['source'].encode()).hexdigest() if source else None,
            'source_rewritten': False, 'answer_encoding_converted': False,
            'method': 'explicit_native_bindings_over_frozen_Boolean_paths_v1'}


class _BoundChecker(_v2._ObligationChecker):
    def __init__(self, source, compiled, obligation, binding):
        super().__init__(source, compiled, obligation)
        self.native_binding = binding
        self.candidate = binding['candidate']['parameter']
        self.reference = binding['reference']['parameter']
        self.initial_markers = {self.candidate: _base.Term('candidate'),
                                self.reference: _base.Term('reference')}
        self.mapping_parameters = {s['parameter'] for s in binding.values() if s['field'] is not None}

    @staticmethod
    def _logical(role):
        return (_base.Term('candidate') if role == 'candidate'
                else _base.Term('field', (_base.Term('reference'),), 'answer'))

    def _is_initial(self, parameter, state):
        return state.env.get(parameter) == self.initial_markers[parameter]

    def expr(self, node, state):
        # Only direct parameter['literal'] reads are mapped. Aliases of a whole
        # native container remain unsupported instead of introducing a model.
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id in self.mapping_parameters
                and self._is_initial(node.value.id, state)):
            if isinstance(node.slice, ast.Constant) and type(node.slice.value) is str:
                for role, selector in self.native_binding.items():
                    if selector['parameter'] == node.value.id and selector['field'] == node.slice.value:
                        return self._logical(role)
            return _base.unknown('native_mapping_field_not_bound')
        if isinstance(node, ast.Name) and node.id in self.initial_markers and self._is_initial(node.id, state):
            if node.id in self.mapping_parameters:
                return _base.unknown('native_mapping_container_is_not_a_bound_scalar')
            if node.id == self.reference:
                return self._logical('reference')
            # Direct candidate parameters already have the preserved candidate
            # Term. Reassigned parameters deliberately fall through unchanged.
        return super().expr(node, state)


def _metadata(compiled, binding, source, input_sha):
    return {'compiled_contract': copy.deepcopy(compiled),
            'contract_fingerprint': _contracts.fingerprint(compiled),
            'input_fingerprint': input_sha, 'native_binding': copy.deepcopy(binding),
            'binding_fingerprint': _hash(binding),
            'source_sha256': hashlib.sha256(source['source'].encode()).hexdigest(),
            'source_rewritten': False, 'answer_encoding_converted': False,
            'legacy_source_sha256': LEGACY_SHA256, 'v2_checker_sha256': V2_CHECKER_SHA256,
            'v2_contracts_sha256': V2_CONTRACTS_SHA256, 'target_source_executed': False,
            'method': 'explicit_native_bindings_over_frozen_Boolean_paths_v1'}


def _prepare_or_unknown(unit, contract, binding):
    compiled = source = checked = None
    input_sha = None
    try:
        verify_frozen()
        compiled = _contracts.compile_contract(contract, unit)
        source = _v2._source_input(unit)
        checked = validate_binding(binding, source)
        input_sha = _hash({**source, 'contract': compiled, 'native_binding': checked})
    except (_contracts.ContractError, ValueError, OSError, SyntaxError, TypeError) as error:
        return None, _unknown(str(error), compiled, checked, input_sha, source)
    return (compiled, source, checked, input_sha), None


def analyze_bound(unit, contract, binding):
    """Globally check only declared atoms on exact source; no reward/gold input."""
    prepared, unknown = _prepare_or_unknown(unit, contract, binding)
    if unknown is not None: return unknown
    compiled, source, checked, input_sha = prepared
    rows = []
    for obligation in compiled['obligations']:
        result = _BoundChecker(source, compiled, obligation, checked).run()
        rows.append({'obligation_id': obligation, **result})
    alarms = [row['obligation_id'] for row in rows if row['verdict'] == 'alarm']
    verdict = 'alarm' if alarms else 'unknown' if any(r['verdict'] == 'unknown' for r in rows) else 'no_alarm'
    return {'verdict': verdict, 'active_obligations': copy.deepcopy(compiled['obligations']),
            'per_obligation': rows, 'alarm_obligations': alarms,
            'source_spans': [s for row in rows for s in row.get('source_spans', [])],
            'unsupported_reason': '; '.join(row['obligation_id']+': '+str(row.get('unsupported_reason'))
                for row in rows if row['verdict'] == 'unknown') or None,
            'qualification': 'Only explicit native parameter or one-level field reads are bound. Frozen paths/predicates are reused; unsupported code remains Unknown. Native mapping containers must remain unmodified; no answer encoding or return-value conversion.',
            **_metadata(compiled, checked, source, input_sha)}


def check_witness_bound(unit, contract, binding, answer, reference):
    """Derive a supplied native scalar witness's reward from frozen source Terms."""
    prepared, unknown = _prepare_or_unknown(unit, contract, binding)
    if unknown is not None: return unknown
    compiled, source, checked, input_sha = prepared
    if answer is not None and type(answer) is not str:
        return _unknown('candidate_domain_violation', compiled, checked, input_sha, source)
    if type(reference) is not str or reference not in {'True', 'False'}:
        return _unknown('reference_domain_violation', compiled, checked, input_sha, source)
    checker = _BoundChecker(source, compiled, compiled['obligations'][0], checked)
    checker.run()
    if checker.budget_exceeded:
        return _unknown('static_path_budget_exceeded', compiled, checked, input_sha, source)
    rewards = []; possible_unknown = False
    for path in checker.exits:
        feasible = checker.path_feasible(path, answer, reference)
        if feasible is False: continue
        if feasible is None:
            possible_unknown = True; continue
        reward = checker.witness_value(path.value, answer, reference)
        if (type(reward) not in (int, float)
                or type(reward) is float and not math.isfinite(reward)):
            possible_unknown = True; continue
        rewards.append((reward, path.span))
    if possible_unknown:
        return _unknown('witness_has_an_unsupported_or_exceptional_possible_path', compiled, checked, input_sha, source)
    if not rewards:
        return _unknown('no_proved_normal_numeric_return_for_witness', compiled, checked, input_sha, source)
    if len({reward for reward, _ in rewards}) != 1:
        return _unknown('witness_has_ambiguous_modeled_returns', compiled, checked, input_sha, source)
    reward = rewards[0][0]
    decision = _contracts.evaluate_witness(compiled, answer, reference, reward)
    decision.pop('observed_reward', None)
    return {**decision, 'reward': reward, 'reward_origin': 'preserved_source_term_path',
            'source_spans': [s for _, s in rewards], **_metadata(compiled, checked, source, input_sha)}
