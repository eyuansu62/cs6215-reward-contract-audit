"""Offline verification of curation bytes/counts; never execute task code."""
from pathlib import Path
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    collection = ROOT/'collection'
    for name, digest in read(collection/'collection-freeze.json')['files_sha256'].items():
        assert sha(collection/name) == digest, name
    manifest = read(collection/'census/source-manifest.json')
    tree = read(BASE/'experiments/reward-contract-extraction-v1/collection/tree.json')
    assert hashlib.sha256((BASE/'experiments/reward-contract-extraction-v1/collection/tree.json').read_bytes()).hexdigest() == manifest['tree_sha256']
    blob_ids = {r['path']: r['sha'] for r in tree['tree'] if r['type'] == 'blob'}
    keys = []; own = 0
    for record in manifest['sources']:
        source = collection/'census/raw-source'/record['path']; data = source.read_bytes()
        assert sha(source) == record['sha256']
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        assert blob == record['git_blob_sha1'] == blob_ids[record['path']]
        for node in ast.parse(data.decode('utf-8')).body:
            if isinstance(node, ast.ClassDef) and node.name.endswith('Dataset'):
                keys.append((record['path'], node.name))
                own += any(isinstance(f, ast.FunctionDef) and f.name == 'score_answer' for f in node.body)
    metadata = read(collection/'census/first-pass-metadata.json')
    assert len(manifest['sources']) == manifest['extracted_python_blobs'] == 122
    assert len(keys) == metadata['task_dataset_classes'] == 108
    assert own == metadata['own_score_classes'] == 75
    assert set(keys) == {(r['path'], r['class']) for r in metadata['records']}
    assert len(read(collection/'census/answer-field-traces.json')['records']) == 108
    assert read(collection/'collection-status.json')['new_eligible_distinct_own_scorers_selected'] == 0
    status = read(ROOT/'results/status.json')
    assert all(value is None for value in status['comparison_metrics'].values())
    for key in ['evaluated_LLM_extraction_requests', 'Semgrep_scans', 'symbolic_analyzer_runs', 'target_scorer_executions']:
        assert status[key] == 0
    previous = BASE/'experiments/reward-contract-e2e-v1'
    old_manifest = read(previous/'artifact-files-sha256.json')['files_sha256']
    for name, digest in old_manifest.items(): assert sha(BASE/name) == digest, name
    for name, digest in read(ROOT/'planned-comparison.json')['frozen_components'].items():
        assert sha(BASE/name) == digest, name
    return {'passed': True, 'collection_freeze_sha256': sha(collection/'collection-freeze.json'),
            'source_blobs_checked': 122, 'Dataset_suffix_classes_checked': 108,
            'own_scorer_definitions_checked': 75, 'old_payloads_preserved': len(old_manifest),
            'qualified_new_implementations': 0, 'independent_test_executed': False,
            'all_comparison_metrics_undefined': True, 'model_analyzer_or_target_executions_by_verification': 0,
            'qualification': 'AST and hash integrity only; this is not a runtime answer-domain proof or analyzer experiment.'}


if __name__ == '__main__': print(json.dumps(verify(), indent=2))
