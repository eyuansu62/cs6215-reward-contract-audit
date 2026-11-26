"""Rerun the fixed development case with explicit Boolean obligations."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from boolean_contracts import compile_contract, evaluate_witness, fingerprint
from boolean_checker import analyze, check_witness, verify_legacy

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
PREVIOUS = ROOT.parent/'reward-contract-loop-v1'
WORKER = BASE/'datasets/reasoning-gym-reward-v1/repro/reproduce.py'
CONDITIONS = ['correct', 'missing', 'omitted_equality']


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def preserve_previous():
    manifests = [BASE/'experiments/reward-contract-extraction-v1/artifact-files-sha256.json',
                 PREVIOUS/'artifact-files-sha256.json']
    checked = 0
    for path in manifests:
        origin = BASE if path.parent != PREVIOUS else PREVIOUS
        for name, digest in read(path)['files_sha256'].items():
            if sha(origin/name) != digest:
                raise ValueError('Prior frozen payload changed: '+name)
            checked += 1
    return {'previous_payload_files_verified': checked,
            'old_case_method_sha256': sha(PREVIOUS/'method-freeze.json'),
            'old_case_manifest_sha256': sha(PREVIOUS/'artifact-files-sha256.json'),
            'legacy_source_sha256': verify_legacy()}


def method_files():
    paths = [*ROOT.glob('*.py'), *(ROOT/'tests').glob('*.py'),
             *[ROOT/name for name in ['implementation-plan.json', 'case.json', 'contracts.json',
                                     'inputs.json', 'archived-observations.json', 'expected.json',
                                     'semgrep-reference.json']]]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def freeze():
    p = ROOT/'method-freeze.json'
    if p.exists(): raise ValueError('Preserve earlier method freeze')
    write(p, {'created_utc': datetime.now(timezone.utc).isoformat(),
              'files_sha256': method_files(), 'preserved_previous': preserve_previous(),
              'worker_sha256': sha(WORKER), 'frozen_before_primary_rerun': True,
              'scope': 'Only explicit Boolean obligation interface/selection/evidence changed; old AST theory and all previous files preserved.',
              'new_LLM_extraction_requests': 0})
    return {'method_freeze_sha256': verify()}


def verify():
    f = read(ROOT/'method-freeze.json')
    assert method_files() == f['files_sha256'], 'New frozen method/input changed'
    assert preserve_previous() == f['preserved_previous']
    assert sha(WORKER) == f['worker_sha256']
    return sha(ROOT/'method-freeze.json')


def run(output):
    freeze_sha = verify(); output = Path(output).resolve()
    if output.exists(): raise ValueError('Preserve previous output')
    output.mkdir(parents=True)
    units = read(ROOT/'inputs.json')['units']; by_id = {u['task_id']: u for u in units}
    contracts = read(ROOT/'contracts.json')['variants']; expected = read(ROOT/'expected.json')
    global_results = []; static_by_key = {}
    for unit in units:
        for condition in CONDITIONS:
            contract = contracts[condition]
            result = analyze(copy.deepcopy(unit), copy.deepcopy(contract))
            write(output/'global'/unit['task_id']/(condition+'.json'), result)
            exp = next(r for r in expected['global_static_rows'] if (r['source_id'], r['contract']) == (unit['task_id'], condition))
            assert result['verdict'] == exp['verdict'], result
            assert result['active_obligations'] == exp['active_obligations']
            assert [{'obligation_id': r['obligation_id'], 'verdict': r['verdict']} for r in result['per_obligation']] == exp['per_obligation']
            assert result['target_source_executed'] is False
            if contract is not None:
                assert result['compiled_contract'] == compile_contract(contract, unit)
                assert result['contract_fingerprint'] == fingerprint(contract)
            static_by_key[unit['task_id'], condition] = result
            global_results.append({'source_id': unit['task_id'], 'contract': condition, **result})
    observations = []; witness_rows = []
    for record in read(ROOT/'archived-observations.json')['observations']:
        command = [sys.executable, '-I', '-B', str(WORKER), 'worker', '--case', record['source_id'], '--probe', record['probe_id']]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=8)
        folder = output/'reproduction'/record['source_id']/record['probe_id'].replace('/', '__')
        folder.mkdir(parents=True)
        (folder/'stdout.txt').write_text(proc.stdout); (folder/'stderr.txt').write_text(proc.stderr)
        write(folder/'command.json', {'argv': command, 'returncode': proc.returncode, 'timeout_seconds': 8})
        assert proc.returncode == 0, proc.stderr
        observed = json.loads(proc.stdout)
        assert observed == record['frozen_observation'], 'Native scorer reward changed'
        observations.append({**record, 'current_observation': observed})
        unit = by_id[record['source_id']]
        for condition in CONDITIONS:
            contract = contracts[condition]
            oracle = evaluate_witness(contract, record['answer'], record['entry']['answer'], observed['reward'])
            # Source checker accepts no observed reward or expected label.
            source = check_witness(copy.deepcopy(unit), copy.deepcopy(contract), record['answer'], record['entry']['answer'])
            exp = next(r for r in expected['witness_rows'] if (r['source_id'], r['probe_id'], r['contract']) == (record['source_id'], record['probe_id'], condition))
            for result in [oracle, source]:
                assert result['verdict'] == exp['expected_witness_verdict'], result
                assert result['active_obligations'] == exp['active_obligations']
                assert result['per_obligation'] == exp['per_obligation']
                assert result['violated_obligations'] == exp['violated_obligations']
            assert source['target_source_executed'] is False
            if contract is not None:
                assert source['reward'] == observed['reward'], 'Static Term reward differs from executed scorer'
                assert source['input_fingerprint'] == static_by_key[record['source_id'], condition]['input_fingerprint']
            witness_rows.append({'source_id': record['source_id'], 'probe_id': record['probe_id'],
                'contract': condition, 'answer': record['answer'], 'reference': record['entry']['answer'],
                'executed_reward': observed['reward'], 'expected': exp, 'concrete_oracle': oracle,
                'static_witness_check': source, 'all_fields_match_expected': True})
    fidelity = []
    for unit in units:
        full = static_by_key[unit['task_id'], 'correct']; weak = static_by_key[unit['task_id'], 'omitted_equality']
        assert full['compiled_contract'] != weak['compiled_contract']
        assert full['input_fingerprint'] != weak['input_fingerprint']
        assert full['contract_fingerprint'] != weak['contract_fingerprint']
        left = copy.deepcopy(full['compiled_contract']); right = copy.deepcopy(weak['compiled_contract'])
        assert left.pop('obligations') == ['valid_boolean_token', 'equals_reference']
        assert right.pop('obligations') == ['valid_boolean_token'] and left == right
        assert [r['obligation_id'] for r in weak['per_obligation']] == ['valid_boolean_token']
        fidelity.append({'source_id': unit['task_id'], 'compiled_contracts_differ_only_in_obligations': True,
            'actual_consumer_inputs_differ': True,
            'full_contract_fingerprint': full['contract_fingerprint'], 'weak_contract_fingerprint': weak['contract_fingerprint'],
            'full_input_fingerprint': full['input_fingerprint'], 'weak_input_fingerprint': weak['input_fingerprint'],
            'weak_active_obligations': weak['active_obligations'], 'omitted_equality_not_reintroduced': True})
    result = {'passed': True, 'method_freeze_sha256': freeze_sha, 'bug_families': 1,
              'source_versions': len(units), 'source_generated_global_results': global_results,
              'witness_rows': witness_rows, 'interface_fidelity': fidelity,
              'native_scorer_executions': len(observations), 'static_supplied_witness_checks': len(witness_rows),
              'all_obligation_ids_and_truths_match_predefined_expectations': True,
              'all_supported_static_rewards_match_native_execution': True,
              'omitted_equality_never_activated_or_reported': True,
              'semgrep': {'reused_frozen_source_pattern_baseline': True, 'new_semgrep_scans': 0,
                          'new_per_obligation_semgrep_proof_claims': False},
              'old_files_preserved': preserve_previous(), 'old_AST_theory_changed': False,
              'new_LLM_extraction_requests': 0,
              'qualification': 'Known development case. Global valid-only Alarm can remain from invalid tokens; attribution on the opposite valid-token witness isolates reference equality. Concrete oracle and static paths are separate; only static paths consume source.'}
    write(output/'observations.json', {'observations': observations})
    write(output/'summary.json', result)
    assert verify() == freeze_sha
    return {k: result[k] for k in ['passed', 'bug_families', 'native_scorer_executions', 'static_supplied_witness_checks', 'omitted_equality_never_activated_or_reported', 'old_AST_theory_changed', 'new_LLM_extraction_requests']}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('operation', choices=['freeze', 'verify', 'run']); p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.operation == 'freeze': result = freeze()
    elif args.operation == 'verify': result = {'passed': True, 'method_freeze_sha256': verify()}
    else: result = run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
