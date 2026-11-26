"""New evaluator tests only; no frozen analyzer or native scorer execution."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('controlled_study_scoring', ROOT / 'run_study.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def fake_data():
    """Build the full dependency structure using an explicit hand-assigned matrix."""
    matrix = {'E': {'equality': 'no_alarm', 'token_only': 'alarm', 'truthiness': 'alarm'},
              'V': {'equality': 'no_alarm', 'token_only': 'no_alarm', 'truthiness': 'alarm'}}
    rows, cards = [], []
    for gold in ('E', 'V', 'U'):
        for family in range(4):
            task_id = gold + str(family)
            for condition in study.CONDITIONS:
                predicted = 'U' if condition == 'fixed_null' else condition[-1] if condition in ('fixed_E', 'fixed_V') else gold
                cards.append({'task_id': task_id, 'condition': condition, 'gold_class': gold,
                              'family': 'family' + str(family), 'class': predicted})
                for program_id in ('equality', 'token_only', 'truthiness'):
                    verdict = 'unknown' if predicted == 'U' else matrix[predicted][program_id]
                    expected = None if gold == 'U' else matrix[gold][program_id]
                    gold_witness = verdict == 'alarm' and gold != 'U' and not (gold == 'V' and predicted == 'E')
                    native = [] if verdict != 'alarm' else [{'gold_predicate_violated': None if gold == 'U' else gold_witness,
                                                            'answer': 'False' if predicted == 'E' else 'banana', 'reference': 'True',
                                                            'native_reward': 1.0}]
                    rows.append({'task_id': task_id, 'program_id': program_id, 'condition': condition,
                                 'gold_class': gold, 'contract_class': predicted, 'result': {'verdict': verdict},
                                 'binary_outcome': study.binary_outcome(gold, expected, verdict),
                                 'gold_witness_validated_alarm': gold_witness, 'native_counterexamples': native})
    return rows, cards


class IndependentOracleTests(unittest.TestCase):
    def test_opposite_label_is_valid_but_not_equal(self):
        self.assertEqual(study.independent_truth(' False ', 'True'),
                         {'valid_boolean_token': True, 'equals_reference': False})

    def test_case_and_boundary_whitespace_are_normalized(self):
        self.assertEqual(study.independent_truth('\tTrUe\n', 'True'),
                         {'valid_boolean_token': True, 'equals_reference': True})
        self.assertEqual(study.independent_truth('True explanation', 'True'),
                         {'valid_boolean_token': False, 'equals_reference': False})

    def test_none_and_fresh_generated_tokens_are_invalid(self):
        for answer in (None, '', 'banana', '__not_a_boolean_token___'):
            self.assertFalse(any(study.independent_truth(answer, 'False').values()))

    def test_native_type_guards(self):
        for answer, reference in ((False, 'True'), (1, 'True'), ('True', True), ('True', 'true')):
            with self.assertRaises(ValueError):
                study.independent_truth(answer, reference)

    def test_only_active_ids_are_evaluated_and_threshold_matters(self):
        valid = study.contract_for('V')
        equality = study.contract_for('E')
        self.assertEqual(study.independent_decision(valid, 'False', 'True', 1)['violated_obligations'], [])
        decision = study.independent_decision(equality, 'False', 'True', 1)
        self.assertEqual(decision['violated_obligations'], ['equals_reference'])
        self.assertEqual([x['obligation_id'] for x in decision['per_obligation']], ['equals_reference'])
        self.assertEqual(study.independent_decision(equality, 'False', 'True', 0.5)['violated_obligations'], [])
        self.assertEqual(study.independent_decision(None, 'banana', 'True', 1)['verdict'], 'unknown')

    def test_e_and_e_plus_v_have_one_semantic_class_without_rewriting(self):
        combined = study.contract_for('E')
        combined['obligations'] = ['valid_boolean_token', 'equals_reference']
        original = copy.deepcopy(combined)
        self.assertEqual(study.semantic_class(combined), 'E')
        self.assertEqual(combined, original)
        self.assertEqual(study.independent_decision(combined, 'banana', 'True', 1)['violated_obligations'],
                         ['valid_boolean_token', 'equals_reference'])


class ExtractionTests(unittest.TestCase):
    class FakeValidator:
        @staticmethod
        def validate_response(response, task):
            if response.get('bad'):
                raise ValueError('Mock rejection')
            return copy.deepcopy(response['contract'])

    def test_valid_abstention_and_invalid_output_are_not_conflated(self):
        task = {'task_id': 'x'}
        valid = study.validated_extraction(self.FakeValidator, task,
                                          {'status': 'abstained', 'response': {'contract': None}})
        malformed = study.validated_extraction(self.FakeValidator, task,
                                              {'status': 'complete', 'response': {'bad': True}})
        failed = study.validated_extraction(self.FakeValidator, task, {'status': 'failed'})
        self.assertEqual(valid['class'], 'U')
        self.assertEqual(malformed['class'], 'INVALID')
        self.assertEqual(failed['class'], 'INVALID')
        self.assertIsNone(malformed['contract'])

    def test_raw_response_and_accepted_contract_must_agree(self):
        result = study.validated_extraction(self.FakeValidator, {'task_id': 'x'},
                                           {'status': 'complete', 'response': {'contract': study.contract_for('E')}},
                                           {'contract': study.contract_for('V')})
        self.assertEqual(result['class'], 'INVALID')

    def test_metadata_abstention_cannot_cover_extracted_contract(self):
        result = study.validated_extraction(self.FakeValidator, {'task_id': 'x'},
                                           {'status': 'abstained', 'response': {'contract': study.contract_for('E')}})
        self.assertEqual(result['class'], 'INVALID')

    def test_failed_partial_json_is_retained_as_invalid_without_parsing(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / 'metadata.json').write_text('{"status":"failed","error":"transport failure"}')
            (folder / 'response.json').write_text('{"contract": ')
            result = study.load_model_extraction(self.FakeValidator, {'task_id': 'x'}, folder)
            self.assertEqual(result['class'], 'INVALID')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error'], 'transport failure')
            self.assertEqual((folder / 'response.json').read_text(), '{"contract": ')

    def test_nominal_success_with_malformed_json_becomes_invalid(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / 'metadata.json').write_text('{"status":"complete"}')
            (folder / 'response.json').write_text('{broken')
            result = study.load_model_extraction(self.FakeValidator, {'task_id': 'x'}, folder)
            self.assertEqual(result['class'], 'INVALID')
            self.assertEqual(result['status'], 'rejected')
            self.assertIsNone(result['contract'])


class AggregationTests(unittest.TestCase):
    def test_correct_reference_has_twenty_four_binary_and_twelve_administrative_cells(self):
        rows, cards = fake_data()
        summary = study.aggregate(rows, cards)
        reference = summary['conditions']['reference']
        self.assertEqual(reference['binary_confusion'], {'TP': 12, 'FP': 0, 'FN': 0, 'TN': 12, 'Unknown': 0})
        self.assertEqual(reference['semantic_cells'], 24)
        self.assertEqual(reference['administrative_U']['cells'], 12)
        self.assertEqual(reference['administrative_U']['valid_abstentions'], 12)
        self.assertEqual(reference['contract_class_correct_cards'], 12)
        self.assertEqual(reference['correct_global_vectors_nonnull_cards'], 8)

    def test_null_never_receives_twenty_four_free_true_negatives(self):
        summary = study.aggregate(*fake_data())['conditions']['fixed_null']
        self.assertEqual(summary['binary_confusion'], {'TP': 0, 'FP': 0, 'FN': 0, 'TN': 0, 'Unknown': 24})
        self.assertEqual(summary['binary_accuracy'], 0)
        self.assertEqual(summary['administrative_U']['valid_abstentions'], 12)
        self.assertEqual(summary['contract_class_correct_cards'], 4)

    def test_unjustified_u_contracts_are_administrative_not_false_positives(self):
        summary = study.aggregate(*fake_data())['conditions']['fixed_E']
        self.assertEqual(summary['binary_confusion'], {'TP': 12, 'FP': 4, 'FN': 0, 'TN': 8, 'Unknown': 0})
        self.assertEqual(summary['administrative_U']['unjustified_contracts'], 12)
        self.assertEqual(summary['administrative_U']['unjustified_alarms'], 8)
        self.assertFalse(summary['administrative_U']['included_in_binary_denominator'])

    def test_lucky_true_positive_without_gold_violating_witness_is_not_supported(self):
        summary = study.aggregate(*fake_data())['conditions']['fixed_E']
        self.assertEqual(summary['binary_correct_cells'], 20)
        self.assertEqual(summary['witness_supported_correct_cells'], 16)
        self.assertEqual(summary['witness_validated_alarms'], 8)
        self.assertEqual(summary['alarm_cells_without_gold_violating_returned_witness'], 8)

    def test_invalid_u_is_not_a_correct_abstention_or_gain(self):
        rows, cards = fake_data()
        for row in rows:
            if row['condition'] == 'llm' and row['gold_class'] == 'U':
                row['contract_class'] = 'INVALID'
        for card in cards:
            if card['condition'] == 'llm' and card['gold_class'] == 'U':
                card['class'] = 'INVALID'
        summary = study.aggregate(rows, cards)
        llm = summary['conditions']['llm']
        self.assertEqual(llm['administrative_U']['invalid_outputs'], 12)
        self.assertEqual(llm['administrative_U']['valid_abstentions'], 0)
        self.assertEqual(llm['contract_class_correct_cards'], 8)
        self.assertEqual(llm['contract_class_confusion']['U']['INVALID'], 4)
        self.assertEqual(summary['llm_vs_rules_U_administrative_counts'], {'loss': 12})

    def test_binary_unknown_and_semantic_fn_are_distinct(self):
        self.assertEqual(study.binary_outcome('E', 'alarm', 'unknown'), 'Unknown')
        self.assertEqual(study.binary_outcome('E', 'alarm', 'no_alarm'), 'FN')
        self.assertIsNone(study.binary_outcome('U', None, 'alarm'))


if __name__ == '__main__':
    unittest.main()
