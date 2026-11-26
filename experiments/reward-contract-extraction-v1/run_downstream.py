"""Run preserved analyzers with two frozen contract-input conditions."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tools'))
from downstream import run_condition, verify_frozen_baseline
from run_extraction import verify as verify_extraction


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def verify():
    f = read(ROOT/'downstream-input-freeze.json')
    for name, digest in f['files_sha256'].items():
        assert sha(ROOT/name) == digest, 'Frozen downstream input/method changed: '+name
    assert verify_extraction() == f['extraction_freeze_sha256']
    assert verify_frozen_baseline()['analyzer_files_unchanged']
    model_freeze = read(ROOT/'results/model-response-freeze.json')
    for name, digest in model_freeze['files_sha256'].items():
        assert sha(ROOT/name) == digest
    return sha(ROOT/'downstream-input-freeze.json')


def prepare():
    assert not (ROOT/'downstream-input-freeze.json').exists()
    accepted = []
    statuses = []
    for i in range(1, 7):
        tid = f'T{i:02d}'; folder = ROOT/'results/extraction-02'/tid
        metadata = read(folder/'metadata.json')
        statuses.append({'task_id': tid, 'validation_status': metadata['status'],
                         'error': metadata.get('error')})
        if metadata['status'] == 'complete':
            accepted.append(read(folder/'validated-contract.json'))
    reference = read(ROOT/'reference/contracts.json')['contracts']
    units = read(ROOT/'collection/source-units.json')['units']
    assert len(units) == len(reference) == 6
    assert {u['task_id'] for u in units} == {c['task_id'] for c in reference}
    condition_file = ROOT/'results/condition-inputs.json'
    assert not condition_file.exists()
    write(condition_file, {'conditions': {'llm': accepted, 'reference': reference},
                          'model_validation': statuses,
                          'rejected_model_responses_not_repaired_or_passed': True,
                          'reference_authorship': 'AI-assisted researcher reference, not a human experiment'})
    files = [ROOT/'run_downstream.py', ROOT/'tools/downstream.py', ROOT/'tools/test_downstream.py',
             ROOT/'protocol/design.json', ROOT/'downstream-method-freeze.json',
             ROOT/'collection/source-units.json', ROOT/'collection/source-unit-provenance.json',
             ROOT/'collection/canonical-reference-evidence.json', ROOT/'collection/source-preparation-checks.json',
             ROOT/'collection/prepare_source_units.py', condition_file,
             ROOT/'results/model-response-freeze.json']
    write(ROOT/'downstream-input-freeze.json', {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'files_sha256': {str(p.relative_to(ROOT)): sha(p) for p in files},
        'extraction_freeze_sha256': verify_extraction(),
        'frozen_before_downstream_predictions': True,
        'source_preparation_executed_targets': False})
    return {'passed': True, 'freeze_sha256': verify(), 'accepted_llm_contracts': len(accepted),
            'reference_contracts': len(reference), 'source_units': len(units)}


def run(condition, output):
    before = verify()
    contracts = read(ROOT/'results/condition-inputs.json')['conditions'][condition]
    units = read(ROOT/'collection/source-units.json')['units']
    result = run_condition(units, contracts, output)
    write(Path(output)/'run-metadata.json', {'condition': condition, 'input_freeze_sha256': before,
        'predictions_sha256': sha(Path(output)/'predictions.json'), 'reference_is_AI_assisted': True,
        'LLM_or_targets_executed_by_this_run': False})
    assert verify() == before
    return result['summary']


def compare_conditions(reference_path, llm_path, output):
    assert not Path(output).exists()
    a, b = read(reference_path), read(llm_path)
    expected = {f'T{i:02d}' for i in range(1, 7)}
    for record in [a, b]:
        ids = [row['task_id'] for row in record['cases']]
        assert len(ids) == len(set(ids)) == 6 and set(ids) == expected
    assert a['source_units_sha256'] == b['source_units_sha256']
    assert a['preserved_baseline'] == b['preserved_baseline']
    rows = []
    for x, y in zip(a['cases'], b['cases']):
        assert x['task_id'] == y['task_id']
        rows.append({'task_id': x['task_id'],
                     'reference_projection': x['projection'], 'llm_projection': y['projection'],
                     'same_compiled_detector_input': (x.get('detector_input_sha256') == y.get('detector_input_sha256')) if x['projection']['supported'] and y['projection']['supported'] else None,
                     'methods': {m: {'reference': x['methods'][m]['verdict'],
                                    'llm': y['methods'][m]['verdict'],
                                    'changed': x['methods'][m]['verdict'] != y['methods'][m]['verdict']}
                                 for m in ['semgrep', 'symbolic']}})
    assert len(rows) == 6
    out = {'input_freeze_sha256': verify(), 'reference_summary': a['summary'], 'llm_summary': b['summary'],
           'cases': rows, 'changed_verdicts': sum(z['changed'] for r in rows for z in r['methods'].values()),
           'distinct_supported_detector_inputs': {n: len({r['detector_input_sha256'] for r in p['cases'] if r['projection']['supported']}) for n, p in [('reference', a), ('llm', b)]},
           'classification_accuracy_not_calculated': 'No frozen independent positive/negative oracle for the six full task contracts. No alarm does not imply no defect.',
           'improved_detection_demonstrated': False,
           'interpretation': 'Only existing necessary-condition projections are consumed. Equal projections and verdicts cannot demonstrate benefit from richer extracted task semantics.'}
    write(output, out)
    return {k: out[k] for k in ['changed_verdicts', 'distinct_supported_detector_inputs', 'improved_detection_demonstrated']}


def normalize(value, origin):
    if isinstance(value, dict):
        return {k: normalize(v, origin) for k, v in value.items() if k not in {'wall_seconds', 'bridge_wall_seconds', 'command'}}
    if isinstance(value, list): return [normalize(v, origin) for v in value]
    if isinstance(value, str): return value.replace(origin, '<run>')
    return value


def replay(old_path, new_path, output):
    assert not Path(output).exists()
    a, b = read(old_path), read(new_path)
    assert normalize(a, a['condition_output']) == normalize(b, b['condition_output']), 'Analytical replay mismatch'
    scans = 0
    for x, y in zip(a['cases'], b['cases']):
        assert x['task_id'] == y['task_id']
        for row, run_record, prediction_path in [(x, a, old_path), (y, b, new_path)]:
            sg = row['methods']['semgrep']
            if sg.get('status') != 'complete': continue
            assert sg['engine']['sha256'] == '8b0c1fa10fa70372ea64ca0dc9cf3de0fd53db9c2556f6af5f973e8df12d4995'
            for record in [sg, sg['coverage']]:
                cmd = record['command']
                def local_file(value):
                    return Path(prediction_path).parent/Path(value).relative_to(run_record['condition_output'])
                rules = local_file(cmd[cmd.index('-rules')+1]); source = local_file(cmd[-1])
                assert sha(rules) == record['rule_sha256']
                assert sha(source) == row['source_sha256']
        sx, sy = x['methods']['semgrep'], y['methods']['semgrep']
        if sx.get('status') == 'complete':
            for rx, ry in [(sx, sy), (sx['coverage'], sy['coverage'])]:
                def flags(record):
                    cmd = record['command'][:]; cmd[0] = '<core>'
                    cmd[cmd.index('-rules')+1] = '<verified-rules>'; cmd[-1] = '<verified-source>'
                    return cmd
                assert flags(rx) == flags(ry)
            scans += 1
    result = {'passed': True, 'input_freeze_sha256': verify(), 'task_condition_rows': 6,
              'full_parsed_analytical_outputs_equal': True, 'completed_semgrep_scans_verified': scans,
              'separate_pattern_and_coverage_commands_verified': scans*2,
              'normalization': ['run paths', 'wall_seconds', 'bridge_wall_seconds', 'commands with bytes and flags verified separately'],
              'same_machine': True, 'new_LLM_or_target_runs': 0}
    write(output, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['prepare', 'verify', 'run', 'compare', 'replay'])
    p.add_argument('--condition', choices=['reference', 'llm'])
    p.add_argument('--output', type=Path); p.add_argument('--reference', type=Path); p.add_argument('--llm', type=Path)
    p.add_argument('--old', type=Path); p.add_argument('--new', type=Path)
    a = p.parse_args()
    if a.operation == 'prepare': r = prepare()
    elif a.operation == 'verify': r = {'passed': True, 'freeze_sha256': verify()}
    elif a.operation == 'run': r = run(a.condition, a.output)
    elif a.operation == 'compare': r = compare_conditions(a.reference, a.llm, a.output)
    else: r = replay(a.old, a.new, a.output)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
