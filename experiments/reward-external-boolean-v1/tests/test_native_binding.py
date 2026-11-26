"""Synthetic native-binding regressions; no external scorer is executed."""
import ast
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_binding as bound


def contract(*ids):
    return {'schema': 'boolean-obligations-v1', 'candidate_arg': 'answer',
            'reference_arg': 'entry', 'reference_key': 'answer',
            'candidate_domain': 'native_str_or_none', 'trusted_reference': 'canonical_True_False',
            'normalization': ['strip', 'lower'], 'full_credit_threshold': 1.0,
            'obligations': list(ids)}


def unit(source, identity='synthetic'):
    return {'entry_name': ast.parse(source).body[0].name, 'source': source,
            'score_source': source, 'helpers': [], 'stdlib_bindings': {},
            'fixed_parameters': {}, 'trusted_reference_canonical_boolean': True,
            'unit_id': identity}


def binding(candidate='solution_str', reference='ground_truth', candidate_field=None, reference_field=None):
    return {'candidate': {'parameter': candidate, 'field': candidate_field},
            'reference': {'parameter': reference, 'field': reference_field}}


TRUTHINESS = '''def compute_score(solution_str, ground_truth):
    if solution_str is not None and bool(solution_str) == bool(ground_truth):
        return 1.0
    return 0.0
'''
EQUALITY = '''def compute_score(solution_str, ground_truth):
    if solution_str is not None and solution_str.strip().lower() == ground_truth.strip().lower():
        return 1.0
    return 0.0
'''


class NativeBindingTests(unittest.TestCase):
    def test_scalar_parameter_names_bind_without_source_or_ir_rewrite(self):
        u = unit(TRUTHINESS); c = contract('valid_boolean_token', 'equals_reference'); b = binding()
        before = copy.deepcopy((u, c, b))
        result = bound.analyze_bound(u, c, b)
        self.assertEqual(result['verdict'], 'alarm')
        self.assertEqual(result['compiled_contract'], c)
        self.assertEqual(result['native_binding'], b)
        self.assertEqual(result['active_obligations'], c['obligations'])
        self.assertEqual((u, c, b), before)
        self.assertEqual(result['source_sha256'], hashlib.sha256(TRUTHINESS.encode()).hexdigest())
        self.assertFalse(result['source_rewritten'])

    def test_wrong_boolean_witness_attribution_uses_only_selected_obligation(self):
        u = unit(TRUTHINESS)
        full = bound.check_witness_bound(u, contract('valid_boolean_token', 'equals_reference'), binding(), 'False', 'True')
        weak = bound.check_witness_bound(u, contract('valid_boolean_token'), binding(), 'False', 'True')
        self.assertEqual(full['reward'], 1.0)
        self.assertEqual(full['violated_obligations'], ['equals_reference'])
        self.assertEqual(weak['verdict'], 'no_violation_for_this_witness')
        self.assertEqual(weak['violated_obligations'], [])
        self.assertNotEqual(full['input_fingerprint'], weak['input_fingerprint'])

    def test_equality_only_never_adds_validity(self):
        result = bound.check_witness_bound(unit(TRUTHINESS), contract('equals_reference'), binding(), 'banana', 'True')
        self.assertEqual(result['active_obligations'], ['equals_reference'])
        self.assertEqual(result['violated_obligations'], ['equals_reference'])

    def test_scalar_reference_normalized_guard_certifies_each_active_obligation(self):
        for ids in [('valid_boolean_token',), ('equals_reference',), ('valid_boolean_token', 'equals_reference')]:
            result = bound.analyze_bound(unit(EQUALITY), contract(*ids), binding())
            self.assertEqual(result['verdict'], 'no_alarm')
            self.assertEqual([r['obligation_id'] for r in result['per_obligation']], list(ids))
        wrong = bound.check_witness_bound(unit(EQUALITY), contract('equals_reference'), binding(), 'False', 'True')
        self.assertEqual(wrong['reward'], 0.0)
        self.assertEqual(wrong['violated_obligations'], [])

    def test_reference_mapping_field_bind_preserves_native_key(self):
        source = "def reward(prediction, sample):\n    if prediction == sample['label']:\n        return 1.0\n    return 0.0\n"
        b = binding('prediction', 'sample', reference_field='label')
        result = bound.analyze_bound(unit(source), contract('valid_boolean_token', 'equals_reference'), b)
        self.assertEqual(result['verdict'], 'no_alarm')
        self.assertEqual(result['native_binding']['reference']['field'], 'label')
        self.assertEqual(bound.check_witness_bound(unit(source), contract('equals_reference'), b, 'False', 'True')['reward'], 0.0)

    def test_candidate_mapping_field_bind(self):
        source = "def reward(result, truth):\n    if result['response'] == truth:\n        return 1.0\n    return 0.0\n"
        b = binding('result', 'truth', candidate_field='response')
        self.assertEqual(bound.analyze_bound(unit(source), contract('equals_reference'), b)['verdict'], 'no_alarm')
        self.assertEqual(bound.check_witness_bound(unit(source), contract('equals_reference'), b, 'True', 'True')['reward'], 1.0)

    def test_shared_native_mapping_two_distinct_fields(self):
        source = "def reward(data):\n    if data['response'] == data['expected']:\n        return 1.0\n    return 0.0\n"
        b = binding('data', 'data', 'response', 'expected')
        result = bound.analyze_bound(unit(source), contract('valid_boolean_token', 'equals_reference'), b)
        self.assertEqual(result['verdict'], 'no_alarm')
        self.assertEqual(bound.check_witness_bound(unit(source), contract('equals_reference'), b, 'False', 'True')['reward'], 0.0)

    def test_scalar_parameter_reassignment_does_not_reinterpret_original_binding(self):
        source = "def reward(prediction, truth):\n    prediction = truth\n    if prediction == truth:\n        return 1.0\n    return 0.0\n"
        result = bound.check_witness_bound(unit(source), contract('equals_reference'), binding('prediction', 'truth'), 'False', 'True')
        self.assertEqual(result['reward'], 1.0)
        self.assertEqual(result['violated_obligations'], ['equals_reference'])
        source = "def reward(prediction, truth):\n    truth = 'False'\n    if prediction == truth:\n        return 1.0\n    return 0.0\n"
        result = bound.check_witness_bound(unit(source), contract('equals_reference'), binding('prediction', 'truth'), 'False', 'True')
        self.assertEqual(result['reward'], 1.0)
        self.assertEqual(result['violated_obligations'], ['equals_reference'])

    def test_scalar_alias_keeps_existing_term_semantics(self):
        source = "def reward(prediction, truth):\n    p = prediction\n    t = truth\n    if p == t:\n        return 1.0\n    return 0.0\n"
        self.assertEqual(bound.analyze_bound(unit(source), contract('equals_reference'), binding('prediction', 'truth'))['verdict'], 'no_alarm')

    def test_reassigned_mapping_parameter_is_unknown_before_rebinding_can_hide_type(self):
        source = "def reward(data):\n    data = data['response']\n    if data['response'] == 'False':\n        return 1.0\n    return 0.0\n"
        b = binding('data', 'data', 'response', 'expected')
        self.assertEqual(bound.analyze_bound(unit(source), contract('equals_reference'), b)['verdict'], 'unknown')
        self.assertEqual(bound.check_witness_bound(unit(source), contract('equals_reference'), b, 'False', 'True')['verdict'], 'unknown')

    def test_bare_or_aliased_mapping_and_unbound_field_are_unknown(self):
        b = binding('data', 'data', 'response', 'expected')
        sources = [
            "def reward(data):\n    if bool(data):\n        return 1.0\n    return 0.0\n",
            "def reward(data):\n    alias = data\n    if alias['response'] == alias['expected']:\n        return 1.0\n    return 0.0\n",
            "def reward(data):\n    if data['other']:\n        return 1.0\n    return 0.0\n",
        ]
        for source in sources:
            self.assertEqual(bound.analyze_bound(unit(source), contract('valid_boolean_token'), b)['verdict'], 'unknown')
            self.assertEqual(bound.check_witness_bound(unit(source), contract('valid_boolean_token'), b, 'True', 'True')['verdict'], 'unknown')

    def test_unknown_helpers_calls_batch_or_mutation_do_not_gain_models(self):
        sources = [
            "def reward(prediction, truth):\n    return helper(prediction, truth)\n",
            "def reward(prediction, truth):\n    if len(prediction) > 0:\n        return 1.0\n    return 0.0\n",
            "def reward(prediction, truth):\n    return [1.0]\n",
            "def reward(prediction, truth):\n    return float(prediction == truth)\n",
        ]
        for source in sources:
            self.assertEqual(bound.analyze_bound(unit(source), contract('equals_reference'), binding('prediction', 'truth'))['verdict'], 'unknown')
            self.assertEqual(bound.check_witness_bound(unit(source), contract('equals_reference'), binding('prediction', 'truth'), 'False', 'True')['verdict'], 'unknown')
        mutated = "def reward(data):\n    data['expected'] = data['response']\n    return 1.0\n"
        self.assertEqual(bound.analyze_bound(unit(mutated), contract('equals_reference'), binding('data', 'data', 'response', 'expected'))['verdict'], 'unknown')

    def test_binding_shape_and_source_parameter_presence_are_strict(self):
        invalid = [None, {}, {'candidate': {'parameter': 'x', 'field': None}},
                   binding('missing', 'ground_truth'), binding('solution_str', 'solution_str'),
                   binding('solution_str', 'solution_str', 'x', 'x'),
                   binding('solution_str', 'solution_str', None, 'label'),
                   binding('solution_str', 'ground_truth', candidate_field=0),
                   {'candidate': {'parameter': 'solution_str', 'field': None, 'default': 'True'}, 'reference': {'parameter': 'ground_truth', 'field': None}}]
        for b in invalid:
            self.assertEqual(bound.analyze_bound(unit(TRUTHINESS), contract('equals_reference'), b)['verdict'], 'unknown')

    def test_unsupported_signature_source_and_native_domain_are_unknown(self):
        b = binding('prediction', 'truth')
        for source in ["def reward(prediction, truth, **kwargs):\n    return 1.0\n", "def reward(prediction, truth, *args):\n    return 1.0\n"]:
            self.assertEqual(bound.analyze_bound(unit(source), contract('equals_reference'), b)['verdict'], 'unknown')
        u = unit(TRUTHINESS); u['helpers'] = [{'name': 'x', 'source': 'def x(): return 1'}]
        self.assertEqual(bound.analyze_bound(u, contract('equals_reference'), binding())['verdict'], 'unknown')
        u = unit(TRUTHINESS); u['source'] = EQUALITY
        self.assertEqual(bound.analyze_bound(u, contract('equals_reference'), binding())['verdict'], 'unknown')
        for answer, reference in [(True, 'True'), ('True', True), ('True', 'true')]:
            self.assertEqual(bound.check_witness_bound(unit(TRUTHINESS), contract('equals_reference'), binding(), answer, reference)['verdict'], 'unknown')

    def test_positional_only_and_keyword_only_names_need_no_source_rewrite(self):
        source = "def reward(prediction, /, *, truth):\n    if prediction == truth:\n        return 1.0\n    return 0.0\n"
        self.assertEqual(bound.analyze_bound(unit(source), contract('equals_reference'), binding('prediction', 'truth'))['verdict'], 'no_alarm')

    def test_inactive_obligation_is_not_evaluated(self):
        with patch.object(bound._contracts, '_equals_reference', side_effect=AssertionError('inactive equality')):
            self.assertEqual(bound.analyze_bound(unit(TRUTHINESS), contract('valid_boolean_token'), binding())['verdict'], 'alarm')
            self.assertEqual(bound.check_witness_bound(unit(TRUTHINESS), contract('valid_boolean_token'), binding(), 'False', 'True')['violated_obligations'], [])

    def test_source_identity_does_not_select_results_and_fingerprints_include_binding(self):
        c = contract('equals_reference'); b = binding()
        a = bound.analyze_bound(unit(TRUTHINESS, 'original'), c, b)
        z = bound.analyze_bound(unit(TRUTHINESS, 'repair'), c, b)
        self.assertEqual(a['per_obligation'], z['per_obligation'])
        self.assertEqual(a['input_fingerprint'], z['input_fingerprint'])
        alternate = binding('ground_truth', 'solution_str')
        different = bound.analyze_bound(unit(TRUTHINESS), c, alternate)
        self.assertNotEqual(a['input_fingerprint'], different['input_fingerprint'])

    def test_no_missing_contract_defaults_and_preserved_source_hashes(self):
        result = bound.analyze_bound(unit(TRUTHINESS), None, binding())
        self.assertEqual(result['verdict'], 'unknown')
        self.assertIsNone(result['active_obligations'])
        self.assertEqual(bound.verify_frozen()['v2_checker_sha256'], bound.V2_CHECKER_SHA256)
        self.assertEqual(bound.verify_frozen()['v2_contracts_sha256'], bound.V2_CONTRACTS_SHA256)


if __name__ == '__main__': unittest.main()
