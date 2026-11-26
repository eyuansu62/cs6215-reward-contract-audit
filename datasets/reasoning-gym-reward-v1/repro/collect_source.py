"""Download fixed public source evidence; never imports upstream code."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = 'open-thought/reasoning-gym'

def now(): return datetime.now(timezone.utc).isoformat()
def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw: raise ValueError('Refusing to overwrite evidence: ' + str(path))
    else: path.write_bytes(raw)

def api(endpoint, destination):
    if endpoint != 'repos/' + REPO and not endpoint.startswith(('repos/' + REPO + '/', 'search/issues?')): raise ValueError('Unexpected API endpoint')
    if destination.exists(): return json.loads(destination.read_text())
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, check=False)
    if result.returncode: raise RuntimeError('Public API read failed: ' + endpoint + ': ' + result.stderr.decode()[:250])
    value = json.loads(result.stdout)
    save(destination, result.stdout)
    return value

def metadata():
    endpoints = {'main-commit.json': 'commits/main', 'issue-commit.json': 'commits/49b0713',
                 'repository.json': '', **{f'issue-{n}.json': f'issues/{n}' for n in [543,544,545]},
                 **{f'issue-{n}-comments.json': f'issues/{n}/comments' for n in [543,544,545]},
                 **{f'pr-{n}.json': f'pulls/{n}' for n in [561,562]},
                 **{f'pr-{n}-files.json': f'pulls/{n}/files' for n in [561,562]}}
    def one(item):
        name, route = item
        endpoint = 'repos/' + REPO + ('/' + route if route else '')
        return name, api(endpoint, ROOT/'collection'/name)
    with ThreadPoolExecutor(max_workers=4) as pool: values = dict(pool.map(one, endpoints.items()))
    refs = {'main': {'commit': values['main-commit.json']['sha'], 'tree': values['main-commit.json']['commit']['tree']['sha']},
            'issue_snapshot': {'commit': values['issue-commit.json']['sha'], 'tree': values['issue-commit.json']['commit']['tree']['sha']}}
    for n in [561,562]:
        pr = values[f'pr-{n}.json']
        for side, alias in [('head',f'pr{n}'),('base',f'pr{n}_base')]:
            commit = api('repos/'+REPO+'/commits/'+pr[side]['sha'], ROOT/'collection'/f'{alias}-commit.json')
            refs[alias] = {'commit': commit['sha'], 'tree': commit['commit']['tree']['sha']}
    for alias, ref in refs.items():
        assert re.fullmatch('[0-9a-f]{40}', ref['commit']) and re.fullmatch('[0-9a-f]{40}',ref['tree'])
        tree = api('repos/'+REPO+'/git/trees/'+ref['tree']+'?recursive=1',ROOT/'collection'/f'{alias}-tree.json')
        if tree.get('truncated'):raise ValueError('Incomplete source tree')
    save(ROOT/'collection/refs.json',(json.dumps({'repository':REPO,'recorded_utc':now(),'refs':refs},indent=2)+'\n').encode())
    print(json.dumps({'refs':refs,'pull_requests':{str(n):{k:values[f'pr-{n}.json'].get(k) for k in ['state','merged_at','html_url']} for n in [561,562]}}))

def fetch(alias, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative:raise ValueError('Unsafe source path')
    refs=json.loads((ROOT/'collection/refs.json').read_text())['refs']
    ref=refs[alias]
    tree=json.loads((ROOT/'collection'/f'{alias}-tree.json').read_text())
    matches=[x for x in tree['tree'] if x['path']==relative and x['type']=='blob']
    if len(matches)!=1:raise ValueError('Source path is not a pinned tree blob: '+relative)
    row=matches[0]
    if row.get('mode')=='120000':raise ValueError('Do not follow upstream symlinks')
    record=api('repos/'+REPO+'/git/blobs/'+row['sha'], ROOT/'collection/blobs'/f"{row['sha']}.json")
    if record.get('encoding')!='base64':raise ValueError('Unexpected blob encoding')
    raw=base64.b64decode(record['content'])
    git=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert git==row['sha'] and len(raw)==record['size']
    dest=ROOT/'upstream'/alias/relative
    save(dest,raw)
    proof={'repository':REPO,'snapshot':alias,**ref,'path':relative,'sha256':sha(raw),'git_blob_sha1':git,
           'bytes':len(raw),'source_url':f"https://github.com/{REPO}/blob/{ref['commit']}/{relative}",
           'local_path':str(dest.relative_to(ROOT)),'fetched_utc':now(),'git_blob_verified':True}
    evidence=ROOT/'collection/source-provenance'/alias/(relative+'.json')
    if not evidence.exists():save(evidence,(json.dumps(proof,indent=2)+'\n').encode())
    else:assert json.loads(evidence.read_text())['sha256']==proof['sha256']
    print(json.dumps({k:proof[k] for k in ['snapshot','path','sha256','git_blob_sha1','bytes']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['metadata','fetch']);p.add_argument('snapshot',nargs='?');p.add_argument('path',nargs='?')
    a=p.parse_args()
    if a.operation=='metadata':metadata()
    else:
        if not a.snapshot or not a.path:p.error('fetch requires snapshot and path')
        fetch(a.snapshot,a.path)
