"""Package and verify saved evidence; no experimental reruns."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
archive=ROOT.with_suffix('.zip')
if archive.exists(): raise ValueError('Preserve existing archive')
deps=json.loads((ROOT/'protocol/dependencies.json').read_text())['files_sha256']
origins=json.loads((ROOT/'data/programs.json').read_text())['frozen_origins']
extra=['experiments/reward-contract-loop-v2/case.json','datasets/reasoning-gym-reward-v1/upstream/main/LICENSE']
files={str(p.relative_to(BASE)):p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for name in [*deps,*origins,*extra]: files[name]=BASE/name
for name,h in {**deps,**origins}.items(): assert sha(BASE/name)==h
relative='experiments/reward-contract-controlled-v1'
readme=f'''# Controlled contract extraction supplement\n\nStart with [{relative}/REPORT.md]({relative}/REPORT.md), the [English supplement]({relative}/SUPPLEMENT.md), or the [study README]({relative}/README.md). This archive contains the new controlled experiment and exact minimal inherited dependencies; it does not replace the original frozen report or studies.\n\nTo verify saved evidence without model/scorer/analyzer calls:\n\n```sh\ncd {relative}\npython3 -B run_study.py verify-saved\n```\n\nPython 3.14.3 on macOS ARM64 was used. Standard library is sufficient for saved verification. Plot generation uses already installed Pillow separately; the supplied PNG needs no runtime.\n\nThe study preserves twelve one-shot requests and the original results, including service metadata and startup warnings. Model identity was not exposed. Full raw logs retain original local paths. No credentials are required for saved verification.\n\nRoot CONTΕNTS.json (ASCII filename CONTENTS.json) binds all files except itself. Existing code is copied byte-for-byte and imports no scoring package. Selected upstream source license and case provenance are included. No overall project license is assigned here.\n'''
readme=readme.replace('Root CONTΕNTS.json (ASCII filename CONTENTS.json)','Root CONTENTS.json')
content={name:sha(p) for name,p in sorted(files.items())};content['README.md']=hashlib.sha256(readme.encode()).hexdigest()
manifest={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files_sha256':content,'scope':'Saved controlled experiment and minimal inherited files; excludes this CONTENTS.json manifest itself','experimental_reruns_in_package_verification':False}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,p in sorted(files.items()):z.write(p,name)
 z.writestr('README.md',readme)
 z.writestr('CONTENTS.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(set(z.namelist()))==len(content)+1
 assert all(not x.startswith('/') and '..' not in Path(x).parts for x in z.namelist())
 assert all(hashlib.sha256(z.read(k)).hexdigest()==h for k,h in content.items())
 with tempfile.TemporaryDirectory(prefix='controlled-contract-archive-') as folder:
  z.extractall(folder);b=Path(folder)
  assert all(sha(b/k)==h for k,h in content.items())
  process=subprocess.run([sys.executable,'-B','run_study.py','verify-saved'],cwd=b/relative,capture_output=True,text=True,check=True)
  result=json.loads(process.stdout);assert result['passed']
  links=0;missing=[]
  for name in ['README.md',relative+'/README.md',relative+'/REPORT.md',relative+'/SUPPLEMENT.md']:
   p=b/name
   for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'):continue
    links+=1
    if not (p.parent/target.split('#')[0]).exists():missing.append({'file':name,'target':target})
  assert not missing,missing
check={'passed':True,'archive':archive.name,'sha256':sha(archive),'bytes':archive.stat().st_size,'archive_files':len(content)+1,'all_archive_and_extracted_bytes_match':True,'saved_verifier_result':result,'relative_links_checked':links,'missing_links':missing,'experimental_requests_or_analyzer_or_native_calls_during_package_check':0}
archive.with_suffix('.zip.sha256').write_text(check['sha256']+'  '+archive.name+'\n')
archive.with_suffix('.package-check.json').write_text(json.dumps(check,indent=2)+'\n')
print(json.dumps(check,indent=2))
