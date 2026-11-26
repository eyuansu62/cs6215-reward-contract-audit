"""Synthetic source-only regressions; no primary fixture or target execution."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import boolean_checker as checker


TRUTHINESS = '''def score_answer(self, answer, entry):
    if answer is not None and bool(answer) == bool(entry['answer']):
        return 1.0
    return 0.0
'''
EQUALITY = '''def score_answer(self, answer, entry):
    if answer is not None and answer.strip().lower() == entry['answer'].strip().lower():
        return 1.0
    return 0.0
'''


def unit(source, identity='synthetic'):
    return {'entry_name': 'score_answer', 'source': source, 'score_source': source,
            'helpers': [], 'stdlib_bindings': {}, 'fixed_parameters': {},
            'trusted_reference_canonical_boolean': True, 'unit_id': identity}


def contract(*obligations):
    return {'schema': 'boolean-obligations-v1', 'candidate_arg': 'answer',
            'reference_arg': 'entry', 'reference_key': 'answer',
            'candidate_domain': 'native_str_or_none', 'trusted_reference': 'canonical_True_False',
            'normalization': ['strip', 'lower'], 'full_credit_threshold': 1.0,
            'obligations': list(obligations)}


class BooleanCheckerTests(unittest.TestCase):
    def test_explicit_obligations_survive_to_actual_input_and_global_results(self):
        u = unit(TRUTHINESS)
        full = checker.analyze(u, contract('valid_boolean_token', 'equals_reference'))
        weak = checker.analyze(u, contract('valid_boolean_token'))
        self.assertEqual(full['verdict'], 'alarm')
        self.assertEqual(weak['verdict'], 'alarm')
        self.assertEqual(weak['active_obligations'], ['valid_boolean_token'])
        self.assertEqual([r['obligation_id'] for r in weak['per_obligation']], ['valid_boolean_token'])
        self.assertNotEqual(full['input_fingerprint'], weak['input_fingerprint'])
        self.assertEqual(full['compiled_contract']['obligations'], ['valid_boolean_token', 'equals_reference'])
        self.assertNotIn('C_BOOLEAN_FULL', str(full['compiled_contract']))

    def test_equality_and_validity_have_distinct_source_generated_counterexamples(self):
        result = checker.analyze(unit(TRUTHINESS), contract('valid_boolean_token', 'equals_reference'))
        rows = {r['obligation_id']: r for r in result['per_obligation']}
        eq = rows['equals_reference']['certificate']
        valid = rows['valid_boolean_token']['certificate']
        self.assertIn(eq['candidate'], ['True', 'False', 'true', 'false'])
        self.assertNotEqual(eq['candidate'].lower(), eq['trusted_reference'].lower())
        self.assertNotIn(valid['candidate'].strip().lower(), {'true', 'false'})
        self.assertEqual(eq['obligation_id'], 'equals_reference')
        self.assertEqual(valid['obligation_id'], 'valid_boolean_token')

    def test_repair_certifies_only_requested_obligations(self):
        for active in [('valid_boolean_token',), ('equals_reference',), ('valid_boolean_token', 'equals_reference')]:
            with self.subTest(active=active):
                result = checker.analyze(unit(EQUALITY), contract(*active))
                self.assertEqual(result['verdict'], 'no_alarm')
                self.assertEqual(result['active_obligations'], list(active))
                self.assertEqual([r['obligation_id'] for r in result['per_obligation']], list(active))

    def test_wrong_valid_token_changes_only_equality_violation(self):
        u = unit(TRUTHINESS)
        full = checker.check_witness(u, contract('valid_boolean_token', 'equals_reference'), 'False', 'True')
        weak = checker.check_witness(u, contract('valid_boolean_token'), 'False', 'True')
        self.assertEqual(full['reward'], 1.0)
        self.assertEqual(full['verdict'], 'full_credit_violation')
        self.assertEqual(full['violated_obligations'], ['equals_reference'])
        self.assertEqual(weak['verdict'], 'no_violation_for_this_witness')
        self.assertEqual(weak['violated_obligations'], [])
        self.assertEqual([r['obligation_id'] for r in weak['per_obligation']], ['valid_boolean_token'])
        self.assertTrue(full['source_spans'])

    def test_invalid_token_violates_active_obligations_but_never_readds_inactive(self):
        full = checker.check_witness(unit(TRUTHINESS), contract('valid_boolean_token', 'equals_reference'), 'not-a-token', 'True')
        weak = checker.check_witness(unit(TRUTHINESS), contract('valid_boolean_token'), 'not-a-token', 'True')
        self.assertEqual(full['violated_obligations'], ['valid_boolean_token', 'equals_reference'])
        self.assertEqual(weak['violated_obligations'], ['valid_boolean_token'])
        eq_only = checker.check_witness(unit(TRUTHINESS), contract('equals_reference'), 'False', 'True')
        self.assertEqual(eq_only['active_obligations'], ['equals_reference'])
        self.assertEqual(eq_only['violated_obligations'], ['equals_reference'])

    def test_subfull_reward_and_matching_answer_have_no_violation(self):
        active = contract('valid_boolean_token', 'equals_reference')
        for source, candidate, expected_reward in [(EQUALITY, 'False', 0.0), (EQUALITY, 'invalid', 0.0),
                                                  (EQUALITY, 'True', 1.0), (TRUTHINESS, 'True', 1.0),
                                                  (TRUTHINESS, None, 0.0)]:
            with self.subTest(candidate=candidate, source=source):
                result = checker.check_witness(unit(source), active, candidate, 'True')
                self.assertEqual(result['reward'], expected_reward)
                self.assertEqual(result['verdict'], 'no_violation_for_this_witness')
                self.assertEqual(result['violated_obligations'], [])

    def test_missing_or_unrepresentable_contract_is_unknown(self):
        for bad in [None, {}, contract(), contract('invented')]:
            self.assertEqual(checker.analyze(unit(TRUTHINESS), bad)['verdict'], 'unknown')
            self.assertEqual(checker.check_witness(unit(TRUTHINESS), bad, 'False', 'True')['verdict'], 'unknown')

    def test_unknown_calls_effects_and_unsupported_conditions_stay_unknown(self):
        sources = [
            "def score_answer(self, answer, entry):\n    helper(answer)\n    return 1.0\n",
            "def score_answer(self, answer, entry):\n    entry['answer'] = answer\n    return 1.0\n",
            "def score_answer(self, answer, entry):\n    if len(answer) > 0:\n        return 1.0\n    return 0.0\n",
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(checker.analyze(unit(source), contract('valid_boolean_token'))['verdict'], 'unknown')
                self.assertEqual(checker.check_witness(unit(source), contract('valid_boolean_token'), 'invalid', 'True')['verdict'], 'unknown')

    def test_finite_counterexample_search_failure_is_not_a_proof(self):
        source = "def score_answer(self, answer, entry):\n    if answer is None:\n        return 1.0\n    return 0.0\n"
        result = checker.analyze(unit(source), contract('valid_boolean_token'))
        self.assertEqual(result['verdict'], 'alarm')
        # A source with a known unsupported helper is not certified from samples.
        unknown = "def score_answer(self, answer, entry):\n    return mystery(answer)\n"
        self.assertEqual(checker.analyze(unit(unknown), contract('equals_reference'))['verdict'], 'unknown')

    def test_known_literal_token_guard_can_certify_validity_without_reference_equality(self):
        source = "def score_answer(self, answer, entry):\n    if answer == 'True' or answer == 'False':\n        return 1.0\n    return 0.0\n"
        valid = checker.analyze(unit(source), contract('valid_boolean_token'))
        equality = checker.analyze(unit(source), contract('equals_reference'))
        self.assertEqual(valid['verdict'], 'no_alarm')
        self.assertEqual(equality['verdict'], 'alarm')

    def test_source_identity_never_selects_results_and_callers_not_mutated(self):
        a = unit(TRUTHINESS, 'original')
        b = unit(TRUTHINESS, 'repair')
        c = contract('valid_boolean_token')
        before = copy.deepcopy((a, b, c))
        ra, rb = checker.analyze(a, c), checker.analyze(b, c)
        self.assertEqual(ra['per_obligation'], rb['per_obligation'])
        self.assertEqual((a, b, c), before)

    def test_inactive_predicate_is_never_evaluated(self):
        with patch('boolean_contracts._equals_reference', side_effect=AssertionError('inactive equality ran')):
            self.assertEqual(checker.analyze(unit(TRUTHINESS), contract('valid_boolean_token'))['verdict'], 'alarm')
            self.assertEqual(checker.check_witness(unit(TRUTHINESS), contract('valid_boolean_token'), 'False', 'True')['verdict'], 'no_violation_for_this_witness')
        with patch('boolean_contracts._valid_boolean_token', side_effect=AssertionError('inactive validity ran')):
            self.assertEqual(checker.analyze(unit(TRUTHINESS), contract('equals_reference'))['verdict'], 'alarm')
            self.assertEqual(checker.check_witness(unit(TRUTHINESS), contract('equals_reference'), 'False', 'True')['violated_obligations'], ['equals_reference'])

    def test_mismatched_source_and_hidden_self_state_are_unknown(self):
        changed = unit(TRUTHINESS); changed['source'] = EQUALITY
        self.assertEqual(checker.analyze(changed, contract('valid_boolean_token'))['verdict'], 'unknown')
        stateful = "def score_answer(self, answer, entry):\n    if self:\n        return 1.0\n    return 0.0\n"
        self.assertEqual(checker.analyze(unit(stateful), contract('valid_boolean_token'))['verdict'], 'unknown')
        self.assertEqual(checker.check_witness(unit(stateful), contract('valid_boolean_token'), 'False', 'True')['verdict'], 'unknown')

    def test_large_native_integer_literal_does_not_overflow_float_finiteness(self):
        reward = 10**500
        source = 'def score_answer(self, answer, entry):\n    return '+str(reward)+'\n'
        self.assertEqual(checker.analyze(unit(source), contract('equals_reference'))['verdict'], 'alarm')
        result = checker.check_witness(unit(source), contract('equals_reference'), 'False', 'True')
        self.assertEqual(result['reward'], reward)
        self.assertEqual(result['violated_obligations'], ['equals_reference'])

    def test_valid_contract_status_survives_unsupported_source(self):
        changed = unit(TRUTHINESS); changed['source'] = EQUALITY
        result = checker.analyze(changed, contract('valid_boolean_token'))
        self.assertEqual(result['active_obligations'], ['valid_boolean_token'])
        self.assertEqual(result['compiled_contract']['obligations'], ['valid_boolean_token'])
        self.assertEqual(result['verdict'], 'unknown')

    def test_old_source_hash_is_unchanged_and_verified(self):
        self.assertEqual(hashlib.sha256(checker.LEGACY_PATH.read_bytes()).hexdigest(), checker.LEGACY_SHA256)
        self.assertEqual(checker.verify_legacy(), checker.LEGACY_SHA256)


if __name__ == '__main__': unittest.main()
