#!/usr/bin/env python3
"""Verify the integrated artifact using saved bytes/JSON only (Python 3.11+).

The only subprocesses are the two fixed saved-verification commands below.
No target, model, analyzer, scanner, test or experimental rerun is invoked.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTROLLED = 'experiments/reward-contract-controlled-v1'
HISTORY = 'history/final-reward-2026-11-09'
SAVED_COMMANDS = (
    ('reproducibility/verify_saved.py',),
    (CONTROLLED + '/run_study.py', 'verify-saved'),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(name, exact_directory=None):
    files = read(name)['files_sha256']
    for relative, expected in files.items():
        path = ROOT / relative
        require(path.resolve().is_relative_to(ROOT), 'Manifest path outside repository')
        require(path.is_file() and sha(path) == expected, 'Saved byte mismatch: ' + relative)
    if exact_directory:
        actual = {str(p.relative_to(ROOT)) for p in (ROOT / exact_directory).rglob('*') if p.is_file()}
        require(actual == set(files), 'Saved directory inventory changed: ' + exact_directory)
    return len(files)


def request_record(folder, stage):
    metadata = read(folder + '/metadata.json')
    events = [json.loads(line) for line in (ROOT / folder / 'events.jsonl').read_text().splitlines() if line.strip()]
    completed = [event for event in events if event.get('type') == 'turn.completed']
    require(len(completed) == 1, 'Expected one completed turn: ' + folder)
    require(metadata['usage'] == completed[0]['usage'], 'Usage/event disagreement: ' + folder)
    require(metadata['accepted_tool_actions'] == 0, 'Model tool actions were accepted: ' + folder)
    require(metadata['model_reported'] is None, 'Revisit unknown-model disclosure: ' + folder)
    for event in events:
        item = event.get('item')
        require(not isinstance(item, dict) or item.get('type') in ('agent_message', 'reasoning'),
                'Unexpected model action item: ' + folder)
    if stage == 'G':
        require(metadata['completed_turns_observed'] == metadata['successful_model_turns'] == 1,
                'Controlled turn accounting changed')
        require(metadata['observed_completed_usage'] == metadata['usage'], 'Controlled observed usage changed')
        require(metadata['no_retries'] and metadata['no_obligations_repaired'], 'Controlled protocol changed')
        require(metadata['response_sha256'] == sha(ROOT / folder / 'response.json'), 'Response hash changed')
    return {'stage': stage, 'metadata': folder + '/metadata.json', 'completed_model_turns': 1,
            'response_status': metadata['status'], 'usage': metadata['usage'],
            'wall_seconds': metadata['wall_seconds'], 'model_reported': metadata['model_reported'],
            'cli_version': metadata['cli_version']}


def subtotal(records):
    return {'completed_experimental_model_turns': len(records),
            **{name: sum(r['usage'].get(name, 0) for r in records) for name in
               ('input_tokens', 'output_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
                'reasoning_output_tokens')},
            'sum_request_wall_seconds': round(sum(r['wall_seconds'] for r in records), 4)}


def resources(legacy):
    old_folders = [f'experiments/reward-contract-extraction-v1/results/extraction-02/T{i:02d}' for i in range(1, 7)]
    old_folders += ['experiments/reward-contract-e2e-v1/results/extraction-01',
                    'experiments/reward-external-boolean-v1/results/extraction-01']
    old = [request_record(folder, 'A-F') for folder in old_folders]
    ids = sorted(t['task_id'] for t in read(CONTROLLED + '/data/test-cards.json')['tasks'])
    new = [request_record(CONTROLLED + '/results/extraction/' + task, 'G') for task in ids]
    old_totals, new_totals = subtotal(old), subtotal(new)
    for key, value in old_totals.items():
        if key != 'cache_write_input_tokens':
            require(legacy['resources'][key] == value, 'Legacy resource subtotal changed: ' + key)
    ledger = read(CONTROLLED + '/analysis/resource-ledger.json')
    require(ledger['completed_turns'] == len(new) == 12, 'Controlled completed turn count changed')
    require(ledger['tokens'] == {key: new_totals[key] for key in ledger['tokens']}, 'Controlled token ledger mismatch')
    require(ledger['summed_request_seconds'] == new_totals['sum_request_wall_seconds'], 'Controlled latency ledger mismatch')
    start, finish = (read(CONTROLLED + '/results/batch-' + name + '.json') for name in ('start', 'finish'))
    elapsed = round((datetime.fromisoformat(finish['created_utc']) - datetime.fromisoformat(start['created_utc'])).total_seconds(), 4)
    require(elapsed == ledger['parallel_batch_elapsed_seconds'], 'Controlled batch elapsed time mismatch')
    require(start['planned_requests'] == finish['attempts'] == 12 and start['retries'] == 0, 'Controlled batch accounting mismatch')
    initial = ROOT / 'experiments/reward-contract-extraction-v1/results/extraction-01/T01/events.jsonl'
    require('turn.completed' not in initial.read_text(), 'Initialization failure has a completed turn')
    all_records = old + new
    return {**subtotal(all_records), 'subtotals': {'A-F': old_totals, 'G': new_totals},
            'controlled_parallel_batch_elapsed_seconds': elapsed,
            'controlled_batch_parallelism': start['parallelism'],
            'pre_model_initialization_failures_not_counted': 1,
            'exact_model_identity_known': False, 'requests_with_unknown_model_identity': len(all_records),
            'temperature_and_seed': 'not controlled/reported',
            'cached_input_is_subset_of_input': True,
            'reasoning_output_tokens_recorded_separately_not_added_to_output': True,
            'scope': 'Experimental completed-request subtotal only, including one evidence-rejected pilot response. Excludes earlier v10 and ideation, source research, coding, review and writing AI use. Service context is included in input usage. Request seconds are summed latency, not human effort, billing, or project elapsed time.',
            'requests': all_records}


def controlled_results():
    summary = read(CONTROLLED + '/results/comparison/summary.json')
    labels = read(CONTROLLED + '/data/labels.json')['labels']
    programs = read(CONTROLLED + '/data/programs.json')['programs']
    globals_ = read(CONTROLLED + '/results/comparison/globals.json')['records']
    wins = [row for row in summary['llm_vs_rules_cells'] if row['gold_class'] != 'U' and row['llm_vs_rules'] == 'win']
    require(all(row['rules_outcome'] == 'Unknown' for row in wins), 'A controlled win corrected a determinate rule result')
    gain_outcomes = Counter(row['llm_outcome'] for row in wins)
    fixed_e_lucky = sum(row['condition'] == 'fixed_E' and row['gold_class'] != 'U'
                        and row['binary_outcome'] == 'TP' and not row['gold_witness_validated_alarm'] for row in globals_)
    require(len(wins) == 21 and gain_outcomes == {'TP': 10, 'TN': 11}, 'Controlled gain interpretation changed')
    require(fixed_e_lucky == 4, 'Fixed E unsupported true-positive count changed')
    freeze = read(CONTROLLED + '/method-freeze.json')
    preflight = read(CONTROLLED + '/audit/preflight.json')
    require(freeze['frozen_before_six_standard_combinations'] and freeze['frozen_before_rule_test_predictions_and_model_requests'],
            'Controlled freeze sequence changed')
    require(not freeze['new_analyzer_semantics'] and preflight['passed'] and preflight['standard_combinations'] == 6,
            'Controlled analyzer or preflight changed')
    return {'source': CONTROLLED + '/results/comparison/summary.json',
            'unit': 'Researcher-authored synthetic policy-control description; repeated source/policy cells are dependent',
            'description_cards': len(labels), 'linguistic_families': len({row['family'] for row in labels}),
            'class_balance': dict(sorted(Counter(row['semantic_class'] for row in labels).items())),
            'known_source_definitions': len(programs), 'unique_nonnull_policy_source_combinations': 6,
            'semantic_cells_per_condition': 24, 'administrative_U_cells_per_condition': 12,
            'U_is_binary_true_negative': False, 'conditions': summary['conditions'],
            'llm_vs_rules_nonnull_counts': summary['llm_vs_rules_nonnull_counts'],
            'llm_vs_rules_U_administrative_counts': summary['llm_vs_rules_U_administrative_counts'],
            'wins_resolving_rule_abstention': len(wins), 'wins_correcting_wrong_determinate_rule_verdict': 0,
            'resolved_abstentions': {'gold_witness_supported_alarms': gain_outcomes['TP'], 'no_alarm_certificates': gain_outcomes['TN']},
            'fixed_E_binary_TP_without_gold_violating_returned_witness': fixed_e_lucky,
            'method_prompt_rules_labels_frozen_before_preflight_and_requests': True,
            'passed_preflight_combinations': preflight['standard_combinations'], 'analyzer_unchanged': summary['frozen_analyzer_unchanged'],
            'experimental_model_turns': 12, 'historical_comparison_analyzer_calls': summary['analyzer_calls'],
            'historical_comparison_native_executions': summary['native_execution_count'],
            'historical_comparison_witness_rows': summary['witness_rows'],
            'new_real_bug_or_generalization_claim': False, 'human_effort_measured': False,
            'qualification': 'This positive controlled contrast concerns contract selection and abstention resolution against one frozen rule extractor. It does not overturn the negative/inconclusive real-code stages, establish performance against all rule systems, prove soundness or natural-language entailment, or show human-time savings or RL training improvement.'}


def collect_index():
    legacy = read('reproducibility/results-index.json')
    result = {key: value for key, value in legacy.items() if key not in ('schema', 'resources', 'scope')}
    return {'schema': 'reward-contract-final-saved-result-index-v2',
            'legacy_result_index_preserved': 'reproducibility/results-index.json', **result,
            'G_controlled_contract_selection': controlled_results(), 'resources': resources(legacy),
            'scope': 'A-F retain their original evidence and limitations. G is an already-completed controlled description study on known source semantics. Never pool independent cases, correlated variants, probes, cards, cells, fields, replays or tests. No new experiments were performed during final integration.'}


def run_saved_verifiers():
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    results = []
    for arguments in SAVED_COMMANDS:
        command = [sys.executable, '-B', str(ROOT / arguments[0]), *arguments[1:]]
        process = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, check=True)
        record = json.loads(process.stdout)
        require(record.get('passed') is True, 'Saved verifier did not pass: ' + arguments[0])
        results.append({'script': arguments[0], 'arguments': list(arguments[1:]), 'result': record})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional new JSON log under local-runs/; default prints JSON only')
    args = parser.parse_args()
    controlled_count = verify_manifest('reproducibility/controlled-payload-manifest.json', CONTROLLED)
    historical_count = verify_manifest('reproducibility/history-manifest.json', HISTORY)
    for name in ('verify_saved.py', 'results-index.json'):
        require(sha(ROOT / 'reproducibility' / name) == sha(ROOT / HISTORY / 'reproducibility' / name),
                'Original saved verifier/index changed: ' + name)
    verifiers = run_saved_verifiers()
    calculated = collect_index()
    require(calculated == read('reproducibility/results-index-v2.json'), 'Combined index differs from saved evidence')
    result = {'passed': True, 'verification': 'saved bytes, JSON aggregation and completed-turn metadata only',
              'original_frozen_files_verified': verifiers[0]['result']['frozen_archive_files_verified'],
              'controlled_payload_files_verified': controlled_count, 'historical_files_verified': historical_count,
              'saved_verifiers': verifiers, 'combined_results_index_recomputed': True,
              'experimental_model_turns_in_existing_records': calculated['resources']['completed_experimental_model_turns'],
              'resource_totals': {key: value for key, value in calculated['resources'].items()
                                  if key.endswith('tokens') or key in ('sum_request_wall_seconds', 'controlled_parallel_batch_elapsed_seconds')},
              'new_model_requests': 0, 'new_target_executions': 0, 'new_analyzer_runs': 0, 'new_scanner_runs': 0,
              'old_tests_rerun': False, 'report_layout_not_checked_by_this_program': True}
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        target = args.output.resolve()
        require(target.is_relative_to(ROOT / 'local-runs'), 'Write optional logs only under local-runs/')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as output:
            output.write(text)
    print(text, end='')


if __name__ == '__main__':
    main()
