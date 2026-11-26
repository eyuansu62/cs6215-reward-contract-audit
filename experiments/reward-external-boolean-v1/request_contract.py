"""Same frozen extraction method, new task packet; no obligation completion."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent/'reward-contract-e2e-v1/run_e2e.py'
OLD_SHA = '58657b6059f664a55e5b8783d7d07dc2bf0bac471212ab2579d08a977c16dc73'
if hashlib.sha256(OLD.read_bytes()).hexdigest() != OLD_SHA:
    raise ValueError('Frozen extraction validation changed')
spec = importlib.util.spec_from_file_location('_preserved_e2e_extractor', OLD)
previous = importlib.util.module_from_spec(spec); spec.loader.exec_module(previous)
from run_study import verify, read, write, sha


def request(output):
    scope = read(ROOT/'data/dataset-scope.json')
    if scope.get('evaluation_scorers_approved') is not True:
        raise ValueError('Dataset type choice still pending; no model call')
    method = verify(); output = Path(output).resolve()
    if output.exists(): raise ValueError('Preserve original attempts')
    output.mkdir(parents=True)
    payload = {'task': read(ROOT/'data/task.json'), 'analysis_profile': read(ROOT/'protocol/analysis-profile.json')}
    prompt = (ROOT/'protocol/prompt-prefix.txt').read_text()+json.dumps(payload, ensure_ascii=False, indent=2)
    write(output/'request.json', payload); (output/'prompt.txt').write_text(prompt)
    metadata = {'status': 'failed', 'method_freeze_sha256': method, 'request_attempted': False,
        'successful_model_turns': 0, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        'source_policy_reference_contract_and_probes_excluded': True, 'no_obligations_added_or_repaired': True}
    try:
        executable = shutil.which('codex')
        if not executable: raise ValueError('Codex CLI unavailable')
        metadata['cli_version'] = subprocess.run([executable, '--version'], text=True, capture_output=True, check=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='external-Boolean-description-') as directory:
            blind = Path(directory); schema = blind/'schema.json'
            write(schema, read(ROOT/'protocol/response-schema.json'))
            command = [executable, 'exec', '--ignore-user-config', '--skip-git-repo-check', '--ephemeral',
                       '--sandbox', 'read-only', '-c', 'project_doc_max_bytes=0', '--json', '--output-schema', str(schema),
                       '--output-last-message', str(output/'response.json'), '--cd', str(blind), '-']
            write(output/'command.json', {'argv': command, 'stdin_sha256': metadata['prompt_sha256']})
            start = time.perf_counter(); metadata['request_attempted'] = True
            result = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=240)
            metadata['wall_seconds'] = round(time.perf_counter()-start, 4); metadata['returncode'] = result.returncode
            (output/'events.jsonl').write_text(result.stdout); (output/'transport.stderr.txt').write_text(result.stderr)
            model = re.search(r'^model:\s*(.+)$', result.stderr, re.MULTILINE)
            metadata['model_reported'] = model.group(1).strip() if model else None
            if result.returncode: raise ValueError('Transport failed; no response-driven retry')
            metadata['usage'], metadata['event_count'] = previous.TRANSPORT.audit_events(result.stdout)
            metadata['successful_model_turns'] = 1; metadata['accepted_tool_actions'] = 0
            response = read(output/'response.json'); metadata['response_sha256'] = sha(output/'response.json')
            contract = previous.validate_response(response, payload['task'])
            if contract != response['contract']: raise ValueError('No contract repair permitted')
            write(output/'accepted-contract.json', {'contract': contract, 'raw_contract_unchanged': True})
            metadata['status'] = 'abstained' if contract is None else 'complete'
            metadata['selected_obligations'] = None if contract is None else contract['obligations']
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        metadata['error'] = type(error).__name__+': '+str(error)
        if isinstance(error, subprocess.TimeoutExpired):
            (output/'events.partial.txt').write_text(str(error.stdout or ''))
            (output/'transport.partial.stderr.txt').write_text(str(error.stderr or ''))
    finally:
        write(output/'metadata.json', metadata)
    assert verify() == method
    return {k: metadata.get(k) for k in ['status', 'successful_model_turns', 'selected_obligations', 'error']}


def seal(folder):
    method = verify(); folder = Path(folder).resolve(); folder.relative_to(ROOT)
    target = ROOT/'results/model-response-freeze.json'
    if target.exists(): raise ValueError('Preserve earlier response seal')
    meta = read(folder/'metadata.json')
    if meta.get('successful_model_turns') != 1: raise ValueError('No completed model turn to seal')
    model = None
    if meta['status'] in {'complete', 'abstained'}:
        raw = read(folder/'response.json'); model = previous.validate_response(raw, read(ROOT/'data/task.json'))
        assert model == raw['contract'] == read(folder/'accepted-contract.json')['contract']
    conditions = ROOT/'data/condition-contracts.json'
    if conditions.exists(): raise ValueError('Preserve condition contracts')
    write(conditions, {'conditions': {'reference': read(ROOT/'data/reference-contract.json')['contract'], 'llm': model},
                       'no_reference_or_model_abstention_filled': True})
    paths = [*sorted(p for p in folder.glob('*') if p.is_file()), conditions]
    write(target, {'created_utc': datetime.now(timezone.utc).isoformat(), 'method_freeze_sha256': method,
        'model_output': str(folder.relative_to(ROOT)), 'files_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'model_status': meta['status'], 'frozen_before_downstream_predictions': True, 'new_model_requests': 1})
    return {'model_response_freeze_sha256': sha(target), 'status': meta['status'],
            'reference_contract_is_null': read(conditions)['conditions']['reference'] is None}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('operation', choices=['request', 'seal'])
    p.add_argument('--output', type=Path); p.add_argument('--model-output', type=Path); a = p.parse_args()
    result = request(a.output) if a.operation == 'request' else seal(a.model_output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
