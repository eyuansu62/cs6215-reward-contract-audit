"""Concrete-oracle regressions only; no static analysis or target execution."""
import unittest
from run_case import witness_oracle


class CaseOracleTests(unittest.TestCase):
    def test_opposite_valid_token_is_the_discriminating_witness(self):
        self.assertEqual(witness_oracle('correct', 'False', 'True', 1)['verdict'], 'full_credit_violation')
        self.assertEqual(witness_oracle('omitted_equality', 'False', 'True', 1)['verdict'], 'no_violation_for_this_witness')
        self.assertEqual(witness_oracle('missing', 'False', 'True', 1)['verdict'], 'unknown_missing_spec')

    def test_weak_contract_still_has_a_different_invalid_token_counterexample(self):
        self.assertEqual(witness_oracle('omitted_equality', 'banana', 'True', 1)['verdict'], 'full_credit_violation')
        self.assertEqual(witness_oracle('omitted_equality', 'banana', 'True', 0)['verdict'], 'no_violation_for_this_witness')

    def test_correct_answer_and_nonfull_reward_are_not_full_credit_violations(self):
        self.assertEqual(witness_oracle('correct', 'True', 'True', 1)['verdict'], 'no_violation_for_this_witness')
        self.assertEqual(witness_oracle('correct', 'False', 'True', 0)['verdict'], 'no_violation_for_this_witness')
        with self.assertRaises(ValueError): witness_oracle('invented', 'True', 'True', 1)


if __name__ == '__main__': unittest.main()
