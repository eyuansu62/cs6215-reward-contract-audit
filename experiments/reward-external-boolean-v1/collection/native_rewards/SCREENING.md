# External native reward-source lane

No eligible test function was selected. This lane collected and pinned 23 source/document files from seven real project repositories. No target function was imported or executed; no model or analyzer was run. All file SHA256 and Git blob IDs match their fixed repository trees.

## Initial exact-binding phase

Twelve files from four projects were checked before the binding-only authorization.

| Project | Pin | Native endpoint | Reason excluded |
|---|---|---|---|
| volcengine/verl | 69921c419cb4ee880c01744f0e6ffcf17337abc0 | compute_score(solution_str,ground_truth,...) or model_output/ground_truth | Initial frozen answer/entry layout mismatch; no Boolean-task invocation established |
| hiyouga/EasyR1 | a73346d028ba0335aa42da104972c86e6cd0fe69 | compute_score(reward_inputs/reward_input,...) | Batch or dictionary returns, not scalar callback |
| OpenRLHF/OpenRLHF | 26494490bc237f6c3af62dab6117e6bbb0a78dba | reward_func(queries,prompts,labels,**kwargs) | Batch/tensor/dict API; generic reward example is random reward |
| NousResearch/atropos | 296a0bc55760e43b9c0743c052f8d6c2732606d1 | completion-batch reward functions; async BoolQ evaluator | List/dict/stateful APIs. BoolQ native prompt and gold are A/B or Yes/No |

## Parameter-binding phase

Root then authorized only source-grounded parameter/reference-field bindings. The initial phase freeze was preserved and a separate amendment recorded before new content reads. Eleven of the twelve allowed additional files were used.

- **kbwal/rl-next-tokens**, pin `5c6cd2fb617ca117caeba1828addd1a63d6501cf`: real GRPO training, but reward is continuation log probability/format/length, not Boolean answer correctness. Boolean BBH is an evaluation task.
- **zzx-peter/Multiple-Solution-TTRL**, pin `5d30fc7ecc20d898a6e4ee5b1f99ca55cd94004a`: the file named `boolean` scores structural logical-expression discovery against lists of formulas and returns a dictionary. It is not a True/False token task.
- **coder-qicao/RL4GLUE**, pin `2ad8bc53f663797bef091db108175fc8651cf538`: BoolQ is Yes/No within Judgement tags, MultiRC is True/False within Judgement tags; native training rewards are model-dependent combinations or batch metrics. A scalar SQuAD exact-match helper was not relabelled as a Boolean reward.

The remaining budget was not filled by reading a known non-Boolean source. Metadata-only repositories and unsuccessful search routes are retained. The GitHub connector search returned Unknown tool and was replaced with primary public REST/raw reads. No source rewrite, synthetic wrapper, label conversion, parser-output substitution, batch slicing or result-value coercion was introduced.

`screening-status.json` contains per-file/per-project reasons. `candidate-sources.json`, `binding_phase/source-records.json`, source files and fixed repo trees support direct review. `phase1-freeze.json` binds the initial collection; `phase2-freeze.json` binds this lane's final materials. This is a bounded data-eligibility audit, not a claim about all external projects and not performance evidence.
