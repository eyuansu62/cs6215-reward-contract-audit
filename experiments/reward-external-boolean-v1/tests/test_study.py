"""Synthetic harness checks only; no project scorers, models or native CE runs."""
from pathlib import Path
from types import SimpleNamespace
import ast
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_study as study

SCORE = '''def synthetic_score(gold: str, pred: str) -> float:
    if pred is not None and pred.strip().lower() == gold.strip().lower():
        return 1
    return 0
'''
CONTRACT = {'schema': 'boolean-obligations-v1', 'candidate_arg': 'answer',
    'reference_arg': 'entry', 'reference_key': 'answer', 'candidate_domain': 'native_str_or_none',
    'trusted_reference': 'canonical_True_False', 'normalization': ['strip', 'lower'],
    'full_credit_threshold': 1.0, 'obligations': ['valid_boolean_token', 'equals_reference']}

class HarnessTests(unittest.TestCase):
    def unit(self, base, source=SCORE, name='synthetic_score', helper_sources=()):
        original = '\n'.join([*helper_sources, source]); source_file = base/'upstream.py'; source_file.write_text(original)
        return {'id': 'SYN', 'task_id': 'TASK', 'entry_name': name, 'source': original, 'all_source': original,
            'score_source': source, 'helpers': [{'name': ast.parse(h).body[0].name, 'source': h} for h in helper_sources],
            'stdlib_bindings': {}, 'fixed_parameters': {}, 'trusted_reference_canonical_boolean': True,
            'native_binding': {'candidate': {'parameter': 'pred', 'field': None}, 'reference': {'parameter': 'gold', 'field': None}},
            'original_source_file': 'upstream.py', 'original_source_sha256': study.sha(source_file),
            'definitions': [{'name': ast.parse(f).body[0].name, 'source': f,
                'ast_sha256': hashlib.sha256(ast.dump(ast.parse(f).body[0], include_attributes=False).encode()).hexdigest()}
                for f in [*helper_sources, source]]}

    def test_exact_native_ast_and_identity_are_required(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study, 'BASE', Path(tmp)):
            base=Path(tmp); unit=self.unit(base)
            self.assertEqual(study.source_packet(unit)[0], SCORE)
            changed=copy.deepcopy(unit); changed['score_source']=SCORE.replace('return 1', 'return 2')
            with self.assertRaisesRegex(ValueError, 'Scorer bytes|scorer fragment'): study.source_packet(changed)
            (base/'upstream.py').write_text(SCORE+'\n# changed\n')
            with self.assertRaisesRegex(ValueError, 'source hash'): study.source_packet(unit)

    def test_native_values_execute_without_encoding_or_reward_coercion(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study, 'BASE', Path(tmp)):
            unit=self.unit(Path(tmp)); result=study.execute_native(unit, {'id':'p','answer':'False','reference':'True'})
            self.assertEqual((result['reward'],result['python_type']), (0,'int'))
            self.assertFalse(result['answer_encoding_converted']); self.assertFalse(result['reward_coerced'])
            self.assertFalse(result['upstream_module_imported'])
            self.assertEqual(study.execute_native(unit, {'id':'p','answer':'True','reference':'True'})['reward'],1)

    def test_helper_execution_does_not_add_static_analysis_support(self):
        helper='''def synthetic_clean(value):
    def lower(inner):
        return inner.lower()
    return lower(value.strip())
'''
        score='''def synthetic_score(gold, pred):
    if not pred:
        return 0
    return 1 if synthetic_clean(gold) == synthetic_clean(pred) else 0
'''
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
            unit=self.unit(Path(tmp),score,helper_sources=[helper])
            self.assertEqual(study.execute_native(unit,{'id':'p','answer':'True','reference':'True'})['reward'],1)
            result=study.analyze_bound(unit,CONTRACT,unit['native_binding'])
            self.assertEqual(result['verdict'],'unknown'); self.assertIn('helpers',result['unsupported_reason'])

    def test_native_scope_rejects_effects_and_unknown_globals(self):
        for source in ["def bad(gold,pred):\n    import os\n    return 0\n", "def bad(gold,pred):\n    return open(pred).read()\n", "def bad(gold,pred):\n    return pred.__class__\n"]:
            with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
                unit=self.unit(Path(tmp),source,'bad')
                with self.assertRaises(ValueError): study.execute_native(unit,{'id':'p','answer':'True','reference':'True'})

    def test_structured_bool_and_nonfinite_rewards_are_not_converted(self):
        for expression in ["{'score':1}",'(1,1)','True',"float('nan')"]:
            with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
                unit=self.unit(Path(tmp),'def synthetic_score(gold,pred):\n    return '+expression+'\n')
                with self.assertRaisesRegex(ValueError,'Native scalar reward'):
                    study.execute_native(unit,{'id':'p','answer':'True','reference':'True'})

    def test_native_target_exception_is_not_hidden_as_scope_rejection(self):
        source="def synthetic_score(gold,pred):\n    return int('not a number')\n"
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
            unit=self.unit(Path(tmp),source)
            with self.assertRaises(ValueError) as caught:
                study.execute_native(unit,{'id':'p','answer':'True','reference':'True'})
            self.assertNotIsInstance(caught.exception,study.NativeScopeError)

    def test_native_prefix_method_runs_without_adding_static_model(self):
        source="def synthetic_score(gold,pred):\n    if pred.startswith(gold):\n        return 1\n    return 0\n"
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
            unit=self.unit(Path(tmp),source)
            result=study.execute_native(unit,{'id':'p','answer':'True trailing','reference':'True'})
            self.assertEqual(result['reward'],1)
            static=study.check_witness_bound(study.analyzer_unit(unit),CONTRACT,unit['native_binding'],'True trailing','True')
            self.assertEqual(static['verdict'],'unknown')
            self.assertFalse(static['target_source_executed'])
            self.assertTrue(static['unsupported_reason'])
            global_result=study.analyze_bound(study.analyzer_unit(unit),CONTRACT,unit['native_binding'])
            self.assertEqual(global_result['verdict'],'unknown')
            self.assertIn('startswith',global_result['unsupported_reason'])

    def test_shared_mapping_fields_preserve_source_and_values(self):
        source="def synthetic_score(payload):\n    if payload['text']==payload['expected']:\n        return 1\n    return 0\n"
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
            unit=self.unit(Path(tmp),source); unit['native_binding']={'candidate':{'parameter':'payload','field':'text'},'reference':{'parameter':'payload','field':'expected'}}
            self.assertEqual(study.execute_native(unit,{'id':'p','answer':'False','reference':'True'})['reward'],0)
            self.assertEqual(unit['source'],source)

    def test_unknown_static_result_is_not_determinate_agreement(self):
        self.assertFalse(study._assert_determinate_matches({'verdict':'unknown'},{},1))
        result={'verdict':'no_violation_for_this_witness','active_obligations':['valid_boolean_token'], 'per_obligation':[],'violated_obligations':[],'reward':1}
        oracle={k:v for k,v in result.items() if k!='reward'}
        self.assertTrue(study._assert_determinate_matches(result,oracle,1))
        with self.assertRaises(ValueError): study._assert_determinate_matches(result,oracle,0)

    def test_probe_shapes_are_not_coerced(self):
        for answer,reference in [(True,'True'),('True',True),('True','true'),('x'*201,'True')]:
            with self.assertRaises(ValueError): study.validate_probe({'id':'p','answer':answer,'reference':reference})

    def test_semgrep_retains_every_finding_without_semantic_filter(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
            base=Path(tmp); unit=self.unit(base); core=base/'core'; core.write_text('synthetic')
            finding={'check_id':'synthetic-rule'}
            fake=SimpleNamespace(PINNED_VERSION='1.183.0',find_core=lambda:core,
                _execute=lambda *a:SimpleNamespace(returncode=0,stdout='1.183.0'),
                coverage_rules=lambda:{},risky_rules=lambda:{},_coverage=lambda *a:{'status':'complete'},
                _scan=lambda _c,r,p,o,prefix:([finding] if prefix=='scan' else [],['synthetic'],'hash'))
            with patch.object(study,'semgrep_module',return_value=fake): result=study.scan_semgrep(unit,base/'out')
            self.assertEqual(result['verdict'],'alarm'); self.assertEqual(result['findings'],[finding])
            self.assertEqual(result['all_findings'],result['findings']); self.assertFalse(result['source_semantics_filtering'])

    def test_semgrep_coverage_error_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)):
            base=Path(tmp); unit=self.unit(base); core=base/'core'; core.write_text('synthetic')
            fake=SimpleNamespace(PINNED_VERSION='1.183.0',find_core=lambda:core,
                _execute=lambda *a:SimpleNamespace(returncode=0,stdout='1.183.0'),coverage_rules=lambda:{},
                _scan=lambda *a:([],['synthetic'],'hash'),_coverage=lambda *a:(_ for _ in ()).throw(ValueError('coverage absent')))
            with patch.object(study,'semgrep_module',return_value=fake): result=study.scan_semgrep(unit,base/'out')
            self.assertEqual(result['verdict'],'unknown'); self.assertIn('coverage absent',result['errors'][0])

    def test_analyzer_input_drops_identity_origin_and_probe_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            unit=self.unit(Path(tmp)); unit.update(expected_reward=1,issue_status='bug',probe_values=['bad'])
            cleaned=study.analyzer_unit(unit)
            self.assertEqual(set(cleaned),set(study.ANALYZER_FIELDS))
            self.assertNotIn('id',cleaned); self.assertNotIn('original_source_file',cleaned)
            self.assertNotIn('expected_reward',cleaned); self.assertNotIn('issue_status',cleaned)
            cleaned['helpers'].append('changed'); self.assertEqual(unit['helpers'],[])

    def test_synthetic_run_handles_null_reference_without_filling_it(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'BASE',Path(tmp)), patch.object(study,'ROOT',Path(tmp)):
            base=Path(tmp); unit=self.unit(base)
            probes=[{'id':'good','answer':'True','reference':'True'}, {'id':'wrong','answer':'False','reference':'True'}]
            def worker(command, **kwargs):
                probe=next(p for p in probes if p['id']==command[command.index('--probe')+1])
                return SimpleNamespace(returncode=0,stdout=json.dumps(study.execute_native(unit,probe)),stderr='')
            study.write(base/'results/model-response-freeze.json',{})
            study.write(base/'data/condition-contracts.json',{})
            with patch.object(study,'verify',return_value='frozen'), patch.object(study,'previous_integrity',return_value={}), patch.object(study,'load_units',return_value=[unit]), patch.object(study,'load_probes',return_value=probes), patch.object(study,'load_conditions',return_value={'reference':None,'llm':CONTRACT}), patch.object(study,'scan_semgrep',return_value={'verdict':'no_alarm','status':'complete'}), patch.object(study.subprocess,'run',side_effect=worker):
                counts=study.run(base/'run')
            result=study.read(base/'run/summary.json')
            self.assertEqual(counts['native_executions'],2)
            self.assertEqual(counts['global_verdict_counts']['reference']['unknown'],1)
            for row in result['witness_rows']:
                self.assertIsNone(row['conditions']['reference']['source_check']['active_obligations'])
                self.assertEqual(row['conditions']['reference']['source_check']['verdict'],'unknown')
                self.assertFalse(row['both_static_determinate'])
            self.assertIsNone(result['bug_precision_recall'])
            self.assertEqual(counts['paired_native_oracle_eligible'],0)
            self.assertIsNone(counts['paired_native_oracle_violated_id_matches'])
            self.assertIsNone(counts['paired_static_verdict_matches'])
            for row in result['witness_rows']:
                self.assertIsNone(row['same_native_oracle_violated_ids'])
                self.assertIsNone(row['reference_violation_ids_not_expressed_by_model'])

    def seal_conditions(self,root,reference,model,status='complete'):
        study.write(root/'data/reference-contract.json',{'contract':reference})
        study.write(root/'data/condition-contracts.json',{'conditions':{'reference':reference,'llm':model}})
        folder=root/'results/extraction-synthetic'
        study.write(folder/'metadata.json',{'status':status})
        study.write(folder/'response.json',{'status':'abstain' if status=='abstained' else 'extracted','contract':model})
        study.write(folder/'accepted-contract.json',{'contract':model})
        self.reseal(root)

    def reseal(self,root):
        paths=[root/'data/condition-contracts.json',*(root/'results/extraction-synthetic').glob('*.json')]
        study.write(root/'results/model-response-freeze.json',{'method_freeze_sha256':'frozen',
            'model_output':'results/extraction-synthetic',
            'files_sha256':{str(p.relative_to(root)):study.sha(p) for p in paths}})

    def test_null_reference_and_model_contracts_stay_null(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'ROOT',Path(tmp)), patch.object(study,'verify',return_value='frozen'):
            root=Path(tmp); self.seal_conditions(root,None,None,'abstained')
            self.assertEqual(study.load_conditions(),{'reference':None,'llm':None})

    def test_condition_must_equal_sealed_raw_and_accepted_model_contract(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'ROOT',Path(tmp)), patch.object(study,'verify',return_value='frozen'):
            root=Path(tmp); weak=copy.deepcopy(CONTRACT); weak['obligations']=['valid_boolean_token']
            self.seal_conditions(root,None,weak)
            self.assertEqual(study.load_conditions()['llm']['obligations'],['valid_boolean_token'])
            study.write(root/'data/condition-contracts.json',{'conditions':{'reference':None,'llm':CONTRACT}})
            self.reseal(root)
            with self.assertRaisesRegex(ValueError,'differs from sealed raw'): study.load_conditions()

    def test_raw_numeric_representation_is_not_silently_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'ROOT',Path(tmp)), patch.object(study,'verify',return_value='frozen'):
            root=Path(tmp); self.seal_conditions(root,None,CONTRACT)
            raw=study.read(root/'results/extraction-synthetic/response.json'); raw['contract']['full_credit_threshold']=1
            study.write(root/'results/extraction-synthetic/response.json',raw); self.reseal(root)
            with self.assertRaisesRegex(ValueError,'differs from sealed raw'): study.load_conditions()

    def test_failed_extraction_never_activates_raw_or_reference_contract(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(study,'ROOT',Path(tmp)), patch.object(study,'verify',return_value='frozen'):
            root=Path(tmp); self.seal_conditions(root,CONTRACT,None,'failed')
            self.assertIsNone(study.load_conditions()['llm'])
            study.write(root/'data/condition-contracts.json',{'conditions':{'reference':CONTRACT,'llm':CONTRACT}}); self.reseal(root)
            with self.assertRaisesRegex(ValueError,'must remain null'): study.load_conditions()

    def test_unknown_oracles_do_not_count_as_agreement_or_violation_difference(self):
        unknown={'verdict':'unknown','violated_obligations':[]}
        known={'verdict':'no_violation_for_this_witness','violated_obligations':[]}
        for left,right in [(unknown,unknown),(unknown,known),(known,unknown)]:
            result=study.compare_concrete_oracles(left,right)
            self.assertFalse(result['native_oracle_comparable'])
            self.assertIsNone(result['same_native_oracle_violated_ids'])
            self.assertIsNone(result['reference_violation_ids_not_expressed_by_model'])
        result=study.compare_concrete_oracles(known,known)
        self.assertTrue(result['native_oracle_comparable']); self.assertTrue(result['same_native_oracle_violated_ids'])

    def test_replay_normalizes_timing_paths_but_not_verdicts(self):
        a={'verdict':'unknown','wall_seconds':1,'path':'/one/file','command':['old']}
        b={'verdict':'unknown','wall_seconds':2,'path':'/two/file','command':['new']}
        self.assertEqual(study.normalize(a,'/one'),study.normalize(b,'/two'))
        b['verdict']='no_alarm'; self.assertNotEqual(study.normalize(a,'/one'),study.normalize(b,'/two'))

if __name__=='__main__': unittest.main()
