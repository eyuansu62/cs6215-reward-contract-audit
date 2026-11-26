"""I/O and hash gates for a new study; no analyzer semantics live here."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def verify_dependencies():
    records = read(ROOT/'protocol/dependencies.json')['files_sha256']
    for name, expected in records.items():
        if sha(BASE/name) != expected:
            raise ValueError('Preserved dependency changed: '+name)
    return records


def method_paths():
    return sorted(p for pattern in ['*.py', 'tests/*.py', 'protocol/*', 'data/*', 'development/*']
                  for p in ROOT.glob(pattern) if p.is_file())


def verify_method():
    freeze = ROOT/'method-freeze.json'
    records = read(freeze)['files_sha256']
    actual = {str(p.relative_to(ROOT)): sha(p) for p in method_paths()}
    if actual != records:
        raise ValueError('Frozen protocol, descriptions, rules or scripts changed')
    verify_dependencies()
    return sha(freeze)


def verify_preflight():
    method = verify_method()
    result = read(ROOT/'audit/preflight.json')
    if result.get('passed') is not True or result.get('method_freeze_sha256') != method:
        raise ValueError('Six-pair preflight has not passed for this freeze')
    if result.get('standard_combinations') != 6:
        raise ValueError('Expected exactly six standard contract/program combinations')
    return sha(ROOT/'audit/preflight.json')


def legacy():
    verify_dependencies()
    path = BASE/'experiments/reward-contract-e2e-v1/run_e2e.py'
    name = '_unchanged_explicit_contract_interface'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def contract_for(label):
    if label == 'U':
        return None
    if label not in ('E', 'V'):
        raise ValueError('Unknown semantic label')
    profile = read(ROOT/'protocol/analysis-profile.json')
    result = {k: copy.deepcopy(v) for k, v in profile.items() if k != 'note'}
    result['obligations'] = ['equals_reference' if label == 'E' else 'valid_boolean_token']
    return result


def semantic_class(contract):
    """Evaluation only; never rewrite or complete the analyzed obligation list."""
    if contract is None:
        return 'U'
    ids = contract['obligations']
    if 'equals_reference' in ids:
        return 'E'
    if ids == ['valid_boolean_token']:
        return 'V'
    raise ValueError('Invalid obligations are not a valid abstention')
