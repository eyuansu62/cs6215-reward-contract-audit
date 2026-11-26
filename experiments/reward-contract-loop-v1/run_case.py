"""One-case witness oracle and unchanged-interface feasibility probe.

The witness oracle only checks known concrete values; it does not analyze code.
All source analysis is delegated to preserved, hash-checked analyzers and bridge.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
DATA = BASE/'datasets/reasoning-gym-reward-v1'
BRIDGE = BASE/'experiments/reward-contract-extraction-v1/tools/downstream.py'
BRIDGE_SHA = 'b0de7b4b933105f3e53e42e733285e96136d7489b86bb6419c931ce813c458e6'
WORKER = DATA/'repro/reproduce.py'
CONDITIONS = ['correct', 'missing', 'omitted_equality']


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def object_sha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def load_bridge():
    assert sha(BRIDGE) == BRIDGE_SHA
    spec = importlib.util.spec_from_file_location('_preserved_contract_bridge', BRIDGE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.verify_frozen_baseline()['analyzer_files_unchanged']
    return module


def freeze():
    target = ROOT/'method-freeze.json'
    assert not target.exists(), 'Preserve existing case freeze'
    files = [*sorted(ROOT.glob('*.py')), *[ROOT/name for name in
             ['case.json', 'contracts.json', 'expected.json', 'inputs.json', 'archived-observations.json']]]
    write(target, {'created_utc': datetime.now(timezone.utc).isoformat(),
                   'files_sha256': {str(p.relative_to(ROOT)): sha(p) for p in files},
                   'bridge_sha256': BRIDGE_SHA, 'reproduction_worker_sha256': sha(WORKER),
                   'preserved_baseline': load_bridge().verify_frozen_baseline(),
                   'expected_table_frozen_before_execution': True,
                   'no_analyzer_modification': True, 'LLM_calls': 0})
    return {'freeze_sha256': verify()}


def verify():
    frozen = read(ROOT/'method-freeze.json')
    for name, expected in frozen['files_sha256'].items(): assert sha(ROOT/name) == expected, name
    assert sha(BRIDGE) == frozen['bridge_sha256']
    assert sha(WORKER) == frozen['reproduction_worker_sha256']
    assert load_bridge().verify_frozen_baseline() == frozen['preserved_baseline']
    return sha(ROOT/'method-freeze.json')


def witness_oracle(condition, answer, reference, reward):
    """Concrete Boolean predicate check, never a whole-function verdict."""
    if condition == 'missing':
        return {'predicate_satisfied': None, 'verdict': 'unknown_missing_spec'}
    if condition not in {'correct', 'omitted_equality'}:
        raise ValueError('Unknown authored ablation')
    candidate = answer.strip().lower() if isinstance(answer, str) else None
    valid = candidate in {'true', 'false'}
    predicate = valid and candidate == reference.strip().lower() if condition == 'correct' else valid
    return {'predicate_satisfied': predicate,
            'verdict': 'full_credit_violation' if reward >= 1.0 and not predicate else 'no_violation_for_this_witness'}


def run(output):
    frozen_sha = verify(); output = Path(output).resolve()
    assert not output.exists(), 'Preserve earlier case output'
    output.mkdir(parents=True)
    case = read(ROOT/'case.json'); contracts = read(ROOT/'contracts.json')['variants']
    units = read(ROOT/'inputs.json')['units']; expectation = read(ROOT/'expected.json')
    archive = read(ROOT/'archived-observations.json')['observations']
    facts = []; witness_rows = []
    for record in archive:
        command = [sys.executable, '-I', '-B', str(WORKER), 'worker', '--case', record['source_id'], '--probe', record['probe_id']]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=8)
        destination = output/'reproduction'/record['source_id']/record['probe_id'].replace('/', '__')
        destination.mkdir(parents=True)
        (destination/'stdout.txt').write_text(proc.stdout); (destination/'stderr.txt').write_text(proc.stderr)
        write(destination/'command.json', {'argv': command, 'returncode': proc.returncode, 'timeout_seconds': 8})
        assert proc.returncode == 0, proc.stderr
        actual = json.loads(proc.stdout)
        assert actual == record['frozen_observation'], 'Source-only reward changed from frozen replay'
        facts.append({**record, 'current_observation': actual})
        for condition in CONDITIONS:
            result = witness_oracle(condition, record['answer'], record['entry']['answer'], actual['reward'])
            expected = next(r for r in expectation['witness_expectations'] if (r['source_id'], r['probe_id'], r['contract']) == (record['source_id'], record['probe_id'], condition))
            assert result['predicate_satisfied'] == expected['contract_predicate_satisfied']
            assert result['verdict'] == expected['expected_witness_verdict']
            witness_rows.append({'source_id': record['source_id'], 'probe_id': record['probe_id'], 'answer': record['answer'], 'reference': record['entry']['answer'], 'reward': actual['reward'], 'contract': condition, **result, 'expected_matched': True})
    bridge = load_bridge(); static = {}
    for condition in CONDITIONS:
        condition_contracts = []
        if contracts[condition] is not None:
            for unit in units:
                contract = copy.deepcopy(contracts[condition]); contract['task_id'] = unit['task_id']
                condition_contracts.append(contract)
        predictions = bridge.run_condition(units, condition_contracts, output/('bridge-'+condition))
        static[condition] = predictions
        for row in predictions['cases']:
            expected = next(r for r in expectation['frozen_bridge_whole_source_expectations'] if r['contract'] == condition and r['source_id'] == row['task_id'])
            for name, result in row['methods'].items():
                assert not result.get('unexpected_error'), result
                assert result['verdict'] == expected[name]
    projection_rows = []
    for unit in units:
        full, _ = bridge.project_contract(unit, contracts['correct'])
        weak, _ = bridge.project_contract(unit, contracts['omitted_equality'])
        absent, missing_reason = bridge.project_contract(unit, None)
        assert full == weak and absent is None
        by_condition = {c: next(r for r in p['cases'] if r['task_id'] == unit['task_id']) for c, p in static.items()}
        assert by_condition['correct']['detector_input_sha256'] == by_condition['omitted_equality']['detector_input_sha256']
        projection_rows.append({'source_id': unit['task_id'], 'input_contracts_differ': contracts['correct'] != contracts['omitted_equality'],
            'projected_contracts_identical': True, 'projected_contract_sha256': object_sha(full),
            'actual_detector_inputs_identical': True, 'compiled_contract': full,
            'deleted_input_obligation': contracts['correct']['full_credit_requirements'][1],
            'compiled_obligation_reintroduced': full['full_credit_requires'],
            'missing_contract_supported': False, 'missing_contract_reason': missing_reason,
            'actual_semgrep': {c: r['methods']['semgrep']['verdict'] for c, r in by_condition.items()},
            'actual_symbolic': {c: r['methods']['symbolic']['verdict'] for c, r in by_condition.items()}})
    result = {'passed': True, 'method_freeze_sha256': frozen_sha, 'bug_families': 1, 'source_versions': 2,
        'live_source_only_executions': len(facts), 'witness_contract_rows': len(witness_rows),
        'all_live_rewards_match_archived_replay': True, 'all_expected_witness_rows_match': True,
        'all_frozen_interface_predictions_match': True, 'witness_results': witness_rows,
        'projection_proof': projection_rows, 'faithful_three_contract_closed_loop_supported': False,
        'qualification': 'Witness results are concrete evaluation oracles. Whole-source weak contract can still alarm on banana. Identical global alarms alone do not diagnose sensitivity; byte-identical projections with reinstated equality do.',
        'analyzer_edits': False, 'LLM_calls': 0,
        'missing_Unknown_is_wrapper_policy_not_intrinsic_semgrep_limit': True}
    write(output/'observations.json', {'observations': facts})
    write(output/'summary.json', result)
    assert verify() == frozen_sha
    return {k: result[k] for k in ['passed', 'bug_families', 'live_source_only_executions', 'witness_contract_rows', 'faithful_three_contract_closed_loop_supported', 'analyzer_edits', 'LLM_calls']}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('operation', choices=['freeze', 'verify', 'run']); p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.operation == 'freeze': result = freeze()
    elif args.operation == 'verify': result = {'passed': True, 'freeze_sha256': verify()}
    else: result = run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
