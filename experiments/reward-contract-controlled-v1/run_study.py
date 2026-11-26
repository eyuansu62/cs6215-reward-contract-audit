"""Frozen controlled study orchestration; the existing analyzer is not modified."""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from common import ROOT, contract_for, legacy, read, semantic_class, sha, verify_method, verify_preflight, write_new

CONDITIONS = ('reference', 'rules', 'llm', 'fixed_E', 'fixed_V', 'fixed_null')
CLASSES = ('E', 'V', 'U', 'INVALID')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def independent_truth(answer, reference):
    """Evaluation predicate written here, without importing the old witness oracle."""
    require(answer is None or type(answer) is str, 'Native candidate domain violation')
    require(type(reference) is str and reference in ('True', 'False'), 'Reference domain violation')
    candidate = None if answer is None else answer.strip().lower()
    return {'valid_boolean_token': candidate in ('true', 'false'),
            'equals_reference': candidate is not None and candidate == reference.lower()}


def independent_decision(contract, answer, reference, reward):
    truth = independent_truth(answer, reference)
    require(type(reward) in (int, float) and math.isfinite(reward), 'Non-numeric native reward')
    if contract is None:
        return {'verdict': 'unknown', 'active_obligations': None, 'per_obligation': [],
                'violated_obligations': [], 'full_credit_event': None}
    active = contract['obligations']
    require(all(x in truth for x in active), 'Unknown independent predicate')
    full_credit = reward >= contract['full_credit_threshold']
    rows = [{'obligation_id': x, 'predicate_satisfied': truth[x],
             'full_credit_event': full_credit, 'violated': full_credit and not truth[x]} for x in active]
    violations = [x['obligation_id'] for x in rows if x['violated']]
    return {'verdict': 'full_credit_violation' if violations else 'no_violation_for_this_witness',
            'active_obligations': copy.deepcopy(active), 'per_obligation': rows,
            'violated_obligations': violations, 'full_credit_event': full_credit}


def study_inputs():
    tasks = read(ROOT / 'data/test-cards.json')['tasks']
    labels = read(ROOT / 'data/labels.json')['labels']
    programs = read(ROOT / 'data/programs.json')['programs']
    require(len(tasks) == len(labels) == 12, 'Exactly twelve cards are required')
    require(len({x['task_id'] for x in tasks}) == 12, 'Task IDs must be unique')
    require({x['task_id'] for x in tasks} == {x['task_id'] for x in labels}, 'Task/label mismatch')
    require(Counter(x['semantic_class'] for x in labels) == {'E': 4, 'V': 4, 'U': 4}, 'Class balance changed')
    require(len({x['family'] for x in labels}) == 4, 'Exactly four language families required')
    require(len({(x['family'], x['semantic_class']) for x in labels}) == 12, 'Family/class crossing changed')
    require(len(programs) == 3 and {x['program_id'] for x in programs} == {'equality', 'token_only', 'truthiness'},
            'Exactly three frozen programs required')
    matrix = read(ROOT / 'protocol/expected.json')['matrix']
    require(set(matrix) == {'E', 'V'} and all(set(v) == {p['program_id'] for p in programs} for v in matrix.values()),
            'Expected matrix must contain only the six meaningful combinations')
    require(all(v in ('alarm', 'no_alarm') for row in matrix.values() for v in row.values()), 'Invalid expected verdict')
    probes = read(ROOT / 'protocol/probes.json')['probes']
    require(len({p['probe_id'] for p in probes}) == len(probes), 'Probe IDs must be unique')
    for p in probes:
        independent_truth(p['answer'], p['reference'])
    return tasks, {x['task_id']: x for x in labels}, programs, matrix, probes


class NativeRuns:
    """Cache identical program/input calls, while retaining every cache use."""
    def __init__(self, folder, method_sha):
        self.folder, self.method_sha = Path(folder), method_sha
        self.executions, self.uses, self.cache = [], [], {}

    def run(self, program_id, answer, reference, purpose):
        independent_truth(answer, reference)
        key = json.dumps([program_id, answer, reference], ensure_ascii=False, separators=(',', ':'))
        cached = key in self.cache
        if not cached:
            execution_id = 'native-' + hashlib.sha256(key.encode()).hexdigest()[:20]
            request = {'program_id': program_id, 'answer': answer, 'reference': reference,
                       'method_freeze_sha256': self.method_sha}
            command = [sys.executable, '-I', '-B', str(ROOT / 'native_worker.py')]
            record = {'execution_id': execution_id, 'request': request, 'argv': command, 'timeout_seconds': 8}
            try:
                proc = subprocess.run(command, input=json.dumps(request), capture_output=True, text=True, timeout=8)
                record.update({'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr})
                write_new(self.folder / (execution_id + '.json'), record)
                require(proc.returncode == 0, 'Native subprocess failed: ' + execution_id)
                reward = json.loads(proc.stdout)
                require(type(reward) in (int, float) and math.isfinite(reward), 'Native stdout is not a numeric scalar')
            except subprocess.TimeoutExpired as error:
                record.update({'timed_out': True, 'stdout': str(error.stdout or ''), 'stderr': str(error.stderr or '')})
                write_new(self.folder / (execution_id + '.json'), record)
                raise ValueError('Native subprocess timed out: ' + execution_id) from error
            item = {**record, 'reward': reward, 'cache_key': key}
            self.executions.append(item)
            self.cache[key] = item
        item = self.cache[key]
        self.uses.append({'execution_id': item['execution_id'], 'cached': cached, 'purpose': purpose})
        return item['reward'], item['execution_id']

    def document(self):
        return {'executions': self.executions, 'uses': self.uses, 'execution_count': len(self.executions),
                'cache_hits': sum(x['cached'] for x in self.uses),
                'cache_scope': 'Identical frozen program_id, native answer, canonical reference within this run'}


def check_raw_contract(api, contract, result):
    if contract is not None:
        require(api.compile_contract(copy.deepcopy(contract)) == contract, 'Compiler changed a raw contract')
        require(result.get('compiled_contract') == contract, 'Analyzer changed a raw contract')
        require(result.get('active_obligations') == contract['obligations'], 'Analyzer changed obligation IDs or order')
        require([r['obligation_id'] for r in result.get('per_obligation', [])] == contract['obligations'],
                'Global result lost per-obligation IDs')
    else:
        require(result['verdict'] == 'unknown', 'Missing contract must remain Unknown')


def certify_global(result, contract, program, native, purpose, gold_class=None):
    """Audit saved certificates and independently execute every returned alarm witness."""
    observations = []
    if contract is None:
        require(result['verdict'] == 'unknown', 'Null contract must remain Unknown')
        return observations
    for row in result['per_obligation']:
        obligation = row['obligation_id']
        require(obligation in contract['obligations'], 'Inactive global obligation')
        certificate = row.get('certificate')
        if row['verdict'] == 'no_alarm':
            require(type(certificate) is dict and certificate.get('kind') == 'all_normal_full_credit_paths_certified',
                    'No-alarm result lacks the normal full-credit path certificate')
            paths = certificate.get('paths')
            require(type(paths) is list and certificate.get('full_credit_path_count') == len(paths) and len(paths) > 0,
                    'Certificate does not enumerate its normal full-credit paths')
            require(all(p.get('obligation_id') == obligation for p in paths), 'Certificate path obligation mismatch')
        elif row['verdict'] == 'alarm':
            require(type(certificate) is dict and certificate.get('kind') == 'native_boolean_obligation_path_counterexample',
                    'Alarm lacks a native counterexample')
            require(certificate.get('obligation_id') == obligation and certificate.get('violated_obligations') == [obligation],
                    'Counterexample obligation IDs changed')
            answer, reference = certificate['candidate'], certificate['trusted_reference']
            reward, execution_id = native.run(program['program_id'], answer, reference, purpose + ':' + obligation)
            truth = independent_truth(answer, reference)
            require(reward >= 1 and not truth[obligation], 'Returned alarm is not a real full-credit violation')
            require(certificate['reward'] == reward, 'Certificate reward disagrees with native execution')
            gold_id = {'E': 'equals_reference', 'V': 'valid_boolean_token'}.get(gold_class)
            observations.append({'obligation_id': obligation, 'answer': answer, 'reference': reference,
                                 'native_reward': reward, 'native_execution_id': execution_id,
                                 'predicate_truth': truth, 'active_predicate_violated': True,
                                 'gold_predicate_violated': None if gold_id is None else not truth[gold_id],
                                 'gold_class': gold_class})
        else:
            require(row['verdict'] == 'unknown', 'Unrecognized analyzer verdict')
    require(result['alarm_obligations'] == [r['obligation_id'] for r in result['per_obligation'] if r['verdict'] == 'alarm'],
            'Global alarm IDs disagree with per-obligation results')
    return observations


def check_concrete(api, program, contract, answer, reference, reward):
    static = api.check_witness(copy.deepcopy(program), copy.deepcopy(contract), answer, reference)
    independent = independent_decision(contract, answer, reference, reward)
    for field in ('verdict', 'active_obligations', 'per_obligation', 'violated_obligations'):
        require(static.get(field) == independent[field], 'Source/independent concrete disagreement: ' + field)
    if contract is not None:
        require(static['compiled_contract'] == contract, 'Witness compiler changed input contract')
        require(static['reward'] == reward, 'Modeled reward disagrees with native reward')
    return {'static': static, 'independent': independent}


def preflight():
    method_sha = verify_method()
    destination = ROOT / 'audit/preflight.json'
    require(not destination.exists(), 'Preserve the previous preflight result')
    output = {'passed': False, 'method_freeze_sha256': method_sha, 'standard_combinations': 6,
              'analyze_calls': 0, 'results': [], 'probe_checks': [], 'failure_reason': None}
    native = NativeRuns(ROOT / 'audit/preflight-native', method_sha)
    try:
        _, _, programs, matrix, probes = study_inputs()
        api = legacy()
        # Exactly these six analyze calls. No comparison, model call, or repair here.
        for label in ('E', 'V'):
            contract = contract_for(label)
            for program in programs:
                result = api.analyze(copy.deepcopy(program), copy.deepcopy(contract))
                output['analyze_calls'] += 1
                row = {'semantic_class': label, 'program_id': program['program_id'],
                       'expected': matrix[label][program['program_id']], 'result': result}
                output['results'].append(row)
                check_raw_contract(api, contract, result)
                require(result['verdict'] == row['expected'], 'Preflight matrix mismatch, including Unknown: ' + label + '/' + program['program_id'])
                row['native_counterexamples'] = certify_global(result, contract, program, native, 'preflight:' + label, label)
        for program in programs:
            for probe in probes:
                reward, execution_id = native.run(program['program_id'], probe['answer'], probe['reference'], 'preflight-probe:' + probe['probe_id'])
                decisions = {label: check_concrete(api, program, contract_for(label), probe['answer'], probe['reference'], reward)
                             for label in ('E', 'V')}
                output['probe_checks'].append({'program_id': program['program_id'], **probe, 'reward': reward,
                                              'native_execution_id': execution_id, 'conditions': decisions})
        require(output['analyze_calls'] == 6, 'Six-call preflight accounting failed')
        require(verify_method() == method_sha, 'Method changed during preflight')
        output['passed'] = True
    except Exception as error:
        output['failure_reason'] = type(error).__name__ + ': ' + str(error)
    output['native_observations'] = native.document()
    output['counts'] = {'global_verdicts': dict(Counter(x['result']['verdict'] for x in output['results'])),
                        'predefined_probe_checks': len(output['probe_checks']),
                        'native_executions': len(native.executions), 'cache_hits': sum(u['cached'] for u in native.uses)}
    write_new(destination, output)
    if not output['passed']:
        raise ValueError('Preflight stopped without auto-fix: ' + output['failure_reason'])
    return {'passed': True, 'standard_combinations': 6, 'counts': output['counts']}


def verify_model_seal(method_sha):
    path = ROOT / 'model-response-freeze.json'
    frozen = read(path)
    require(frozen['method_freeze_sha256'] == method_sha, 'Model responses belong to a different method')
    for name, digest in frozen['files_sha256'].items():
        target = ROOT / name
        require(target.resolve().is_relative_to(ROOT.resolve()), 'Seal path outside this study')
        require(sha(target) == digest, 'Sealed response changed: ' + name)
    actual = {str(p.relative_to(ROOT)) for p in (ROOT / 'results/extraction').rglob('*') if p.is_file()}
    sealed = {name for name in frozen['files_sha256'] if name.startswith('results/extraction/')}
    require(actual == sealed, 'Unsealed model extraction files or missing sealed files')
    return sha(path)


def validated_extraction(api, task, record, accepted=None):
    """Invalid transport/schema output is INVALID, never a successful U abstention."""
    if record.get('status') in ('failed', 'rejected'):
        return {'contract': None, 'class': 'INVALID', 'status': record['status'], 'error': record.get('error')}
    try:
        response = record['response']
        contract = api.validate_response(copy.deepcopy(response), copy.deepcopy(task))
        require(contract == response['contract'], 'Validator changed raw contract')
        if 'contract' in record:
            require(record['contract'] == contract, 'Frozen extraction contract disagrees with raw response')
        if accepted is not None:
            require(accepted['contract'] == contract, 'Accepted model contract disagrees with raw response')
        predicted = semantic_class(contract)
        expected_status = 'abstained' if contract is None else 'complete'
        if record.get('status') in ('complete', 'abstained'):
            require(record['status'] == expected_status, 'Metadata and accepted contract status disagree')
        return {'contract': contract, 'class': predicted, 'status': expected_status, 'error': None,
                'raw_contract_unchanged': True}
    except (KeyError, ValueError, AssertionError, TypeError) as error:
        return {'contract': None, 'class': 'INVALID', 'status': 'rejected', 'error': type(error).__name__ + ': ' + str(error)}


def load_model_extraction(api, task, folder=None):
    folder = Path(folder) if folder is not None else ROOT / 'results/extraction' / task['task_id']
    try:
        metadata = read(folder / 'metadata.json')
        require(type(metadata) is dict, 'Model metadata must be an object')
        require(metadata.get('status') in ('complete', 'abstained', 'failed', 'rejected'), 'Invalid model metadata status')
        if metadata['status'] in ('failed', 'rejected'):
            # Partial response files can be malformed. Their sealed bytes are evidence,
            # not accepted contracts, and must not abort the remaining evaluation.
            return validated_extraction(api, task, metadata)
        response = read(folder / 'response.json')
        accepted = read(folder / 'accepted-contract.json')
        require(type(accepted) is dict and 'contract' in accepted, 'Accepted model contract file missing or malformed')
        return validated_extraction(api, task, {**metadata, 'response': response}, accepted)
    except (OSError, ValueError, TypeError) as error:
        return {'contract': None, 'class': 'INVALID', 'status': 'rejected',
                'error': type(error).__name__ + ': ' + str(error)}


def extraction_conditions(api, task, gold, rules):
    identifier = task['task_id']
    def fixed(label):
        return {'contract': contract_for(label), 'class': label, 'status': 'assumed',
                'policy_kind': 'fixed assumption; not a description extractor', 'error': None}
    return {'reference': {'contract': contract_for(gold), 'class': gold, 'status': 'researcher_reference', 'error': None},
            'rules': validated_extraction(api, task, rules[identifier]),
            'llm': load_model_extraction(api, task),
            'fixed_E': fixed('E'), 'fixed_V': fixed('V'), 'fixed_null': fixed('U')}


def binary_outcome(gold, expected, verdict):
    if gold == 'U':
        return None
    require(gold in ('E', 'V'), 'Unknown gold class')
    if verdict == 'unknown':
        return 'Unknown'
    require(verdict in ('alarm', 'no_alarm'), 'Invalid global verdict')
    return {('alarm', 'alarm'): 'TP', ('alarm', 'no_alarm'): 'FN',
            ('no_alarm', 'alarm'): 'FP', ('no_alarm', 'no_alarm'): 'TN'}[expected, verdict]


def supported_correct(row):
    if row['gold_class'] == 'U':
        return row['contract_class'] == 'U' and row['result']['verdict'] == 'unknown'
    outcome = row['binary_outcome']
    return outcome == 'TN' or outcome == 'TP' and row['gold_witness_validated_alarm']


def aggregate(globals_, extractions):
    metrics = {}
    for condition in CONDITIONS:
        rows = [r for r in globals_ if r['condition'] == condition]
        semantic = [r for r in rows if r['gold_class'] != 'U']
        administrative = [r for r in rows if r['gold_class'] == 'U']
        count = Counter(r['binary_outcome'] for r in semantic)
        cards = [r for r in extractions if r['condition'] == condition]
        confusion = {g: {p: 0 for p in CLASSES} for g in ('E', 'V', 'U')}
        for card in cards:
            confusion[card['gold_class']][card['class']] += 1
        by_task = defaultdict(list)
        for row in rows:
            by_task[row['task_id']].append(row)
        metrics[condition] = {
            'semantic_cells': len(semantic), 'binary_confusion': {x: count[x] for x in ('TP', 'FP', 'FN', 'TN', 'Unknown')},
            'binary_correct_cells': count['TP'] + count['TN'],
            'binary_accuracy': (count['TP'] + count['TN']) / len(semantic) if semantic else None,
            'binary_coverage': (len(semantic) - count['Unknown']) / len(semantic) if semantic else None,
            'witness_validated_alarms': sum(r['gold_witness_validated_alarm'] for r in semantic),
            'unjustified_alarm_witnesses': sum(sum(w['gold_predicate_violated'] is False for w in r['native_counterexamples']) for r in semantic),
            'alarm_cells_without_gold_violating_returned_witness': sum(r['result']['verdict'] == 'alarm' and not r['gold_witness_validated_alarm'] for r in semantic),
            'witness_supported_correct_cells': sum(supported_correct(r) for r in semantic),
            'administrative_U': {'cells': len(administrative),
                'valid_abstentions': sum(r['contract_class'] == 'U' for r in administrative),
                'invalid_outputs': sum(r['contract_class'] == 'INVALID' for r in administrative),
                'unjustified_contracts': sum(r['contract_class'] in ('E', 'V') for r in administrative),
                'unjustified_alarms': sum(r['result']['verdict'] == 'alarm' for r in administrative),
                'included_in_binary_denominator': False},
            'contract_class_confusion': confusion,
            'contract_class_correct_cards': sum(r['gold_class'] == r['class'] for r in cards),
            'contract_class_denominator': len(cards),
            'correct_global_vectors_nonnull_cards': sum(all(r['binary_outcome'] in ('TP', 'TN') for r in group)
                for group in by_task.values() if group[0]['gold_class'] != 'U'),
            'correct_global_vectors_nonnull_denominator': sum(group[0]['gold_class'] != 'U' for group in by_task.values()),
            'witness_supported_correct_vectors_nonnull_cards': sum(all(supported_correct(r) for r in group)
                for group in by_task.values() if group[0]['gold_class'] != 'U'),
            'fully_correct_cards_with_U_administration': sum(all(supported_correct(r) for r in group) for group in by_task.values())}
    indexed = {(r['task_id'], r['program_id'], r['condition']): r for r in globals_}
    wins = []
    for key in sorted({(r['task_id'], r['program_id']) for r in globals_}):
        left, right = indexed[*key, 'llm'], indexed[*key, 'rules']
        llm, rules = supported_correct(left), supported_correct(right)
        delta = 'win' if llm and not rules else 'loss' if rules and not llm else 'tie'
        wins.append({'task_id': key[0], 'program_id': key[1], 'gold_class': left['gold_class'],
                     'evaluation': 'administrative_abstention' if left['gold_class'] == 'U' else 'witness_supported_global',
                     'llm_outcome': left['binary_outcome'], 'rules_outcome': right['binary_outcome'],
                     'llm_supported_correct': llm, 'rules_supported_correct': rules, 'llm_vs_rules': delta,
                     'llm_contract_class': left['contract_class'], 'rules_contract_class': right['contract_class'],
                     'llm_returned_witnesses': left['native_counterexamples'], 'rules_returned_witnesses': right['native_counterexamples']})
    per_card = []
    card_index = {(x['task_id'], x['condition']): x for x in extractions}
    for task_id in sorted({x['task_id'] for x in extractions}):
        a, b = card_index[task_id, 'llm'], card_index[task_id, 'rules']
        lc, rc = a['class'] == a['gold_class'], b['class'] == b['gold_class']
        cells = [r for r in wins if r['task_id'] == task_id]
        per_card.append({'task_id': task_id, 'gold_class': a['gold_class'], 'family': a['family'],
                         'llm_class': a['class'], 'rules_class': b['class'],
                         'extraction_class_llm_vs_rules': 'win' if lc and not rc else 'loss' if rc and not lc else 'tie',
                         'llm_all_three_supported_correct': all(x['llm_supported_correct'] for x in cells),
                         'rules_all_three_supported_correct': all(x['rules_supported_correct'] for x in cells),
                         'cell_win_loss': dict(Counter(x['llm_vs_rules'] for x in cells))})
    return {'conditions': metrics, 'llm_vs_rules_cells': wins, 'llm_vs_rules_cards': per_card,
            'llm_vs_rules_nonnull_counts': dict(Counter(x['llm_vs_rules'] for x in wins if x['gold_class'] != 'U')),
            'llm_vs_rules_U_administrative_counts': dict(Counter(x['llm_vs_rules'] for x in wins if x['gold_class'] == 'U'))}


def compare():
    preflight_sha = verify_preflight()
    method_sha = verify_method()
    seal_sha = verify_model_seal(method_sha)
    destination = ROOT / 'results/comparison'
    require(not destination.exists(), 'Preserve the previous comparison')
    tasks, labels, programs, matrix, probes = study_inputs()
    rules_document = read(ROOT / 'results/rule-extraction.json')
    rules = {x['task_id']: x for x in rules_document['records']}
    require(len(rules_document['records']) == 12 and set(rules) == set(labels), 'Rule card set mismatch')
    # Rule records must have been sealed with the responses or the frozen method.
    sealed = read(ROOT / 'model-response-freeze.json')['files_sha256']
    frozen = read(ROOT / 'method-freeze.json')['files_sha256']
    require(sealed.get('results/rule-extraction.json', frozen.get('results/rule-extraction.json')) == sha(ROOT / 'results/rule-extraction.json'),
            'Rule outputs were not sealed before comparison')
    api = legacy()
    native = NativeRuns(destination / 'native', method_sha)
    globals_, extractions, witnesses = [], [], []
    per_card_conditions = {}
    probe_inputs = {p['program_id']: {(x['answer'], x['reference']): {**x, 'origins': ['predefined']}
                                      for x in probes} for p in programs}
    for task in tasks:
        task_id = task['task_id']
        label = labels[task_id]
        conditions = extraction_conditions(api, task, label['semantic_class'], rules)
        per_card_conditions[task_id] = conditions
        for condition, selected in conditions.items():
            extractions.append({'task_id': task_id, 'gold_class': label['semantic_class'], 'family': label['family'],
                                'condition': condition, **selected})
            for program in programs:
                contract = selected['contract']
                result = api.analyze(copy.deepcopy(program), copy.deepcopy(contract))
                check_raw_contract(api, contract, result)
                counterexamples = certify_global(result, contract, program, native, task_id + ':' + condition, label['semantic_class'])
                expected = None if label['semantic_class'] == 'U' else matrix[label['semantic_class']][program['program_id']]
                row = {'task_id': task_id, 'program_id': program['program_id'], 'condition': condition,
                       'gold_class': label['semantic_class'], 'family': label['family'], 'contract_class': selected['class'],
                       'contract': contract, 'extraction_status': selected['status'], 'expected_global_verdict': expected,
                       'binary_outcome': binary_outcome(label['semantic_class'], expected, result['verdict']),
                       'result': result, 'native_counterexamples': counterexamples,
                       'gold_witness_validated_alarm': any(x['gold_predicate_violated'] is True for x in counterexamples)}
                globals_.append(row)
                for witness in counterexamples:
                    key = witness['answer'], witness['reference']
                    group = probe_inputs[program['program_id']]
                    if key not in group:
                        tag = hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]
                        group[key] = {'probe_id': 'source-generated-' + tag, 'answer': key[0], 'reference': key[1], 'origins': []}
                    group[key]['origins'].append({'task_id': task_id, 'condition': condition, 'obligation_id': witness['obligation_id']})
    # Actual observations are used only by this evaluator, never passed to analyze/check_witness.
    for task in tasks:
        task_id = task['task_id']
        gold = labels[task_id]['semantic_class']
        for program in programs:
            for probe in probe_inputs[program['program_id']].values():
                reward, execution_id = native.run(program['program_id'], probe['answer'], probe['reference'], task_id + ':probe:' + probe['probe_id'])
                decisions = {condition: check_concrete(api, program, selected['contract'], probe['answer'], probe['reference'], reward)
                             for condition, selected in per_card_conditions[task_id].items()}
                witnesses.append({'task_id': task_id, 'program_id': program['program_id'], 'gold_class': gold,
                                  **probe, 'native_reward': reward, 'native_execution_id': execution_id,
                                  'predicate_truth': independent_truth(probe['answer'], probe['reference']),
                                  'gold_semantic_violation': None if gold == 'U' else decisions['reference']['independent']['verdict'] == 'full_credit_violation',
                                  'conditions': decisions})
    require(len(globals_) == 216, 'Expected six conditions crossed with twelve cards and three programs')
    require(verify_method() == method_sha and verify_preflight() == preflight_sha and verify_model_seal(method_sha) == seal_sha,
            'Study gates changed during comparison')
    summary = {'passed': True, 'method_freeze_sha256': method_sha, 'preflight_sha256': preflight_sha,
               'model_response_freeze_sha256': seal_sha, 'analyzer_calls': len(globals_),
               'units': {'description_cards': 12, 'linguistic_families': 4, 'programs': 3,
                         'nonnull_semantic_program_combinations': 6, 'semantic_global_cells_per_condition': 24,
                         'administrative_U_cells_per_condition': 12, 'conditions': 6},
               'interpretation': 'Researcher-authored controlled descriptions; repeated program/semantic cells are dependent. U is administrative abstention, never a true negative. Fixed policies are assumptions, not extractors. Binary TP alone is not a semantic extraction success or witness-supported gain.',
               'frozen_analyzer_unchanged': True, 'raw_contracts_unchanged': True, 'observed_rewards_passed_to_analyzer': False,
               'new_model_calls': 0, 'semgrep_runs': 0, 'native_execution_count': len(native.executions),
               'witness_rows': len(witnesses), **aggregate(globals_, extractions)}
    write_new(destination / 'globals.json', {'records': globals_})
    write_new(destination / 'extractions.json', {'records': extractions})
    write_new(destination / 'witnesses.json', {'records': witnesses})
    write_new(destination / 'native-observations.json', native.document())
    write_new(destination / 'summary.json', summary)
    files = {str(p.relative_to(destination)): sha(p) for p in sorted(destination.rglob('*')) if p.is_file()}
    write_new(destination / 'artifact-files-sha256.json', {'files_sha256': files})
    return {'passed': True, 'analyzer_calls': len(globals_), 'native_executions': len(native.executions),
            'llm_vs_rules_nonnull_counts': summary['llm_vs_rules_nonnull_counts']}


def verify_saved():
    preflight_sha, method_sha = verify_preflight(), verify_method()
    seal_sha = verify_model_seal(method_sha)
    folder = ROOT / 'results/comparison'
    manifest = read(folder / 'artifact-files-sha256.json')['files_sha256']
    actual = {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*'))
              if p.is_file() and p.name != 'artifact-files-sha256.json'}
    require(actual == manifest, 'Saved comparison artifact manifest mismatch')
    summary = read(folder / 'summary.json')
    require(summary['method_freeze_sha256'] == method_sha and summary['preflight_sha256'] == preflight_sha
            and summary['model_response_freeze_sha256'] == seal_sha, 'Saved summary gate mismatch')
    globals_ = read(folder / 'globals.json')['records']
    extractions = read(folder / 'extractions.json')['records']
    regenerated = aggregate(globals_, extractions)
    require(all(summary[key] == value for key, value in regenerated.items()), 'Saved aggregation mismatch')
    observations = read(folder / 'native-observations.json')
    by_id = {x['execution_id']: x for x in observations['executions']}
    require(len(by_id) == len(observations['executions']) == summary['native_execution_count'], 'Native execution accounting mismatch')
    for item in by_id.values():
        require(json.loads(item['stdout']) == item['reward'] and item['returncode'] == 0, 'Native stdout/reward disagreement')
        raw = read(folder / 'native' / (item['execution_id'] + '.json'))
        require(all(item[key] == value for key, value in raw.items()), 'Native raw command record disagreement')
    for witness in read(folder / 'witnesses.json')['records']:
        item = by_id[witness['native_execution_id']]
        require(item['request']['program_id'] == witness['program_id'] and item['request']['answer'] == witness['answer']
                and item['request']['reference'] == witness['reference'] and item['reward'] == witness['native_reward'], 'Witness native request mismatch')
        require(witness['predicate_truth'] == independent_truth(witness['answer'], witness['reference']), 'Independent witness truth changed')
        contracts = {r['condition']: r['contract'] for r in extractions if r['task_id'] == witness['task_id']}
        for condition, decisions in witness['conditions'].items():
            require(decisions['independent'] == independent_decision(contracts[condition], witness['answer'], witness['reference'], witness['native_reward']),
                    'Saved independent witness decision mismatch')
    return {'passed': True, 'verified_artifacts': len(manifest), 'recomputed_aggregation': True,
            'new_model_calls': 0, 'new_analyzer_calls': 0, 'new_native_executions': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('preflight', 'compare', 'verify-saved'))
    args = parser.parse_args()
    action = {'preflight': preflight, 'compare': compare, 'verify-saved': verify_saved}[args.operation]
    print(json.dumps(action(), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
