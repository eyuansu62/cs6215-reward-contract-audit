"""One additional source-review boundary diagnostic; no analyzer is run."""
from pathlib import Path
import json
import resource
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from reproduce import ROOT,read,score,full_credit_allowed
resource.setrlimit(resource.RLIMIT_CPU,(2,3))
data=read(ROOT/'repro/replay-inputs.json')
subject=next(s for s in data['subjects'] if s['id']=='control-group-anagrams-order-main')
reference=subject['probes'][0]['entry']
probe={'answer':'[{"eat":0,"tea":0},{"nat":0,"tan":0}]','entry':reference}
observed=score(subject,probe)
result={'subject':subject['id'],'probe':probe,'observed':observed,
 'strict_list_of_lists_predicate_satisfied':full_credit_allowed(subject,probe),
 'interpretation':'The prompt specifies list-of-lists. Dictionary groups preserve the correct word partition under Python key iteration but violate that representation. Whether permissive representation deserves full reward is contract-sensitive; this is not a confirmed new upstream issue or training exploit.',
 'dataset_role':'Qualified semantic-order control for valid list inputs; exclude from unqualified schema-safety negatives.',
 'upstream_source_changed':False,'full_package_or_generator_executed':False,'analyzer_or_model_run':False}
assert observed['reward']==1.0 and not result['strict_list_of_lists_predicate_satisfied']
print(json.dumps(result,ensure_ascii=False,indent=2))
