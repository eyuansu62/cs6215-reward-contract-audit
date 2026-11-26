#!/usr/bin/env python3
"""Read-only checks of frozen bytes and published saved-result counts.

This program imports only the Python standard library. It never imports a study
module, starts a subprocess, executes a target scorer, invokes Semgrep, requests
an LLM response, or reruns a test/experiment. Unknowns remain explicit.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def confusion(cases, method):
    counts = dict.fromkeys(('tp', 'fp', 'fn', 'tn', 'unknown_positive', 'unknown_negative'), 0)
    for row in cases:
        value = row['methods'][method]['verdict']; gold = row['expected_violation']
        check(value in ('alarm', 'no_alarm', 'unknown') and type(gold) is bool, 'Invalid saved verdict/label')
        key = ('unknown_positive' if gold else 'unknown_negative') if value == 'unknown' else (
            ('tp' if gold else 'fp') if value == 'alarm' else ('fn' if gold else 'tn'))
        counts[key] += 1
    return {**counts, 'correct': counts['tp'] + counts['tn'], 'total': len(cases)}


def task_budget():
    folders = [f'experiments/reward-contract-extraction-v1/results/extraction-02/T{i:02d}' for i in range(1, 7)]
    folders += ['experiments/reward-contract-e2e-v1/results/extraction-01',
                'experiments/reward-external-boolean-v1/results/extraction-01']
    ledger = []
    for folder in folders:
        metadata = read(folder + '/metadata.json')
        events = [json.loads(line) for line in (ROOT / folder / 'events.jsonl').read_text().splitlines() if line.strip()]
        completed = [event for event in events if event.get('type') == 'turn.completed']
        check(len(completed) == 1, 'Not exactly one completed model turn: ' + folder)
        check(metadata['usage'] == completed[0]['usage'], 'Usage/event disagreement: ' + folder)
        check(metadata['accepted_tool_actions'] == 0, 'Unexpected model tool action: ' + folder)
        for event in events:
            item = event.get('item')
            check(not isinstance(item, dict) or item.get('type') in ('agent_message', 'reasoning'), 'Unexpected model action item')
        check(metadata['model_reported'] is None, 'Revisit model-identity disclosure')
        ledger.append({'metadata': folder + '/metadata.json', 'completed_model_turns': 1,
            'response_status': metadata['status'], 'usage': metadata['usage'],
            'wall_seconds': metadata['wall_seconds'], 'model_reported': metadata['model_reported'],
            'cli_version': metadata['cli_version']})
    initial = 'experiments/reward-contract-extraction-v1/results/extraction-01/T01'
    failed_events = (ROOT / initial / 'events.jsonl').read_text()
    check('turn.completed' not in failed_events, 'Initialization failure incorrectly counted as model response')
    return {'completed_experimental_model_turns': len(ledger),
        'input_tokens': sum(x['usage']['input_tokens'] for x in ledger),
        'cached_input_tokens': sum(x['usage'].get('cached_input_tokens', 0) for x in ledger),
        'output_tokens': sum(x['usage']['output_tokens'] for x in ledger),
        'reasoning_output_tokens': sum(x['usage'].get('reasoning_output_tokens', 0) for x in ledger),
        'sum_request_wall_seconds': round(sum(x['wall_seconds'] for x in ledger), 4),
        'pre_model_initialization_failures_not_counted': 1,
        'exact_model_identity_known': False,
        'scope': 'Experimental-request subtotal only. Includes one completed but evidence-rejected pilot response. Excludes earlier v10, ideation, source research, coding, review and report-writing AI usage; not an account-billing total.',
        'requests': ledger}


def collect_results():
    prefix = 'experiments/'
    a = read(prefix + 'reward-baselines-v1/results/primary-01/scores.json')
    ad = read(prefix + 'reward-baselines-v1/results/diagnostic-01/scores.json')
    a_counts = {m: confusion(a['cases'], m) for m in ('semgrep', 'symbolic')}
    ad_counts = {m: confusion(ad['cases'], m) for m in ('semgrep', 'symbolic')}
    for source, counts in ((a, a_counts), (ad, ad_counts)):
        for method, values in counts.items():
            check(all(source['overall'][method][key] == value for key, value in values.items()), 'Saved confusion summary mismatch')
    b = read(prefix + 'reward-contract-extraction-v1/comparison/summary.json')
    rb = read(prefix + 'reward-contract-extraction-v1/comparison/root-field-review.json')
    ib = read(prefix + 'reward-contract-extraction-v1/comparison/independent-field-review.json')
    root_decisions = {(c['task_id'], f['field_group']): (f['action'], f['required_substantive_revision']) for c in rb['cases'] for f in c['fields']}
    independent = {(c['task_id'], f['field_group']): (f['decision'], f['required_substantive_revision']) for c in ib['tasks'] for f in c['semantic_fields']}
    check(root_decisions == independent and len(root_decisions) == 60, 'Saved field reviews disagree')
    decisions = Counter(x[0] for x in root_decisions.values())
    check(decisions == {'keep': 59, 'uncertain': 1}, 'Unexpected pilot field-review counts')
    bmodel = read(prefix + 'reward-contract-extraction-v1/results/model-response-freeze.json')
    bdown = read(prefix + 'reward-contract-extraction-v1/results/downstream-comparison.json')
    bunits = read(prefix + 'reward-contract-extraction-v1/collection/source-units.json')['units']
    check(len({unit['score_source'] for unit in bunits}) == 3, 'Pilot scorer duplication changed')
    b_reference = read(prefix + 'reward-contract-extraction-v1/results/downstream-reference-01/predictions.json')
    b_llm = read(prefix + 'reward-contract-extraction-v1/results/downstream-llm-01/predictions.json')
    check([x['task_id'] for x in b_reference['cases']] == [x['task_id'] for x in b_llm['cases']], 'Pilot task alignment changed')
    changes = sum(left['methods'][m]['verdict'] != right['methods'][m]['verdict']
                  for left, right in zip(b_reference['cases'], b_llm['cases']) for m in ('semgrep', 'symbolic'))
    check(changes == bdown['changed_verdicts'] == 0, 'Pilot verdict difference changed')
    supported = [row for row in b_reference['cases'] if row['projection']['supported']]
    check(len(supported) == 3 and len({row['detector_input_sha256'] for row in supported}) == 1, 'Pilot supported-input collapse changed')
    c0 = read(prefix + 'reward-contract-loop-v1/results/run-01/summary.json')
    c = read(prefix + 'reward-contract-loop-v2/results/run-01/summary.json')
    check(not c0['faithful_three_contract_closed_loop_supported'], 'Broken projection history changed')
    check(all(x['projected_contracts_identical'] and x['actual_detector_inputs_identical'] for x in c0['projection_proof']), 'Broken projection evidence changed')
    check(len(c['witness_rows']) == 18 and len(c['interface_fidelity']) == 2, 'Explicit-IR case unit count changed')
    for x in c['interface_fidelity']:
        check(x['compiled_contracts_differ_only_in_obligations'] and x['actual_consumer_inputs_differ'] and x['omitted_equality_not_reintroduced'], 'Explicit IR omission was not preserved')
    nonmissing = [x for x in c['witness_rows'] if x['contract'] != 'missing']
    missing = [x for x in c['witness_rows'] if x['contract'] == 'missing']
    for row in c['witness_rows']:
        result = row['static_witness_check']; oracle = row['concrete_oracle']; expected = row['expected']
        for field in ('active_obligations', 'per_obligation', 'violated_obligations'):
            check(result[field] == oracle[field] == expected[field], 'Explicit IR witness attribution changed')
        check(result['verdict'] == expected['expected_witness_verdict'], 'Explicit IR verdict changed')
        if row['contract'] != 'missing': check(result['reward'] == row['executed_reward'], 'Saved static/native reward mismatch')
    d = read(prefix + 'reward-contract-e2e-v1/results/run-01/summary.json')
    check(d['raw_model_contract_preserved'] and len(d['witness_rows']) == 6, 'Known-case integration changed')
    same_verdict = sum(x['conditions']['reference']['static']['verdict'] == x['conditions']['llm']['static']['verdict'] for x in d['witness_rows'])
    same_ids = sum(set(x['conditions']['reference']['static']['violated_obligations']) == set(x['conditions']['llm']['static']['violated_obligations']) for x in d['witness_rows'])
    check(same_verdict == d['same_witness_verdicts'] == 6 and same_ids == d['same_violated_obligation_id_sets'] == 6, 'Known-case paired comparison changed')
    e = read(prefix + 'reward-boolean-holdout-v1/results/status.json')
    check(e['selected_fresh_compatible_nondeduplicated_functions'] == 0 and all(x is None for x in e['comparison_metrics'].values()), 'Eligibility audit was relabelled as an experiment')
    f = read(prefix + 'reward-external-boolean-v1/results/run-01/summary.json')
    for row in f['global_results']:
        check(row['verdict'] == 'unknown', 'Revisit external global-result summary')
    check(len(f['global_results']) == 6 and len(f['semgrep_results']) == 3, 'External unit count changed')
    f_counts = {name: dict(Counter(row['verdict'] for row in f['global_results'] if row['condition'] == name)) for name in ('reference', 'llm')}
    observations = read(prefix + 'reward-external-boolean-v1/results/run-01/observations.json')['observations']
    check(len(observations) == 42 and all(x['observed']['kind'] == 'returned' and type(x['observed']['reward']) in (int, float) for x in observations), 'Native saved-return evidence changed')
    per_metric = {}
    for uid in ('H01', 'H02', 'H03'):
        records = [x for x in observations if x['unit_id'] == uid]
        witness_rows = [x for x in f['witness_rows'] if x['unit_id'] == uid]
        incompatible = []
        for row in witness_rows:
            check(row['conditions']['reference']['native_reward_oracle']['verdict'] == 'unknown', 'Null reference was silently filled')
            check(row['native_oracle_comparable'] is False and row['same_native_oracle_violated_ids'] is None, 'Unknown was counted as agreement')
            oracle = row['conditions']['llm']['native_reward_oracle']
            active = oracle['active_obligations']
            check(active == ['valid_boolean_token', 'equals_reference'], 'Model atom selection changed')
            violated = [x['obligation_id'] for x in oracle['per_obligation'] if x['violated']]
            check(violated == oracle['violated_obligations'], 'Saved per-obligation list mismatch')
            check(all(x['full_credit_event'] == (row['native_reward'] >= 1) for x in oracle['per_obligation']), 'Full-credit flag mismatch')
            if oracle['verdict'] == 'full_credit_violation': incompatible.append(row['probe_id'])
        per_metric[uid] = {'native_return_rows': len(records), 'full_rewards': sum(x['observed']['reward'] >= 1 for x in records),
                           'conditional_policy_incompatibilities': len(incompatible), 'probe_ids': incompatible}
    check([per_metric[k]['conditional_policy_incompatibilities'] for k in ('H01', 'H02', 'H03')] == [0, 4, 4], 'External conditional counts changed')
    check(f['summary']['paired_native_oracle_eligible'] == 0 and f['summary']['paired_native_oracle_violated_id_matches'] is None and f['bug_precision_recall'] is None, 'Undefined quality metrics changed')
    return {
        'schema': 'reward-contract-final-saved-result-index-v1',
        'A_known_RG_contracts': {'source': prefix + 'reward-baselines-v1/results/primary-01/scores.json',
            'unit': 'source-exposed function-version/contract case', 'cases': len(a['cases']), 'families': len({x['function_family'] for x in a['cases']}),
            'positive_labels': sum(x['expected_violation'] for x in a['cases']), 'negative_labels': sum(not x['expected_violation'] for x in a['cases']),
            'methods': a_counts, 'neural_method_tested_in_this_stage': False},
        'A_authored_diagnostics': {'source': prefix + 'reward-baselines-v1/results/diagnostic-01/scores.json', 'cases': len(ad['cases']), 'methods': ad_counts,
            'unit': 'authored synthetic diagnostic; separate from real cases and no neural gain claim'},
        'B_description_pilot': {'source': prefix + 'reward-contract-extraction-v1/comparison/summary.json', 'tasks': b['tasks'],
            'schema_valid_responses': sum(x['schema_valid'] is True for x in bmodel['tasks']), 'strictly_accepted_responses': sum(x['strict_validation_status'] == 'complete' for x in bmodel['tasks']),
            'field_groups': len(root_decisions), 'keep': decisions['keep'], 'confirmed_substantive_edits': sum(x[1] is True for x in root_decisions.values()),
            'uncertain': decisions['uncertain'], 'protocol_evidence_rejected_task': 'T05', 'supported_projections': len(supported),
            'distinct_supported_detector_inputs': 1, 'distinct_scorer_bodies': 3, 'inherited_scorer_tasks': b['downstream']['inherited_previously_exposed_scorer_tasks'],
            'changed_downstream_method_verdicts': changes, 'human_effort_measured': False, 'reference_authorship': 'AI-assisted researcher reference'},
        'C_development_interface': {'sources': [prefix + 'reward-contract-loop-v1/results/run-01/summary.json', prefix + 'reward-contract-loop-v2/results/run-01/summary.json'],
            'bug_families': 1, 'versions': 2, 'probes': 3, 'conditions': 3, 'witness_contract_rows': len(c['witness_rows']),
            'nonmissing_static_reward_rows': len(nonmissing), 'missing_contract_Unknown_rows': len(missing),
            'old_projection_reintroduced_equality': True, 'explicit_v2_preserves_omission': True, 'experimental_model_turns': 0},
        'D_known_case_LLM_integration': {'source': prefix + 'reward-contract-e2e-v1/results/run-01/summary.json', 'task_templates': 1,
            'experimental_model_turns': 1, 'selected_atoms': d['model_contract']['obligations'], 'paired_witness_version_inputs': len(d['witness_rows']),
            'condition_rows': d['condition_witness_rows'], 'same_verdict_pairs': same_verdict, 'same_violated_ID_pairs': same_ids,
            'raw_contract_preserved': True, 'held_out_bug_evaluation': False},
        'E_RG_eligibility_audit': {'source': prefix + 'reward-boolean-holdout-v1/results/status.json', 'candidate_modules': e['screened_concept_candidates'],
            'parsed_source_files': e['same_snapshot_census']['included_python_source_files'], 'Dataset_suffix_classes_including_base_composite': e['same_snapshot_census']['top_level_classes_with_Dataset_name_suffix'],
            'own_score_definitions': e['same_snapshot_census']['of_these_owning_score_answer'], 'selected_cases': 0,
            'experiment_started': False, 'performance_metrics': None},
        'F_HELM_policy_transfer': {'source': prefix + 'reward-external-boolean-v1/results/run-01/summary.json', 'project_count': 1, 'task_templates': 1,
            'related_metric_implementations': 3, 'experimental_model_turns': 1, 'reference_contract': None,
            'model_atoms': ['valid_boolean_token', 'equals_reference'], 'native_return_rows': len(observations),
            'condition_witness_rows': len(f['witness_rows']) * 2, 'source_global_counts': f_counts,
            'Semgrep_counts': dict(Counter(x['verdict'] for x in f['semgrep_results'])), 'per_metric_native_counts': per_metric,
            'conditional_policy_incompatibilities': sum(x['conditional_policy_incompatibilities'] for x in per_metric.values()),
            'eligible_reference_model_pairs': 0, 'quality_metrics': None,
            'qualification': 'Native interface probes, not actual CivilComments examples. Intentional normalization/prefix leniency is not an adjudicated upstream bug. Reference abstention is not a negative contract label.'},
        'resources': task_budget(),
        'scope': 'Do not sum stages, probes, paired variants, replays, field groups or test counts as independent tasks. Legacy v10 leakage results are not reward-contract accuracy.'}


def verify_payload():
    manifest = read('reproducibility/frozen-payload-manifest.json')
    for name, expected in manifest['files_sha256'].items():
        path = ROOT / name
        check(path.is_file() and digest(path) == expected, 'Frozen byte mismatch: ' + name)
    return len(manifest['files_sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional verification JSON output outside frozen study directories; default is stdout only')
    args = parser.parse_args()
    count = verify_payload()
    calculated = collect_results()
    check(calculated == read('reproducibility/results-index.json'), 'Result index differs from saved evidence')
    result = {'passed': True, 'verification': 'saved files and JSON only', 'frozen_archive_files_verified': count,
              'source_hashes_intact': True, 'published_saved_counts_recomputed': True,
              'experimental_model_turns_in_existing_records': calculated['resources']['completed_experimental_model_turns'],
              'new_model_requests': 0, 'new_target_executions': 0, 'new_Semgrep_scans': 0,
              'new_symbolic_runs': 0, 'old_tests_rerun': False,
              'main_report_not_checked_by_this_program': True}
    if args.output:
        target = args.output.resolve()
        for name in ('experiments', 'datasets'):
            check(not target.is_relative_to(ROOT / name), 'Do not write verification logs inside frozen data')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
