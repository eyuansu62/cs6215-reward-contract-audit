# Independent saved-results review

**Passed, with a bounded controlled-coverage claim.** The review reads saved artifacts and recomputes their statistics and Boolean predicates. It makes no new model, analyzer, scorer or test calls.

| Condition | Correct classes / 12 | TP | FP | FN | TN | Unknown | Witness-supported correct / 24 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| reference | 12 | 12 | 0 | 0 | 12 | 0 | 24 |
| rules | 5 | 2 | 0 | 0 | 1 | 21 | 3 |
| llm | 12 | 12 | 0 | 0 | 12 | 0 | 24 |
| fixed_E | 4 | 12 | 4 | 0 | 8 | 0 | 16 |
| fixed_V | 4 | 8 | 0 | 4 | 12 | 0 | 20 |
| fixed_null | 4 | 0 | 0 | 0 | 0 | 24 | 0 |

The denominator is 24 nonnull description/program cells, repeating six policy/program combinations. Four U descriptions add 12 administrative cells per condition and are excluded from binary counts. Both extractors correctly abstain on every U description.

In this single frozen controlled run, the LLM extractor matched all 12 researcher-assigned semantic classes, versus 5 for the fixed six-development-card rule baseline, and increased witness-supported correct determinate decisions from 3/24 to 24/24 repeated nonnull policy/program cells without added false positives, unjustified returned witnesses, or U-policy obligations. All 21 paired cell gains resolved baseline abstentions. This supports controlled contract-selection coverage gain only.

The rules extract only P28 and abstain on the other eleven cards. Four abstentions are justified U results; seven miss a supported E or V contract. Thus the 21 additional correct cells are increases in coverage, with no incorrect determinate rule verdict to repair. The baseline was fixed from six development cards, and this limitation must accompany the result.

The witness distinction changes the fixed-E comparison. For P35 (gold V) paired with truthiness, fixed E returns `False` against reference `True`, with saved native reward 1.0. The equality predicate is false, but Boolean validity is true, so this returned witness does not justify a V violation. The LLM selects V and the static checker returns `__not_a_boolean_token__`, also rewarded 1.0; that witness violates V. The saved `banana` probe separately confirms the same V defect. Across all four V descriptions, fixed E has four such coincidental TPs in addition to four FPs on token_only. Consequently its 20 binary-correct cells contain only 16 witness-supported correct decisions.

All method hashes match the pre-model review and freeze; all 99 model-sealed files and all 33 comparison artifacts match their manifests. The chronological records and hash dependencies show method freeze before preflight and predictions, and response seal before comparison. Six standard preflight combinations match their expected determinate verdicts. All twelve raw model responses match their event messages and accepted contracts; evidence is quoted exactly from the cards. E responses retain their original ordered `[valid_boolean_token, equals_reference]` lists. No obligation repair or method/source/prompt/rule change is visible.

The audit independently checks 216 saved global rows, 28 raw native execution records from comparison, and 2,016 condition-level decisions across 336 saved witness rows, finding no mismatches. Preflight has its own 28 native executions. The review does not rerun any of them.

Raw usage across the twelve successful turns is 303,662 input tokens, including 83,328 reported cached input tokens, and 1,834 output tokens. Reported reasoning-output tokens are zero. Parallelism is three: batch elapsed time is about 32.84 seconds, while summed per-request wall time is 84.86 seconds. All exact model identity fields are null; temperature, seed and monetary cost are unreported. Token counts describe service-reported usage, not merely the visible prompt.

Transport stderr contains startup warnings/errors about system skills, models cache and MCP initialization. Each command nevertheless exits zero, has exactly one completed model turn and has no model tool/action event. The artifacts support the explicit payload boundary; they do not establish a fully hermetic or error-free implicit service context.

The positive claim concerns controlled contract selection and coverage. It is not evidence of new independent real bugs, improved static-analysis semantics, broad superiority over rule systems, or reduced human effort. The researcher-assigned language labels are not formal semantic proofs. No-alarm results establish only necessary full-credit obligations, so permitted-answer under-rewarding and complete scoring correctness remain outside scope. No iid statistical inference is justified by the repeated cells.

## Final reporting delta review

**Passed.** The final Chinese report and English supplement preserve the controlled-coverage interpretation, repeated-cell denominators, Unknown handling and binary-versus-witness distinction. The 21 wins are ten additional verified alarms and eleven necessary-condition certificates, all from previous abstentions; no incorrect determinate rule verdict was corrected. The reports explicitly limit the six-development-card baseline, distinguish correct U labels from demonstrated semantic understanding, disclose parallel AI-assisted authorship, and retain the one-sided reward scope.

All resource-ledger records match the saved per-request metadata. Exact model identity, monetary cost and implicit service context remain unverified; reported latency and tokens exclude research/design/review costs. Startup warnings are disclosed. The rendered comparison image was inspected and matches the numerical table, with a zero-based scale and separate Unknown and witness-supported measures. No experiment was rerun and no method file changed.

Final reviewed artifact hashes:

| Artifact | SHA-256 |
| --- | --- |
| REPORT.md | `31e2aef94a75e3cc12628f3af179e6742c5facdff61b71b65fea5b348a605c6b` |
| SUPPLEMENT.md | `8d38252e3c38928c543a67e150f043c8f306aba8a024391cbc896f96bd463d6d` |
| analysis/resource-ledger.json | `67e6c3f3c2e4b1da82f0ebd75246377fe26948658a052783790fc6cdb6b4fece` |
| figures/downstream-comparison.png | `152897c9f722f893cfafdfa34da5302c5b10e38695f794673a4b098b2c550d26` |
