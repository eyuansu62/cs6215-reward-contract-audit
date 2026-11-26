"""Frozen one-shot description-only LLM requests, with blind-event audit."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
OLD = BASE/'experiments/reward-baselines-v1'
OLD_SHA = '0925274a7d4b18780fabc611d75c03e0dc9066ef426781ca1a85a2b33edeb1de'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def verify_old():
    assert sha(OLD/'method-freeze.json') == OLD_SHA, 'Old baseline freeze changed'
    frozen = read(OLD/'method-freeze.json')
    for group in ['files_sha256', 'inputs_sha256']:
        for name, expected in frozen[group].items():
            assert sha(OLD/name) == expected, 'Old baseline changed: '+name
    return OLD_SHA


def extraction_files():
    paths = [ROOT/'run_extraction.py', ROOT/'test_extraction.py',
             ROOT/'reference/contracts.json', ROOT/'reference/review.json', ROOT/'reference/annotation-notes.md',
             ROOT/'collection/blind-task-descriptions.json',
             ROOT/'collection/description-packet-freeze.json',
             *sorted((ROOT/'protocol').glob('*'))]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths if p.is_file()}


def freeze():
    path = ROOT/'extraction-freeze.json'
    if path.exists():
        raise ValueError('Preserve earlier extraction freeze')
    for required in ['reference/contracts.json', 'reference/review.json', 'test_extraction.py']:
        assert (ROOT/required).is_file(), required
    assert read(ROOT/'reference/review.json')['passed']
    write(path, {'created_utc': datetime.now(timezone.utc).isoformat(),
                 'files_sha256': extraction_files(), 'old_method_sha256': verify_old(),
                 'reference_frozen_before_model_responses': True,
                 'reference_authorship': 'AI-assisted researcher reference; no actual human annotation',
                 'scorer_content_not_read_before_extraction': True,
                 'model_selection': 'Codex CLI service default with user config ignored; actual identity recorded if exposed',
                 'requests': 6, 'outcome_tuning_or_retries': False})
    return {'freeze_sha256': sha(path), 'files': len(read(path)['files_sha256'])}


def verify():
    freeze_path = ROOT/'extraction-freeze.json'
    frozen = read(freeze_path)
    assert extraction_files() == frozen['files_sha256'], 'Extraction method/reference changed'
    assert verify_old() == frozen['old_method_sha256']
    return sha(freeze_path)


def validate_schema(value, schema, location='$'):
    """Small recursive validator for this fixed schema's object/array/scalar subset."""
    types = schema['type']
    types = [types] if isinstance(types, str) else types
    matches = {'object': type(value) is dict, 'array': type(value) is list,
               'string': type(value) is str, 'number': type(value) in (int, float),
               'null': value is None}
    if not any(matches[t] for t in types):
        raise ValueError(location+': wrong JSON type')
    if type(value) is float and not math.isfinite(value):
        raise ValueError(location+': nonfinite number is not JSON')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(location+': unknown enum')
    if type(value) is dict:
        props = schema['properties']
        if set(value) != set(schema['required']) or set(value)-set(props):
            raise ValueError(location+': missing/unexpected fields')
        for key, child in value.items():
            validate_schema(child, props[key], location+'.'+key)
    elif type(value) is list:
        for i, child in enumerate(value):
            validate_schema(child, schema['items'], location+'['+str(i)+']')


def validate_contract(response, task):
    validate_schema(response, read(ROOT/'protocol/response-schema.json'))
    if response['task_id'] != task['task_id']:
        raise ValueError('Response ID differs from blind task ID')
    for evidence in response['evidence']:
        if not evidence['quote'] or evidence['quote'] not in task['question_description']:
            raise ValueError('Evidence quote not an exact description substring')
    return response


def audit_events(raw):
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    allowed = {'thread.started', 'turn.started', 'item.started', 'item.updated',
               'item.completed', 'turn.completed'}
    completed = []
    for event in events:
        if event.get('type') not in allowed:
            raise ValueError('Unexpected/failed event: '+str(event.get('type')))
        item = event.get('item')
        if isinstance(item, dict) and item.get('type') not in {'agent_message', 'reasoning'}:
            raise ValueError('Tool/action event violates blinding: '+str(item.get('type')))
        if event['type'] == 'turn.completed':
            completed.append(event)
    if len(completed) != 1:
        raise ValueError('Expected one successful model turn')
    return completed[0].get('usage'), len(events)


def request(task, output):
    freeze_sha = verify()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Preserve previous attempts; no silent overwrite')
    output.mkdir(parents=True)
    payload = {k: task[k] for k in ['task_id', 'question_description', 'placeholder_notes']}
    prompt = (ROOT/'protocol/prompt-prefix.txt').read_text()+json.dumps(payload, ensure_ascii=False, indent=2)
    write(output/'request.json', payload)
    (output/'prompt.txt').write_text(prompt)
    executable = shutil.which('codex')
    metadata = {'task_id': task['task_id'], 'status': 'failed', 'model_called': False,
                'extraction_freeze_sha256': freeze_sha,
                'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                'request_inputs': ['opaque ID', 'description', 'placeholder notes', 'generic schema'],
                'no_reference_scorer_or_history_in_prompt': True}
    try:
        if not executable:
            raise ValueError('Codex CLI unavailable; do not fabricate response')
        metadata['cli_version'] = subprocess.run([executable, '--version'], text=True,
                                                 capture_output=True, check=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='rg-contract-blind-') as directory:
            blind = Path(directory)
            schema_path = blind/'schema.json'
            write(schema_path, read(ROOT/'protocol/response-schema.json'))
            command = [executable, 'exec', '--ignore-user-config', '--skip-git-repo-check',
                       '--ephemeral', '--sandbox', 'read-only', '-c', 'project_doc_max_bytes=0',
                       '--json', '--output-schema', str(schema_path),
                       '--output-last-message', str(output/'response.json'), '--cd', str(blind), '-']
            write(output/'command.json', {'argv': command, 'stdin_sha256': metadata['prompt_sha256']})
            start = time.perf_counter()
            metadata['model_called'] = True
            result = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=240)
            metadata['wall_seconds'] = round(time.perf_counter()-start, 4)
            (output/'events.jsonl').write_text(result.stdout)
            (output/'transport.stderr.txt').write_text(result.stderr)
            metadata['returncode'] = result.returncode
            model = re.search(r'^model:\s*(.+)$', result.stderr, re.MULTILINE)
            metadata['model_reported'] = model.group(1).strip() if model else None
            metadata['model_identity_note'] = 'Exact model unknown if service does not expose it; no latest-model claim'
            if result.returncode:
                raise ValueError('Codex transport failed; inspect preserved logs')
            metadata['usage'], metadata['event_count'] = audit_events(result.stdout)
            metadata['accepted_tool_actions'] = 0
            response = validate_contract(read(output/'response.json'), task)
            write(output/'validated-contract.json', response)
            metadata['status'] = 'complete'
            metadata['response_sha256'] = sha(output/'response.json')
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        metadata['error'] = type(error).__name__+': '+str(error)
        if isinstance(error, subprocess.TimeoutExpired):
            (output/'events.partial.txt').write_text(str(error.stdout or ''))
            (output/'transport.partial.stderr.txt').write_text(str(error.stderr or ''))
    finally:
        write(output/'metadata.json', metadata)
    assert verify() == freeze_sha
    return {k: metadata.get(k) for k in ['task_id', 'status', 'model_called', 'error']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['freeze', 'verify', 'request'])
    parser.add_argument('--task-id')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.operation == 'freeze':
        result = freeze()
    elif args.operation == 'verify':
        result = {'passed': True, 'freeze_sha256': verify()}
    else:
        tasks = read(ROOT/'collection/blind-task-descriptions.json')['tasks']
        task = next(t for t in tasks if t['task_id'] == args.task_id)
        result = request(task, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
