"""Finalize a bounded source-availability census, not an analyzer experiment."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parent

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 metadata=read(ROOT/'first-pass-metadata.json');sources=read(ROOT/'source-manifest.json');trace=read(ROOT/'answer-field-traces.json')
 spec=importlib.util.spec_from_file_location('_conservative_dedup',ROOT/'answer_domain_review.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 def fp(source):return mod.fingerprints(ast.parse(source).body[0])
 a=fp('def score_answer(self, answer, entry):\n return bool(answer)\n')
 b=fp('def score_answer(self, answer, entry):\n return str(answer)\n')
 c=fp('def score_answer(owner, candidate, record):\n return bool(candidate)\n')
 assert a['alpha_lexical_local_sha256']!=b['alpha_lexical_local_sha256']
 assert a['alpha_lexical_local_sha256']==c['alpha_lexical_local_sha256']
 (ROOT/'dedup-selfchecks.json').write_text(json.dumps({'passed':True,'global_bool_vs_str_kept_distinct':True,'parameter_alpha_rename_same':True,'source_imported_or_executed':False,'fingerprint_claim':'heuristic only; no semantic equivalence proof'},indent=2)+'\n')
 classifications={
 'reasoning_gym/algorithmic/cryptarithm.py':('nonboolean_mapping','Prompt asks comma-separated letter-to-digit mapping A=1,B=2,C=3; True/False appears only in config/validator docs.'),
 'reasoning_gym/algorithmic/game_of_life_halting.py':('already_exposed_canonical_boolean','Canonical True/False task, but it is the already-developed #544 scoring implementation.'),
 'reasoning_gym/algorithmic/graph_color.py':('nonboolean_mapping','Prompt requests a JSON vertices-to-colors map; validator is Boolean internally.'),
 'reasoning_gym/algorithmic/isomorphic_strings.py':('already_exposed_and_inherited','Canonical True/False, but previously exposed and inherits old default score.'),
 'reasoning_gym/algorithmic/jugs.py':('nonboolean_move_list','Prompt requests JSON-parsable list of jug moves; Boolean verifier result is not submission format.'),
 'reasoning_gym/algorithmic/ransom_note.py':('already_exposed_and_inherited','Canonical True/False, but previously exposed and inherits old default score.'),
 'reasoning_gym/arithmetic/bitwise_arithmetic.py':('nonboolean_hex_number','Prompt requests final hexadecimal value; internal correctness verifier returns bool.'),
 'reasoning_gym/games/tower_of_hanoi.py':('nonboolean_move_sequence','Prompt requests newline-separated move instructions; move-validity helper returns bool.'),
 'reasoning_gym/games/tsumego.py':('nonboolean_board_move','Submission is Go move coordinate; make-move helper returns bool.'),
 'reasoning_gym/graphs/course_schedule.py':('already_exposed_and_inherited','Canonical True/False, but previously exposed and inherits old default score.'),
 'reasoning_gym/logic/circuit_logic.py':('boolean_but_wrong_native_encoding','Generated output is string 0/1, not canonical True/False. Fixed interface cannot translate.'),
 'reasoning_gym/logic/self_reference.py':('nonboolean_solution_count','Submission is number of possible assignments; truth values appear in statement/helper logic.'),
 'reasoning_gym/probability/coin_flip.py':('nonboolean_probability','Submission is numeric probability; config assertion contains True.'),
 }
 candidates=[]
 for r in metadata['records']:
  if r['candidate_boolean_text']:
   disposition,reason=classifications[r['path']]
   candidates.append({'path':r['path'],'class':r['class'],'owns_score_answer':r['owns_score_answer'],'disposition':disposition,'eligible':False,'reason':reason,'literal_evidence':r['question_or_generator_literal_matches']})
 summary={'created_utc':datetime.now(timezone.utc).isoformat(),'commit':sources['commit'],'scope':'Same pinned snapshot, nonvendored/non-rearc/data Python task-source structural census plus source-reviewed Boolean-like candidates. Not arbitrary-Python complete return-domain proof.',
  'archive_bytes':(ROOT/'pinned-source.tar.gz').stat().st_size,'extracted_exact_git_blobs':sources['extracted_python_blobs'],'git_blob_verification':True,
  'dataset_named_classes':metadata['task_dataset_classes'],'own_score_classes':metadata['own_score_classes'],'boolean_text_hint_classes':metadata['boolean_text_classes'],
  'answer_field_trace_classes':len(trace['records']),'confirmed_canonical_TrueFalse_task_families':['game_of_life_halting','isomorphic_strings','ransom_note','course_schedule'],
  'all_confirmed_canonical_families_previously_exposed':True,'confirmed_canonical_with_own_score':['game_of_life_halting'],
  'new_eligible_distinct_canonical_scorers_confirmed':0,'selected_independent_test_cases':[],
  'boolean_like_candidates':candidates,'diagnosis':'No fresh canonical True/False task with an own unique scorer was identified by the full retained structural census and candidate review. The candidate shortage is not solved by the additional same-commit source inventory.',
  'limits':['This is source availability/scope evidence, not a completed LLM/analyzer evaluation.','Structural answer traces are incomplete for arbitrary dynamic/delegated generators; lack of a hint is not a theorem of non-Boolean output.','Census excludes vendored, rearc generators/data and package initializers by prior amendment.','No independent test cases are invented from mutated sources, encoding translations or inherited duplicate functions.','No new-head source or different repository has been used.'],
  'model_calls':0,'analyzer_runs':0,'upstream_method_execution':False,'analyzer_feature_changes':False,
  'current_ref_metadata':'../current-ref-assessment.json'}
 (ROOT/'census-conclusion.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 exposure={'purpose':'All retained raw-source modules are now exposed; exclude these exact bodies and derived helper closures from later fresh-content claims.','commit':sources['commit'],'sources':sources['sources'],'new_source_files_relative_to_start_of_census':sum(not x['previous_content_exposed_before_census']for x in sources['sources']),'task_outcomes_or_model_predictions_observed':False}
 (ROOT/'source-exposure-inventory.json').write_text(json.dumps(exposure,indent=2)+'\n')
 lines=['# Same-commit Boolean source availability census','',f"Pinned commit: `{sources['commit']}`. One 8.60 MB public codeload archive was read after an explicit amendment; 122 regular Python blobs matched the cached git tree exactly. No source executed.",'', 'Metadata covers 108 Dataset-named classes (including support wrappers), 75 own score definitions, and all 108 answer-field traces. Thirteen classes had non-score True/False/Boolean string hints; their actual requested output domains were reviewed.','', '| Canonical True/False family | Own scorer | New source content? | Eligible |','|---|---|---|---|','| Game of Life halting | yes | no, developed #544 | no |','| String isomorphism | no, inherited | no | no |','| Ransom note | no, inherited | no | no |','| Course schedule | no, inherited | no | no |','', '**No new eligible distinct canonical Boolean scorer was confirmed.** Circuit logic uses native 0/1, syllogisms Yes/No, ACRE on/off/undetermined. Other hint matches are internal validators for mappings, moves, arithmetic or counts. None were recoded to force the unchanged interface.','', 'This is broader source-availability evidence, not a complete theorem about arbitrary dynamic return values or all future project versions. The fixed census excludes vendored/rearc-generated/data sources and does not execute delegated generators. No LLM/analyzer outcomes were produced.','', 'Conservative dedup hashes preserve global/builtin/member names. The earlier broad-alpha normalization risk remains documented in ../dedup-erratum.json; no initial eligibility decision depended on that hash. Hash equality is not semantic-equivalence proof.','', 'Current-main metadata differs from the pin but has no added Python filenames; source contents at that newer head were not read. Do not silently switch versions or count the inherited default scorer under multiple tasks as independent implementations.']
 (ROOT/'CENSUS.md').write_text('\n'.join(lines)+'\n')
 paths=sorted(p for p in ROOT.rglob('*')if p.is_file()and'__pycache__'not in p.parts and p.name!='census-freeze.json')
 (ROOT/'census-freeze.json').write_text(json.dumps({'files_sha256':{str(p.relative_to(ROOT)):sha(p)for p in paths},'models_and_analyzers_not_run':True,'conclusion':'No eligible new canonical-TrueFalse own scorer confirmed in retained census scope'},indent=2)+'\n')
 print(json.dumps({k:summary[k]for k in ['extracted_exact_git_blobs','dataset_named_classes','own_score_classes','new_eligible_distinct_canonical_scorers_confirmed','model_calls','analyzer_runs']}))

if __name__=='__main__':main()
