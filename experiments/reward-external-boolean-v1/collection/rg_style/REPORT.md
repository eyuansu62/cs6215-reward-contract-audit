# RG-style external source screening lane

Five public projects were pinned before reading candidate content. This lane selected **zero** new independent scalar Boolean reward callbacks. It did not run a model, analyzer or target scorer, and did not alter any existing interface or source.

| Repository | Pinned commit | Source-backed exclusion |
|---|---|---|
| EnvCommons/ReasoningGym | `460ae1a987c40d4bd9c1964566affb3daf99198f` | `base_env.binary_score(dataset, answer, entry)` adds real binary-reward wrapper logic, but returns `(reward, raw_score)` and calls a dataset scorer plus a helper. The environment submission returns ToolOutput and uses self-state. No scalar component was extracted or rewritten. |
| huggingface/OpenEnv | `9fac2a9acae682d5c18857198eac7152d7bf1a63` | Native environment `step` delegates to the RG dataset scorer; it is not an independent answer/entry Boolean callback. |
| NousResearch/atropos | `296a0bc55760e43b9c0743c052f8d6c2732606d1` | Async/stateful RG environment wraps task creation, tag extraction and delegated scoring. It is not a fresh independent RG-compatible scalar reward method. |
| apple/ml-multilingual-reasoning-gym | `260d3e6a883bcc5be24cbd1c1d7e9dfcf1efeae4` | Default/reseeding scorers match previously exposed implementations after stripping docs/annotations. The localized GoL scorer differs in text but remains the already exposed task/scorer family. Translated reference strings cannot be assumed canonical in all configurations. |
| researchim-ai/reasoning-gym-ru | `a66a7e796552ff23410508a6c696a6f1a70a9988` | Modified known generic default scorer adds strip/0.01 branches; not counted as a new independent task scorer. Reseeding wrapper matches prior source. |

The initial bounded lookup attempted 12 specific document/source paths, with two 404s. Two same-project path corrections then produced 12 successful text artifacts in total, including seven Python source files. Metadata trees were used to locate genuine paths and distinguish copied task inventories from added task content. No broad claim about all external projects follows from this lane.

`source-review.json` retains exact method sources, argument lists, lines, AST hashes, exact previous-copy matches and delegation-call evidence. The comparison removes only docs/annotations and preserves identifiers; it is not a semantic-equivalence test. Known-family and wrapper exclusions are separately explained rather than inferred solely from hash equality.

`EnvCommons` is deliberately not dismissed as a no-logic delegator: its wrapper changes binary correctness treatment. It remains incompatible because its native return is a tuple and the boundary is stateful/delegated. Returning only the first element would create a new wrapper, which this study has not done.

No function was alpha-renamed, parameter-rewritten, return-projected, or converted from another answer encoding. Later user authorization for source-grounded argument/reference bindings does not turn tuple or ToolOutput returns into native scalar rewards; the source evidence remains useful to the root's broader search.

## Artifacts

- `candidate-sources.json`: commit pins and initial GET provenance.
- `envcommons-path-corrections.json`: corrected native paths after a 404.
- `source-review.json`: exact source and reasons for exclusions.
- `exposure-inventory.json`: content/metadata exposure for future studies.
- `lookup-log.json`: query topics and failed search transports.
- `raw/`: pinned source/docs and tree/pin metadata.

The GitHub connector returned Unknown tool. Public raw reads succeeded with normal host permissions. A grep.app query was rate-limited and contributed no source. Search results incidentally contained old RG issue snippets; none were used to select candidates or derive labels. No dependencies or upstream code were executed.
