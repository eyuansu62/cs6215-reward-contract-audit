"""One-shot LLM selection into the frozen explicit Boolean obligation interface."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
V2 = ROOT.parent/'reward-contract-loop-v2'
sys.path.insert(0, str(V2))
from boolean_contracts import ContractError, compile_contract, evaluate_witness, fingerprint
from boolean_checker import analyze, check_witness
SPEC = importlib.util.spec_from_file_location('_preserved_extraction_transport', ROOT.parent/'reward-contract-extraction-v1/run_extraction.py')
TRANSPORT = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(TRANSPORT)
WORKER = BASE/'datasets/reasoning-gym-reward-v1/repro/reproduce.py'
V2_FREEZE = 'e6db263e27555a1b68aa15389e94ce6f1cb4468ddf6d2cc6b88b3489fccb49da'
TRANSPORT_SHA = '2f87c1461c9b50ac621a838425042d59a7ade098109b58bbc02d3f4617dac4cb'


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def preserve():
    assert sha(V2/'method-freeze.json') == V2_FREEZE
    for name, digest in read(V2/'method-freeze.json')['files_sha256'].items():
        assert sha(V2/name) == digest, name
    assert sha(WORKER) == read(V2/'method-freeze.json')['worker_sha256']
    assert sha(Path(TRANSPORT.__file__)) == TRANSPORT_SHA
    manifest = V2/'artifact-files-sha256.json'
    records = read(manifest)['files_sha256']
    for name, digest in records.items(): assert sha(BASE/name) == digest, name
    return {'v2_method_sha256': V2_FREEZE, 'v2_manifest_sha256': sha(manifest),
            'preserved_payloads': len(records), 'transport_sha256': sha(Path(TRANSPORT.__file__)),
            'worker_sha256': sha(WORKER)}


def method_files():
    paths = [*ROOT.glob('*.py'), *(ROOT/'tests').glob('*.py'), *(ROOT/'protocol').glob('*'),
             ROOT/'inputs.json', ROOT/'archived-observations.json', ROOT/'audit/description-provenance.json']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths) if p.is_file()}


def freeze():
    path = ROOT/'method-freeze.json'
    if path.exists(): raise ValueError('Preserve earlier method freeze')
    write(path, {'created_utc': datetime.now(timezone.utc).isoformat(),
                 'files_sha256': method_files(), 'preserved_previous': preserve(),
                 'reference_and_prompt_frozen_before_model_response': True,
                 'one_known_case_one_model_request': True, 'new_analyzer_semantics': False})
    return {'method_freeze_sha256': verify()}


def verify():
    frozen = read(ROOT/'method-freeze.json')
    assert method_files() == frozen['files_sha256'], 'Frozen new method/protocol/reference changed'
    assert preserve() == frozen['preserved_previous']
    return sha(ROOT/'method-freeze.json')


def validate_response(response, task):
    """Validate without comparing to the reference or inserting any obligation."""
    fields = {'task_id', 'status', 'contract', 'evidence', 'not_specified', 'abstention_reason'}
    if type(response) is not dict or set(response) != fields: raise ValueError('response_fields_must_be_exact')
    if response['task_id'] != task['task_id']: raise ValueError('wrong_task_id')
    if type(response['not_specified']) is not list or any(type(x) is not str for x in response['not_specified']):
        raise ValueError('not_specified_must_be_string_list')
    if type(response['evidence']) is not list: raise ValueError('evidence_must_be_list')
    if response['status'] == 'abstain':
        if response['contract'] is not None or response['evidence'] or type(response['abstention_reason']) is not str or not response['abstention_reason'].strip():
            raise ValueError('invalid_abstention')
        return None
    if response['status'] != 'extracted' or response['abstention_reason'] is not None:
        raise ValueError('unsupported_response_status')
    compiled = compile_contract(response['contract'])
    assert compiled == response['contract'], 'Compiler must not complete or repair contract'
    selected = compiled['obligations']; supported = set()
    for item in response['evidence']:
        if type(item) is not dict or set(item) != {'obligation_id', 'quote', 'reason'}:
            raise ValueError('invalid_evidence_shape')
        if any(type(item[k]) is not str for k in item): raise ValueError('evidence_fields_must_be_strings')
        if item['obligation_id'] not in selected: raise ValueError('evidence_for_inactive_obligation')
        if not item['quote'] or item['quote'] not in task['question_description']:
            raise ValueError('evidence_quote_not_in_question')
        if not item['reason'].strip(): raise ValueError('empty_evidence_reason')
        supported.add(item['obligation_id'])
    if supported != set(selected): raise ValueError('selected_obligation_lacks_evidence')
    return compiled


def prompt_payload():
    return {'task': read(ROOT/'protocol/task.json'),
            'analysis_profile': read(ROOT/'protocol/analysis-profile.json')}


def request(output):
    frozen_sha = verify(); output = Path(output).resolve()
    if output.exists(): raise ValueError('Preserve all earlier attempts')
    output.mkdir(parents=True)
    payload = prompt_payload(); prompt = (ROOT/'protocol/prompt-prefix.txt').read_text()+json.dumps(payload, ensure_ascii=False, indent=2)
    write(output/'request.json', payload); (output/'prompt.txt').write_text(prompt)
    metadata = {'status': 'failed', 'request_attempted': False, 'successful_model_turns': 0,
        'method_freeze_sha256': frozen_sha, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        'source_reference_contract_and_probe_inputs_excluded': True,
        'profile_is_researcher_supplied_not_extracted': True}
    try:
        executable = shutil.which('codex')
        if not executable: raise ValueError('Codex unavailable; no response fabricated')
        metadata['cli_version'] = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='explicit-boolean-blind-') as temp:
            blind = Path(temp); schema = blind/'response-schema.json'
            write(schema, read(ROOT/'protocol/response-schema.json'))
            command = [executable, 'exec', '--ignore-user-config', '--skip-git-repo-check', '--ephemeral',
                       '--sandbox', 'read-only', '-c', 'project_doc_max_bytes=0', '--json',
                       '--output-schema', str(schema), '--output-last-message', str(output/'response.json'), '--cd', str(blind), '-']
            write(output/'command.json', {'argv': command, 'stdin_sha256': metadata['prompt_sha256']})
            metadata['request_attempted'] = True; start = time.perf_counter()
            result = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=240)
            metadata['wall_seconds'] = round(time.perf_counter()-start, 4)
            (output/'events.jsonl').write_text(result.stdout); (output/'transport.stderr.txt').write_text(result.stderr)
            metadata['returncode'] = result.returncode
            match = re.search(r'^model:\s*(.+)$', result.stderr, re.MULTILINE)
            metadata['model_reported'] = match.group(1).strip() if match else None
            metadata['model_identity_note'] = 'Exact model unknown when CLI service does not disclose it.'
            if result.returncode: raise ValueError('Transport failed; retained logs, no outcome-based retry')
            metadata['usage'], metadata['event_count'] = TRANSPORT.audit_events(result.stdout)
            metadata['successful_model_turns'] = 1; metadata['accepted_tool_actions'] = 0
            response = read(output/'response.json'); metadata['response_sha256'] = sha(output/'response.json')
            contract = validate_response(response, payload['task'])
            write(output/'accepted-contract.json', {'contract': contract, 'origin': 'Exact model-selected IR; no obligations added', 'raw_contract_unchanged': contract == response['contract']})
            metadata['status'] = 'abstained' if contract is None else 'complete'
            metadata['selected_obligations'] = None if contract is None else contract['obligations']
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        metadata['error'] = type(error).__name__+': '+str(error)
        if isinstance(error, subprocess.TimeoutExpired):
            (output/'events.partial.txt').write_text(str(error.stdout or ''))
            (output/'transport.partial.stderr.txt').write_text(str(error.stderr or ''))
    finally:
        write(output/'metadata.json', metadata)
    assert verify() == frozen_sha
    return {k: metadata.get(k) for k in ['status', 'successful_model_turns', 'selected_obligations', 'error']}


def seal_model(model_output):
    verify(); folder = Path(model_output).resolve(); target = ROOT/'model-response-freeze.json'
    if target.exists(): raise ValueError('Preserve model-response freeze')
    folder.relative_to(ROOT)
    metadata = read(folder/'metadata.json')
    if metadata.get('successful_model_turns') != 1: raise ValueError('No successful model turn to seal')
    write(target, {'created_utc': datetime.now(timezone.utc).isoformat(), 'method_freeze_sha256': verify(),
        'model_output': str(folder.relative_to(ROOT)), 'files_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(folder.glob('*')) if p.is_file()},
        'model_status': metadata['status'], 'model_response_retries': 0, 'frozen_before_downstream': True})
    return {'model_response_freeze_sha256': sha(target), 'status': metadata['status']}


def saved_model_contract():
    frozen = read(ROOT/'model-response-freeze.json'); assert frozen['method_freeze_sha256'] == verify()
    for name, digest in frozen['files_sha256'].items(): assert sha(ROOT/name) == digest
    folder = ROOT/frozen['model_output']; meta = read(folder/'metadata.json')
    if meta['status'] not in {'complete', 'abstained'}: return None, meta
    raw = read(folder/'response.json'); contract = validate_response(raw, read(ROOT/'protocol/task.json'))
    assert read(folder/'accepted-contract.json')['contract'] == contract == raw['contract']
    return contract, meta


def run(output):
    method_sha = verify(); model, meta = saved_model_contract(); output = Path(output).resolve()
    if output.exists(): raise ValueError('Preserve earlier downstream output')
    output.mkdir(parents=True)
    reference = read(ROOT/'protocol/reference-contract.json')['contract']
    conditions = {'reference': reference, 'llm': model}
    units = read(ROOT/'inputs.json')['units']; globals_ = []; by_key = {}
    for unit in units:
        for condition, contract in conditions.items():
            result = analyze(copy.deepcopy(unit), copy.deepcopy(contract))
            if contract is not None:
                assert result['compiled_contract'] == contract
                assert result['active_obligations'] == contract['obligations']
            write(output/'global'/unit['task_id']/(condition+'.json'), result)
            globals_.append({'source_id': unit['task_id'], 'condition': condition, **result}); by_key[unit['task_id'], condition] = result
    observations = []; rows = []
    manual = read(ROOT/'protocol/reference-expected.json')['witness_rows']
    for record in read(ROOT/'archived-observations.json')['observations']:
        command = [sys.executable, '-I', '-B', str(WORKER), 'worker', '--case', record['source_id'], '--probe', record['probe_id']]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=8)
        destination = output/'reproduction'/record['source_id']/record['probe_id'].replace('/', '__'); destination.mkdir(parents=True)
        (destination/'stdout.txt').write_text(proc.stdout); (destination/'stderr.txt').write_text(proc.stderr)
        write(destination/'command.json', {'argv': command, 'returncode': proc.returncode, 'timeout_seconds': 8})
        assert proc.returncode == 0, proc.stderr
        observed = json.loads(proc.stdout); assert observed == record['frozen_observation']
        observations.append({**record, 'current_observation': observed})
        unit = next(u for u in units if u['task_id'] == record['source_id']); decisions = {}
        expected = next(x for x in manual if x['source_id'] == record['source_id'] and x['probe_id'] == record['probe_id'])
        predicate_truth = {x['obligation_id']: x for x in expected['per_obligation']}
        for condition, contract in conditions.items():
            source = check_witness(copy.deepcopy(unit), copy.deepcopy(contract), record['answer'], record['entry']['answer'])
            oracle = evaluate_witness(contract, record['answer'], record['entry']['answer'], observed['reward'])
            for field in ['verdict', 'active_obligations', 'per_obligation', 'violated_obligations']:
                assert source[field] == oracle[field], (field, source, oracle)
            if contract is not None:
                assert source['reward'] == observed['reward']
                assert source['compiled_contract'] == contract
                assert source['input_fingerprint'] == by_key[record['source_id'], condition]['input_fingerprint']
                assert source['per_obligation'] == [predicate_truth[o] for o in contract['obligations']]
                assert all(x['obligation_id'] in contract['obligations'] for x in source['per_obligation'])
            decisions[condition] = {'static': source, 'concrete_oracle': oracle}
        ref_ids = decisions['reference']['static']['violated_obligations']; model_ids = decisions['llm']['static']['violated_obligations']
        rows.append({'source_id': record['source_id'], 'probe_id': record['probe_id'], 'answer': record['answer'], 'reference': record['entry']['answer'],
                     'executed_reward': observed['reward'], 'conditions': decisions,
                     'same_witness_verdict': decisions['reference']['static']['verdict'] == decisions['llm']['static']['verdict'],
                     'same_violated_obligation_ids': set(ref_ids) == set(model_ids),
                     'reference_violations_not_attributed_by_model_contract': sorted(set(ref_ids)-set(model_ids)),
                     'extra_model_contract_violation_ids': sorted(set(model_ids)-set(ref_ids))})
    missing = sorted(set(reference['obligations'])-set(model['obligations'])) if model else reference['obligations']
    result = {'passed': True, 'method_freeze_sha256': method_sha, 'model_response_freeze_sha256': sha(ROOT/'model-response-freeze.json'),
        'reference_contract': reference, 'model_contract': model, 'model_status': meta['status'],
        'raw_model_contract_preserved': model is None or model == read(ROOT/read(ROOT/'model-response-freeze.json')['model_output']/'response.json')['contract'],
        'selected_obligations_match_reference_as_set': model is not None and set(model['obligations']) == set(reference['obligations']),
        'missing_reference_obligations': missing,
        'missing_id_interpretation': 'Structural list difference, not necessarily semantic insufficiency: equals_reference implies token validity under the fixed canonical reference.', 'global_results': globals_, 'witness_rows': rows,
        'native_scorer_executions': len(observations), 'condition_witness_rows': len(rows)*2,
        'same_witness_verdicts': sum(r['same_witness_verdict'] for r in rows),
        'same_violated_obligation_id_sets': sum(r['same_violated_obligation_ids'] for r in rows),
        'all_available_static_rewards_match_native_execution': True, 'no_auto_completion': True,
        'v2_interface_and_analyzer_changes': False, 'new_model_calls_by_downstream': 0,
        'qualification': 'Single known development case with a supplied two-atom vocabulary/profile. Matching reference results establishes this integration only, not neural gain or generalization.'}
    write(output/'observations.json', {'observations': observations}); write(output/'summary.json', result)
    assert verify() == method_sha
    return {k: result[k] for k in ['passed', 'model_status', 'selected_obligations_match_reference_as_set', 'missing_reference_obligations', 'condition_witness_rows', 'same_witness_verdicts', 'same_violated_obligation_id_sets', 'v2_interface_and_analyzer_changes']}


def replay(old, new, output):
    if Path(output).exists(): raise ValueError('Preserve earlier replay check')
    assert Path(old).read_bytes() == Path(new).read_bytes(), 'Analytical rerun summary differs'
    result = {'passed': True, 'byte_identical_analytical_summary': True, 'method_freeze_sha256': verify(),
              'model_response_freeze_sha256': sha(ROOT/'model-response-freeze.json'),
              'new_model_calls': 0, 'same_machine_only': True}
    write(output, result); return result


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('operation', choices=['freeze', 'verify', 'request', 'seal-model', 'run', 'replay'])
    p.add_argument('--output', type=Path); p.add_argument('--model-output', type=Path); p.add_argument('--old', type=Path); p.add_argument('--new', type=Path)
    a = p.parse_args()
    if a.operation == 'freeze': r = freeze()
    elif a.operation == 'verify': r = {'passed': True, 'method_freeze_sha256': verify()}
    elif a.operation == 'request': r = request(a.output)
    elif a.operation == 'seal-model': r = seal_model(a.model_output)
    elif a.operation == 'run': r = run(a.output)
    else: r = replay(a.old, a.new, a.output)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
