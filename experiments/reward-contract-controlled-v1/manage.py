"""Seal a single controlled study and submit its precommitted twelve requests."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time

from common import (ROOT, BASE, read, sha, write_new, method_paths, verify_method,
                    verify_dependencies, verify_preflight, legacy)


def now():
    return datetime.now(timezone.utc).isoformat()


def freeze():
    if (ROOT/'method-freeze.json').exists():
        raise ValueError('Never overwrite a method freeze')
    review = read(ROOT/'audit/pre-model-review.json')
    if review.get('passed') is not True:
        raise ValueError('Pre-model review has not passed')
    current = {str(p.relative_to(ROOT)): sha(p) for p in method_paths()}
    if review.get('reviewed_method_files_sha256') != current:
        raise ValueError('Pre-model review does not bind the current complete method')
    tasks = read(ROOT/'data/test-cards.json')['tasks']
    labels = read(ROOT/'data/labels.json')['labels']
    assert len(tasks) == len(labels) == 12
    assert {x['task_id'] for x in tasks} == {x['task_id'] for x in labels}
    assert len({x['family'] for x in labels}) == 4
    assert all(sum(x['semantic_class'] == label for x in labels) == 4 for label in ['E','V','U'])
    verify_dependencies()
    write_new(ROOT/'method-freeze.json', {
        'created_utc': now(), 'files_sha256': current,
        'dependencies_sha256': verify_dependencies(),
        'prior_files_snapshot_sha256': sha(ROOT/'audit/prior-files.json'),
        'pre_model_review_sha256': sha(ROOT/'audit/pre-model-review.json'),
        'frozen_before_six_standard_combinations': True,
        'frozen_before_rule_test_predictions_and_model_requests': True,
        'new_analyzer_semantics': False, 'requests_planned': 12, 'outcome_tuning': False})
    return {'method_freeze_sha256': verify_method()}


def rules():
    method = verify_method()
    gate = verify_preflight()
    from rule_extractor import extract
    records = []
    profile = read(ROOT/'protocol/analysis-profile.json')
    for task in read(ROOT/'data/test-cards.json')['tasks']:
        record = {'task_id': task['task_id'], 'response': None, 'contract': None, 'status': 'rejected', 'error': None}
        try:
            record['response'] = extract(task, profile)
            record['contract'] = legacy().validate_response(record['response'], task)
            assert record['contract'] == record['response']['contract']
            record['status'] = 'abstained' if record['contract'] is None else 'complete'
        except (ValueError, TypeError, KeyError, AssertionError) as error:
            record['error'] = type(error).__name__+': '+str(error)
        records.append(record)
    write_new(ROOT/'results/rule-extraction.json', {'created_utc': now(),
        'method_freeze_sha256': method, 'preflight_sha256': gate, 'records': records,
        'test_predictions_after_freeze': True, 'rules_not_tuned_on_test': True})
    return {'rule_test_responses': len(records), 'rule_extraction_sha256': sha(ROOT/'results/rule-extraction.json')}


def request_one(task, method, gate):
    output = ROOT/'results/extraction'/task['task_id']
    output.mkdir(parents=True, exist_ok=False)
    payload = {'task': {k: task[k] for k in ['task_id','question_description','placeholder_notes']},
               'analysis_profile': read(ROOT/'protocol/analysis-profile.json')}
    prompt = (ROOT/'protocol/prompt-prefix.txt').read_text()+json.dumps(payload, ensure_ascii=False, indent=2)
    write_new(output/'request.json', payload)
    (output/'prompt.txt').write_text(prompt)
    meta = {'task_id': task['task_id'], 'created_utc': now(), 'status': 'failed',
            'method_freeze_sha256': method, 'preflight_sha256': gate,
            'request_attempted': False, 'successful_model_turns': 0,
            'completed_turns_observed': 0, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
            'model_reported': None, 'no_retries': True, 'no_obligations_repaired': True,
            'label_family_source_reference_contract_and_results_excluded': True}
    stage = 'transport'
    try:
        executable = shutil.which('codex')
        if not executable:
            raise ValueError('Codex CLI unavailable; no substitute response')
        meta['cli_version'] = subprocess.run([executable,'--version'], capture_output=True, text=True, check=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='controlled-contract-blind-') as directory:
            blind = Path(directory)
            schema = blind/'response-schema.json'
            write_new(schema, read(ROOT/'protocol/response-schema.json'))
            argv = [executable,'exec','--ignore-user-config','--skip-git-repo-check','--ephemeral',
                    '--sandbox','read-only','-c','project_doc_max_bytes=0','--json',
                    '--output-schema',str(schema),'--output-last-message',str(output/'response.json'),
                    '--cd',str(blind),'-']
            write_new(output/'command.json', {'argv': argv, 'stdin_sha256': meta['prompt_sha256']})
            meta['request_attempted'] = True
            started = time.perf_counter()
            try:
                proc = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=240)
            finally:
                meta['wall_seconds'] = round(time.perf_counter()-started, 4)
            (output/'events.jsonl').write_text(proc.stdout)
            (output/'transport.stderr.txt').write_text(proc.stderr)
            meta['returncode'] = proc.returncode
            match = re.search(r'^model:\s*(.+)$', proc.stderr, re.MULTILINE)
            if match:
                meta['model_reported'] = match.group(1).strip()
            meta['model_identity_note'] = 'Observed default service; exact identity remains unknown if not exposed. Temperature/seed not recorded.'
            for line in proc.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get('type') == 'turn.completed':
                    meta['completed_turns_observed'] += 1
                    meta['observed_completed_usage'] = event.get('usage')
            if proc.returncode:
                raise ValueError('CLI transport failure; no automatic retry')
            meta['usage'], meta['event_count'] = legacy().TRANSPORT.audit_events(proc.stdout)
            meta['successful_model_turns'] = 1
            meta['accepted_tool_actions'] = 0
            stage = 'admission'
            response = read(output/'response.json')
            meta['response_sha256'] = sha(output/'response.json')
            contract = legacy().validate_response(response, task)
            if contract != response['contract']:
                raise ValueError('Compiler changed model contract')
            write_new(output/'accepted-contract.json', {'contract': contract, 'raw_contract_unchanged': True})
            meta['status'] = 'abstained' if contract is None else 'complete'
            meta['selected_obligations'] = None if contract is None else contract['obligations']
    except (ValueError, OSError, KeyError, TypeError, AssertionError, subprocess.SubprocessError) as error:
        meta['status'] = 'rejected' if stage == 'admission' else 'failed'
        meta['error'] = type(error).__name__+': '+str(error)
        if isinstance(error, subprocess.TimeoutExpired):
            for name, data in [('events.partial.txt', error.stdout), ('transport.partial.stderr.txt',error.stderr)]:
                (output/name).write_text(data.decode(errors='replace') if isinstance(data,bytes) else data or '')
    finally:
        write_new(output/'metadata.json', meta)
    return {k: meta.get(k) for k in ['task_id','status','successful_model_turns','error']}


def request_all():
    method, gate = verify_method(), verify_preflight()
    if not (ROOT/'results/rule-extraction.json').exists():
        raise ValueError('Record frozen rule predictions before model batch')
    if (ROOT/'results/batch-start.json').exists():
        raise ValueError('One batch only; preserve all attempts')
    tasks = read(ROOT/'data/test-cards.json')['tasks']
    write_new(ROOT/'results/batch-start.json', {'created_utc':now(), 'method_freeze_sha256':method,
        'preflight_sha256':gate, 'rule_extraction_sha256':sha(ROOT/'results/rule-extraction.json'),
        'task_order':[t['task_id'] for t in tasks], 'planned_requests':12, 'parallelism':3, 'retries':0})
    legacy()  # Load immutable validator once before threads, no model or scorer call.
    records = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(request_one, task, method, gate) for task in tasks]
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            print(json.dumps(record), flush=True)
    assert verify_method() == method
    write_new(ROOT/'results/batch-finish.json', {'created_utc':now(), 'records':records,
        'attempts':len(records), 'no_outcome_driven_retries_or_tuning':True})
    paths = [ROOT/'results/batch-start.json', ROOT/'results/batch-finish.json', ROOT/'results/rule-extraction.json',
             *sorted(p for p in (ROOT/'results/extraction').rglob('*') if p.is_file())]
    write_new(ROOT/'model-response-freeze.json', {'created_utc':now(),'method_freeze_sha256':method,
        'preflight_sha256':gate,'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},
        'requests':12,'failed_and_rejected_outputs_retained':True,'frozen_before_downstream_comparison':True})
    return {'batch_records':len(records),'model_response_freeze_sha256':sha(ROOT/'model-response-freeze.json')}


def preserve():
    previous = read(ROOT/'audit/prior-files.json')['files_sha256']
    mismatches = [name for name, expected in previous.items() if not (BASE/name).is_file() or sha(BASE/name) != expected]
    result = {'passed':not mismatches,'previous_files_checked':len(previous),'mismatches':mismatches,
              'method_freeze_sha256':verify_method(),'no_existing_files_intentionally_modified':True}
    write_new(ROOT/'audit/final-preservation.json',result)
    if mismatches:
        raise ValueError('Prior file integrity mismatch')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['freeze','rules','request-all','verify','preserve'])
    args = parser.parse_args()
    functions = {'freeze':freeze,'rules':rules,'request-all':request_all,'verify':lambda:{'passed':True,'sha256':verify_method()},'preserve':preserve}
    print(json.dumps(functions[args.operation](),indent=2))
