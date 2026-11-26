"""Protocol regressions: synthetic data only, no model/target execution."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import run_extraction as run


class ExtractionTests(unittest.TestCase):
    def fixture(self):
        schema = run.read(run.ROOT/'protocol/response-schema.json')
        response = {}
        for key, definition in schema['properties'].items():
            kind = definition['type']
            if key == 'boolean_tokens': response[key] = {'true': None, 'false': None}
            elif isinstance(kind, list): response[key] = None
            elif kind == 'array': response[key] = []
            elif 'enum' in definition: response[key] = definition['enum'][0]
            else: response[key] = ''
        response['task_id'] = 'SYNTHETIC'
        response['evidence'] = [{'field': 'answer_kind', 'quote': 'Return True'}]
        return response, {'task_id': 'SYNTHETIC', 'question_description': 'Return True or False.'}

    def test_generic_schema_and_exact_evidence(self):
        value, task = self.fixture()
        self.assertEqual(run.validate_contract(value, task), value)
        value['evidence'][0]['quote'] = 'invented scorer policy'
        with self.assertRaisesRegex(ValueError, 'Evidence quote'):
            run.validate_contract(value, task)

    def test_extra_field_wrong_type_or_wrong_id_rejected(self):
        original, task = self.fixture()
        value = copy.deepcopy(original); value['gold'] = True
        with self.assertRaises(ValueError): run.validate_contract(value, task)
        value = copy.deepcopy(original); value['numeric_tolerance'] = True
        with self.assertRaises(ValueError): run.validate_contract(value, task)
        value = copy.deepcopy(original); value['task_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'ID differs'): run.validate_contract(value, task)

    def test_nonfinite_json_numbers_rejected(self):
        value, task = self.fixture()
        for number in [float('nan'), float('inf'), -float('inf')]:
            value['numeric_tolerance'] = number
            with self.assertRaisesRegex(ValueError, 'nonfinite number'):
                run.validate_contract(value, task)

    def test_tool_or_failed_turn_cannot_pass_blind_audit(self):
        clean = [{'type': 'thread.started'}, {'type': 'turn.started'},
                 {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{}'}},
                 {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 2}}]
        encode = lambda events: '\n'.join(json.dumps(x) for x in events)
        self.assertEqual(run.audit_events(encode(clean))[0]['input_tokens'], 10)
        bad = copy.deepcopy(clean); bad[2]['item']['type'] = 'command_execution'
        with self.assertRaisesRegex(ValueError, 'Tool/action'): run.audit_events(encode(bad))
        with self.assertRaises(ValueError): run.audit_events(encode([{'type': 'turn.failed'}]))
        with self.assertRaises(ValueError): run.audit_events(encode(clean+clean))

    def test_preserved_baseline_hashes_verify(self):
        self.assertEqual(run.verify_old(), run.OLD_SHA)


if __name__ == '__main__':
    unittest.main()
