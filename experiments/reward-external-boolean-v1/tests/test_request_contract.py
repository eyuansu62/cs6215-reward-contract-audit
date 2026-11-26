"""Only synthetic extraction and seal boundaries; no model/primary execution."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import request_contract as request


class RequestContractTests(unittest.TestCase):
    def test_pending_dataset_choice_does_not_invoke_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();request.write(root/'data/dataset-scope.json',{'evaluation_scorers_approved':False})
            with patch.object(request,'ROOT',root), patch.object(request.subprocess,'run') as proc:
                with self.assertRaisesRegex(ValueError,'pending'):request.request(root/'output')
                proc.assert_not_called()
            self.assertFalse((root/'output').exists())

    def test_abstained_reference_and_model_stay_null_when_sealed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();folder=root/'results/synthetic';folder.mkdir(parents=True)
            request.write(root/'data/reference-contract.json',{'contract':None})
            request.write(root/'data/task.json',{'task_id':'SYN','question_description':'Decide whether P holds.'})
            response={'task_id':'SYN','status':'abstain','contract':None,'evidence':[],
                      'not_specified':['Format not stated'],'abstention_reason':'No supported literal format rule.'}
            request.write(folder/'response.json',response)
            request.write(folder/'accepted-contract.json',{'contract':None})
            request.write(folder/'metadata.json',{'successful_model_turns':1,'status':'abstained'})
            with patch.object(request,'ROOT',root),patch.object(request,'verify',return_value='frozen'):
                result=request.seal(folder)
            conditions=request.read(root/'data/condition-contracts.json')['conditions']
            self.assertEqual(conditions,{'reference':None,'llm':None})
            self.assertTrue(result['reference_contract_is_null'])
            seal=request.read(root/'results/model-response-freeze.json')
            self.assertIn('data/condition-contracts.json',seal['files_sha256'])
            self.assertIn('results/synthetic/response.json',seal['files_sha256'])

    def test_validator_preserves_single_selected_atom(self):
        contract=request.previous.read(request.previous.V2/'contracts.json')['variants']['omitted_equality']
        response={'task_id':'SYN','status':'extracted','contract':contract,
                  'evidence':[{'obligation_id':'valid_boolean_token','quote':'True or False','reason':'Token set'}],
                  'not_specified':[],'abstention_reason':None}
        actual=request.previous.validate_response(response,{'task_id':'SYN','question_description':'Reply True or False.'})
        self.assertEqual(actual['obligations'],['valid_boolean_token'])
        self.assertEqual(actual,response['contract'])


if __name__=='__main__':unittest.main()
