"""Execute one exact, hash-pinned study function in an isolated Python process."""
import __future__
import hashlib
import json
import math
from pathlib import Path
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    freeze_path = root / 'method-freeze.json'
    frozen = json.loads(freeze_path.read_text())
    for name in ('native_worker.py', 'data/programs.json'):
        if digest(root / name) != frozen['files_sha256'].get(name):
            raise ValueError('Native execution file differs from method freeze: ' + name)
    request = json.load(sys.stdin)
    if type(request) is not dict or set(request) != {'program_id', 'answer', 'reference', 'method_freeze_sha256'}:
        raise ValueError('Exact native request fields required')
    if request['method_freeze_sha256'] != digest(freeze_path):
        raise ValueError('Unexpected method freeze')
    if request['answer'] is not None and type(request['answer']) is not str:
        raise ValueError('Candidate must be a native string or None')
    if type(request['reference']) is not str or request['reference'] not in ('True', 'False'):
        raise ValueError('Reference must be a canonical Boolean string')
    programs = json.loads((root / 'data/programs.json').read_text())['programs']
    if {p['program_id'] for p in programs} != {'equality', 'token_only', 'truthiness'} or len(programs) != 3:
        raise ValueError('Exactly the three pinned programs are executable')
    matches = [p for p in programs if p['program_id'] == request['program_id']]
    if len(matches) != 1:
        raise ValueError('Unknown program')
    program = matches[0]
    if program['source'] != program['score_source'] or program['entry_name'] != 'score_answer':
        raise ValueError('Exact source/entry disagreement')
    # Postpone the frozen annotations without inserting imports or changing source.
    code = compile(program['source'], '<pinned:' + program['program_id'] + '>', 'exec',
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)
    namespace = {'__builtins__': {'bool': bool}}
    exec(code, namespace)
    reward = namespace['score_answer'](None, request['answer'], {'answer': request['reference']})
    if type(reward) not in (int, float) or not math.isfinite(reward):
        raise ValueError('Reward must be a finite native JSON number')
    # Stdout is deliberately just the reward scalar. The parent records the input.
    print(json.dumps(reward, allow_nan=False))


if __name__ == '__main__':
    main()
