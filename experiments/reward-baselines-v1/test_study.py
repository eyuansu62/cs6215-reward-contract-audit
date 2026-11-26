"""Study protocol tests; no primary detector/subject execution."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_baselines as study


class StudyTests(unittest.TestCase):
    def test_unknown_is_not_true_negative_and_reduces_positive_recall(self):
        rows = [
            {'expected_violation': gold, 'methods': {'m': {'verdict': verdict}}}
            for gold, verdict in [(True, 'alarm'), (True, 'unknown'),
                                  (False, 'unknown'), (False, 'no_alarm'),
                                  (False, 'alarm'), (True, 'no_alarm')]
        ]
        result = study.metric(rows, 'm')
        self.assertEqual([result[k] for k in ['tp', 'fp', 'fn', 'tn',
                         'unknown_positive', 'unknown_negative']], [1]*6)
        self.assertEqual(result['accuracy'], 2/6)
        self.assertEqual(result['coverage'], 4/6)
        self.assertEqual(result['recall_with_unknown'], 1/3)

    def test_corrupted_verdict_is_not_treated_as_no_alarm(self):
        with self.assertRaisesRegex(ValueError, 'Invalid prediction verdict'):
            study.metric([{'expected_violation': False, 'methods': {'m': {'verdict': 'corrupt'}}}], 'm')

    def test_contract_and_projection_have_no_evaluation_fields(self):
        forbidden = {'expected_violation', 'observed_reward', 'probe', 'probes',
                     'disposition', 'subject_id', 'issue_url', 'pr_status'}
        data = study.read(study.ROOT/'inputs.json')
        self.assertEqual(len(data['units']), 7)
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values(): check(child)
            elif isinstance(value, list):
                for child in value: check(child)
        check(data)
        contracts = study.read(study.ROOT/'protocol/contracts.json')['contracts']
        self.assertEqual(len({u['unit_id'] for u in data['units']}), 7)
        for unit in data['units']:
            contract = contracts[unit['contract']['id']]
            self.assertEqual(unit['contract'], {
                'id': unit['contract']['id'], 'candidate_arg': 'answer',
                'reference_arg': 'entry', 'full_credit_threshold': 1.0,
                **contract})
        probability = [u for u in data['units'] if u['contract']['id']=='C_PROBABILITY_FULL']
        self.assertEqual(probability[0]['fixed_parameters'], {'tol': 0.0001})

    def test_scoring_rejects_duplicate_units_before_gold_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = {'unit_id': 'u', 'source': 'source', 'contract': {'id': 'C'}}
            study.write(root/'inputs.json', {'units': [unit]})
            study.write(root/'method-freeze.json', {})
            pred = {'method_freeze_sha256': 'frozen', 'diagnostic': False,
                    'inputs_sha256': study.sha(root/'inputs.json'),
                    'units': [{'unit_id': 'u'}, {'unit_id': 'u'}]}
            study.write(root/'predictions.json', pred)
            with patch.object(study, 'ROOT', root), patch.object(study, 'verify', return_value='frozen'):
                with self.assertRaisesRegex(AssertionError, 'Missing/duplicate'):
                    study.score(root/'predictions.json', root/'scores.json')
            self.assertFalse((root/'scores.json').exists())

    def test_freeze_verification_rejects_modified_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'protocol').mkdir()
            (root/'tools').mkdir()
            (root/'sample.py').write_text('x = 1\n')
            study.write(root/'tools/tool-release.json', {'version': 'test'})
            study.write(root/'protocol/contracts-evaluation-freeze.json', {'files_sha256': {}})
            with patch.object(study, 'ROOT', root):
                study.write(root/'method-freeze.json', {'files_sha256': study.method_files(), 'inputs_sha256': {}})
                self.assertEqual(len(study.verify()), 64)
                (root/'sample.py').write_text('x = 2\n')
                with self.assertRaisesRegex(AssertionError, 'Frozen method'):
                    study.verify()


if __name__ == '__main__':
    unittest.main()
