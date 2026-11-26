"""Synthetic regressions for the two explicit Boolean obligations only."""
from pathlib import Path
import copy
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boolean_contracts import ContractError, compile_contract, evaluate_witness, fingerprint


def contract(obligations=None):
    return {
        'schema': 'boolean-obligations-v1',
        'candidate_arg': 'answer',
        'reference_arg': 'entry',
        'reference_key': 'answer',
        'candidate_domain': 'native_str_or_none',
        'trusted_reference': 'canonical_True_False',
        'normalization': ['strip', 'lower'],
        'full_credit_threshold': 1.0,
        'obligations': ['valid_boolean_token', 'equals_reference'] if obligations is None else obligations,
    }


class BooleanContractTests(unittest.TestCase):
    def test_compile_preserves_exact_obligations_and_isolated_copy(self):
        source = contract(['equals_reference', 'valid_boolean_token'])
        compiled = compile_contract(source)
        self.assertEqual(compiled, source)
        self.assertEqual(compiled['obligations'], ['equals_reference', 'valid_boolean_token'])
        compiled['obligations'].pop()
        compiled['normalization'].append('untrusted')
        self.assertEqual(source, contract(['equals_reference', 'valid_boolean_token']))

    def test_omission_survives_compilation_and_fingerprint(self):
        full = contract()
        weak = contract(['valid_boolean_token'])
        self.assertEqual(compile_contract(weak), weak)
        self.assertNotEqual(fingerprint(full), fingerprint(weak))
        self.assertEqual(fingerprint(full), fingerprint(copy.deepcopy(full)))

    def test_equality_only_does_not_add_validity(self):
        value = contract(['equals_reference'])
        self.assertEqual(compile_contract(value)['obligations'], ['equals_reference'])
        result = evaluate_witness(value, 'banana', 'True', 1)
        self.assertEqual(result['active_obligations'], ['equals_reference'])
        self.assertEqual(result['violated_obligations'], ['equals_reference'])
        self.assertEqual([x['obligation_id'] for x in result['per_obligation']], ['equals_reference'])

    def test_missing_empty_duplicate_and_unknown_obligations_rejected(self):
        for value, reason in [(None, 'missing_contract'),
                              (contract([]), 'empty_obligations'),
                              (contract(['equals_reference', 'equals_reference']), 'duplicate_obligations'),
                              (contract(['unknown']), 'unsupported_obligation')]:
            with self.subTest(reason=reason), self.assertRaisesRegex(ContractError, reason):
                compile_contract(value)

    def test_obligations_need_native_list_of_native_strings(self):
        for obligations in [('valid_boolean_token',), 'valid_boolean_token', [True], [None]]:
            with self.subTest(obligations=obligations), self.assertRaises(ContractError):
                compile_contract(contract(obligations))

    def test_no_defaults_or_free_text_inference(self):
        value = contract(['valid_boolean_token'])
        del value['obligations']
        with self.assertRaisesRegex(ContractError, 'contract_fields'):
            compile_contract(value)
        value = contract(['valid_boolean_token'])
        value['full_credit_requirements'] = ['Always equal the reference']
        with self.assertRaisesRegex(ContractError, 'contract_fields'):
            compile_contract(value)

    def test_unsupported_profile_fields_are_rejected(self):
        changes = {'schema': 'future-schema', 'candidate_arg': 'candidate',
                   'reference_arg': 'other', 'reference_key': 'solution',
                   'candidate_domain': 'anything', 'trusted_reference': 'arbitrary_string',
                   'normalization': ['lower', 'strip']}
        for field, value in changes.items():
            malformed = contract(); malformed[field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                compile_contract(malformed)

    def test_nonfinite_boolean_and_wrong_thresholds_rejected(self):
        for threshold in [True, False, float('nan'), float('inf'), -float('inf'), 0, 0.5, '1']:
            value = contract(); value['full_credit_threshold'] = threshold
            with self.subTest(threshold=threshold), self.assertRaisesRegex(ContractError, 'full_credit_threshold'):
                compile_contract(value)

    def test_optional_source_unit_requires_literal_trusted_reference(self):
        value = contract()
        self.assertEqual(compile_contract(value, {'trusted_reference_canonical_boolean': True}), value)
        for unit in [{}, {'trusted_reference_canonical_boolean': 1},
                     {'trusted_reference_canonical_boolean': False}, []]:
            with self.subTest(unit=unit), self.assertRaisesRegex(ContractError, 'source_reference'):
                compile_contract(value, unit)

    def test_opposite_valid_token_only_violates_active_equality(self):
        full = evaluate_witness(contract(), 'False', 'True', 1)
        weak = evaluate_witness(contract(['valid_boolean_token']), 'False', 'True', 1)
        self.assertEqual(full['verdict'], 'full_credit_violation')
        self.assertEqual(full['violated_obligations'], ['equals_reference'])
        self.assertEqual(weak['verdict'], 'no_violation_for_this_witness')
        self.assertEqual(weak['violated_obligations'], [])
        self.assertEqual([p['predicate_satisfied'] for p in full['per_obligation']], [True, False])

    def test_invalid_token_violates_each_active_obligation(self):
        full = evaluate_witness(contract(), 'banana', 'True', 1)
        weak = evaluate_witness(contract(['valid_boolean_token']), 'banana', 'True', 1)
        self.assertEqual(full['violated_obligations'], ['valid_boolean_token', 'equals_reference'])
        self.assertEqual(weak['violated_obligations'], ['valid_boolean_token'])

    def test_inactive_predicates_are_never_called(self):
        with patch('boolean_contracts._equals_reference', side_effect=AssertionError('inactive equality evaluated')):
            result = evaluate_witness(contract(['valid_boolean_token']), 'False', 'True', 1)
            self.assertEqual(result['verdict'], 'no_violation_for_this_witness')
        with patch('boolean_contracts._valid_boolean_token', side_effect=AssertionError('inactive validity evaluated')):
            result = evaluate_witness(contract(['equals_reference']), 'False', 'True', 1)
            self.assertEqual(result['violated_obligations'], ['equals_reference'])

    def test_false_predicates_are_not_violations_without_full_reward(self):
        result = evaluate_witness(contract(), 'banana', 'True', 0)
        self.assertEqual(result['verdict'], 'no_violation_for_this_witness')
        self.assertEqual(result['violated_obligations'], [])
        self.assertEqual([p['predicate_satisfied'] for p in result['per_obligation']], [False, False])
        self.assertTrue(all(not p['full_credit_event'] and not p['violated'] for p in result['per_obligation']))

    def test_none_case_and_existing_normalization(self):
        result = evaluate_witness(contract(), None, 'True', 1)
        self.assertEqual(result['violated_obligations'], ['valid_boolean_token', 'equals_reference'])
        result = evaluate_witness(contract(), '  tRuE\n', 'True', 1.0)
        self.assertEqual(result['verdict'], 'no_violation_for_this_witness')
        self.assertTrue(all(p['predicate_satisfied'] for p in result['per_obligation']))

    def test_missing_or_invalid_contract_is_unknown_even_for_zero_reward(self):
        for value in [None, contract([]), {'answer_kind': 'boolean'}]:
            result = evaluate_witness(value, 'False', 'True', 0)
            self.assertEqual(result['verdict'], 'unknown')
            self.assertEqual(result['per_obligation'], [])
            self.assertEqual(result['violated_obligations'], [])
            self.assertIsNotNone(result['unsupported_reason'])

    def test_witness_domain_errors_are_unknown(self):
        for answer, reference, reward in [(True, 'True', 1), (1, 'True', 1),
                                          ('True', 'true', 1), ('True', True, 1),
                                          ('True', 'True', True), ('True', 'True', float('nan')),
                                          ('True', 'True', float('inf')), ('True', 'True', None)]:
            with self.subTest(answer=answer, reference=reference, reward=reward):
                result = evaluate_witness(contract(), answer, reference, reward)
                self.assertEqual(result['verdict'], 'unknown')
                self.assertEqual(result['per_obligation'], [])
                self.assertEqual(result['violated_obligations'], [])

    def test_large_native_integer_reward_is_finite_without_float_conversion(self):
        result = evaluate_witness(contract(), 'False', 'True', 10**500)
        self.assertEqual(result['violated_obligations'], ['equals_reference'])


if __name__ == '__main__':
    unittest.main()
