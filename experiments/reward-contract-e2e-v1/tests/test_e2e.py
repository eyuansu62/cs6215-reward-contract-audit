"""Integration-boundary regressions; synthetic requests, no model/target calls."""
from pathlib import Path
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_e2e as run


class E2ETests(unittest.TestCase):
    def fixture(self, obligations=None):
        contract = run.read(ROOT/'protocol/reference-contract.json')['contract']
        contract['obligations'] = obligations if obligations is not None else ['valid_boolean_token', 'equals_reference']
        task = {'task_id': 'SYN', 'question_description': "Reply 'True' if correct, otherwise 'False'."}
        result = {'task_id': 'SYN', 'status': 'extracted', 'contract': contract,
                  'evidence': [{'obligation_id': o, 'quote': "Reply 'True' if correct, otherwise 'False'.", 'reason': 'Synthetic task support'} for o in contract['obligations']],
                  'not_specified': [], 'abstention_reason': None}
        return result, task

    def test_direct_contract_identity_and_no_equality_completion(self):
        response, task = self.fixture(['valid_boolean_token']); before = copy.deepcopy(response)
        compiled = run.validate_response(response, task)
        self.assertEqual(compiled, response['contract'])
        self.assertEqual(compiled['obligations'], ['valid_boolean_token'])
        self.assertEqual(response, before)
        self.assertEqual(run.evaluate_witness(compiled, 'False', 'True', 1)['violated_obligations'], [])

    def test_equality_only_is_not_completed_with_validity(self):
        response, task = self.fixture(['equals_reference'])
        compiled = run.validate_response(response, task)
        self.assertEqual(compiled['obligations'], ['equals_reference'])
        self.assertEqual(run.evaluate_witness(compiled, 'banana', 'True', 1)['violated_obligations'], ['equals_reference'])

    def test_abstention_preserved_as_missing_not_reference(self):
        response, task = self.fixture()
        response.update(status='abstain', contract=None, evidence=[], abstention_reason='Not enough task information')
        self.assertIsNone(run.validate_response(response, task))
        self.assertEqual(run.evaluate_witness(None, 'False', 'True', 1)['verdict'], 'unknown')

    def test_invalid_ir_empty_duplicate_and_unknown_never_repaired(self):
        for ids in [[], ['equals_reference', 'equals_reference'], ['new_rule']]:
            response, task = self.fixture(ids)
            with self.assertRaises(ValueError): run.validate_response(response, task)
        response, task = self.fixture(); response['contract'].pop('normalization')
        with self.assertRaises(ValueError): run.validate_response(response, task)

    def test_quote_must_be_exact_and_only_selected_ids_need_evidence(self):
        response, task = self.fixture(['valid_boolean_token'])
        self.assertEqual(run.validate_response(response, task)['obligations'], ['valid_boolean_token'])
        response['evidence'].append({'obligation_id': 'equals_reference', 'quote': 'True', 'reason': 'extra'})
        with self.assertRaisesRegex(ValueError, 'inactive'): run.validate_response(response, task)
        response, task = self.fixture(); response['evidence'][0]['quote'] = 'not in task'
        with self.assertRaisesRegex(ValueError, 'quote_not'): run.validate_response(response, task)
        response, task = self.fixture(); response['evidence'] = response['evidence'][:1]
        with self.assertRaisesRegex(ValueError, 'lacks_evidence'): run.validate_response(response, task)

    def test_top_fields_and_status_strict(self):
        response, task = self.fixture(); response['gold'] = True
        with self.assertRaises(ValueError): run.validate_response(response, task)
        response, task = self.fixture(); response['task_id'] = 'other'
        with self.assertRaises(ValueError): run.validate_response(response, task)
        response, task = self.fixture(); response['status'] = 'guess'
        with self.assertRaises(ValueError): run.validate_response(response, task)
        response, task = self.fixture(); response['contract']['full_credit_threshold'] = True
        with self.assertRaises(ValueError): run.validate_response(response, task)

    def test_payload_contains_task_and_unselected_fixed_profile_only(self):
        payload = run.prompt_payload()
        self.assertEqual(set(payload), {'task', 'analysis_profile'})
        self.assertEqual(set(payload['task']), {'task_id', 'question_description', 'placeholder_notes'})
        self.assertNotIn('obligations', payload['analysis_profile'])
        for token in ['scorer', 'reference_contract', 'reward_observations', 'issue_url', 'source_file']:
            self.assertNotIn(token, payload)

    def test_tool_or_failed_event_is_not_a_blind_model_response(self):
        clean = [{'type': 'thread.started', 'thread_id': 'synthetic'}, {'type': 'turn.started'},
                 {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{}'}},
                 {'type': 'turn.completed', 'usage': {'input_tokens': 1, 'output_tokens': 1}}]
        encode = lambda rows: '\n'.join(json.dumps(x) for x in rows)
        self.assertEqual(run.TRANSPORT.audit_events(encode(clean))[1], 4)
        bad = copy.deepcopy(clean); bad[2]['item']['type'] = 'command_execution'
        with self.assertRaises(ValueError): run.TRANSPORT.audit_events(encode(bad))
        with self.assertRaises(ValueError): run.TRANSPORT.audit_events(encode([{'type': 'turn.failed'}]))

    def test_previous_frozen_payloads_verify(self):
        self.assertEqual(run.preserve()['v2_method_sha256'], run.V2_FREEZE)


if __name__ == '__main__': unittest.main()
