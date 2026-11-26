"""Two explicit Boolean obligations and a concrete-value validation oracle.

No source program is interpreted here. This module neither infers obligations
from text/type metadata nor adds an omitted obligation during compilation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math


SUPPORTED_OBLIGATIONS = ('valid_boolean_token', 'equals_reference')
_FIXED_FIELDS = {
    'schema': 'boolean-obligations-v1',
    'candidate_arg': 'answer',
    'reference_arg': 'entry',
    'reference_key': 'answer',
    'candidate_domain': 'native_str_or_none',
    'trusted_reference': 'canonical_True_False',
}
_FIELDS = set(_FIXED_FIELDS) | {'normalization', 'full_credit_threshold', 'obligations'}


class ContractError(ValueError):
    """The supplied contract cannot be represented by this minimal interface."""


def compile_contract(contract, unit=None):
    """Validate and copy an explicit contract, preserving exactly its obligations.

    Source binding is optional for standalone concrete-value checks. A supplied
    source unit must separately establish the canonical native reference domain.
    """
    if contract is None:
        raise ContractError('missing_contract')
    if (type(contract) is not dict or any(type(key) is not str for key in contract)
            or set(contract) != _FIELDS):
        raise ContractError('contract_fields_must_be_exact')
    for field, expected in _FIXED_FIELDS.items():
        if type(contract[field]) is not str or contract[field] != expected:
            raise ContractError('unsupported_'+field)
    normalization = contract['normalization']
    if (type(normalization) is not list or any(type(item) is not str for item in normalization)
            or normalization != ['strip', 'lower']):
        raise ContractError('unsupported_normalization')
    threshold = contract['full_credit_threshold']
    if (type(threshold) not in (int, float)
            or type(threshold) is float and not math.isfinite(threshold)
            or threshold != 1.0):
        raise ContractError('unsupported_full_credit_threshold')
    obligations = contract['obligations']
    if type(obligations) is not list or any(type(item) is not str for item in obligations):
        raise ContractError('obligations_must_be_native_string_list')
    if not obligations:
        raise ContractError('empty_obligations')
    if len(obligations) != len(set(obligations)):
        raise ContractError('duplicate_obligations')
    if any(item not in SUPPORTED_OBLIGATIONS for item in obligations):
        raise ContractError('unsupported_obligation')
    if unit is not None and (type(unit) is not dict
                             or unit.get('trusted_reference_canonical_boolean') is not True):
        raise ContractError('source_reference_not_established')
    return copy.deepcopy(contract)


def fingerprint(contract):
    """Hash the validated input, including its unchanged ordered obligation list."""
    compiled = compile_contract(contract)
    serialized = json.dumps(compiled, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def _valid_boolean_token(normalized):
    return normalized in {'true', 'false'}


def _equals_reference(normalized, reference):
    return normalized is not None and normalized == reference.strip().lower()


def _unknown(reason, active=None):
    return {'verdict': 'unknown', 'active_obligations': copy.deepcopy(active),
            'per_obligation': [], 'violated_obligations': [],
            'unsupported_reason': reason}


def evaluate_witness(contract, answer, reference, reward):
    """Check concrete native values against only the explicitly active predicates.

    This is an evaluation oracle, not a source analyzer. Missing/invalid contracts
    produce administrative Unknown even if a supplied reward is below full credit.
    """
    try:
        compiled = compile_contract(contract)
    except ContractError as error:
        return _unknown(str(error))
    active = compiled['obligations']
    if answer is not None and type(answer) is not str:
        return _unknown('candidate_domain_violation', active)
    if type(reference) is not str or reference not in {'True', 'False'}:
        return _unknown('reference_domain_violation', active)
    if (type(reward) not in (int, float)
            or type(reward) is float and not math.isfinite(reward)):
        return _unknown('reward_domain_violation', active)
    normalized = answer.strip().lower() if type(answer) is str else None
    full_credit = reward >= compiled['full_credit_threshold']
    rows = []
    for obligation in active:
        # Dispatch only the selected predicate: an omitted equality is never run.
        predicate = (_valid_boolean_token(normalized) if obligation == 'valid_boolean_token'
                     else _equals_reference(normalized, reference))
        rows.append({'obligation_id': obligation, 'predicate_satisfied': predicate,
                     'full_credit_event': full_credit, 'violated': full_credit and not predicate})
    violated = [row['obligation_id'] for row in rows if row['violated']]
    return {'verdict': 'full_credit_violation' if violated else 'no_violation_for_this_witness',
            'active_obligations': copy.deepcopy(active), 'per_obligation': rows,
            'violated_obligations': violated, 'observed_reward': reward,
            'full_credit_event': full_credit, 'unsupported_reason': None}
