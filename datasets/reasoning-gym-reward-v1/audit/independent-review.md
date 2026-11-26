# Independent dataset review

Verdict: **pass for seven primary subjects, plus one qualified semantic-order control**. The original eight-subject, 63-probe replay is sound within its recorded domains. A separate output-schema diagnostic requires excluding GroupAnagrams from primary/general normal-negative labels; that qualification resolves the material labeling concern. This audit made no analyzer changes, fetched no new sources, and executed no upstream method, module, generator, model or training job. It inspected root's two replay rounds and independently checked their results.

| Subject | Probes | Observed full-credit violations |
| --- | ---: | ---: |
| Coin-flip original, issue 543 | 11 | 3 |
| Game-of-Life original, issue 544 | 7 | 3 |
| Complex arithmetic original, issue 545 | 9 | 3 |
| PR561 proposed repair | 8 | 0 |
| PR562 proposed repair | 10 | 0 |
| Palindrome scoped control | 7 | 0 |
| Group-anagrams qualified semantic-order control, outside primary normal negatives | 6 | 0 on original valid-list probes |
| Prime-factorization scoped control | 5 | 0 |

The reviewed set contains six scoring families, three known-bug issue families and one project. The primary set now contains seven subject versions: three known originals, two proposed upstream repairs and two property-scoped normal controls (Palindrome and PrimeFactorization). GroupAnagrams remains the eighth qualified semantic-order control. The original/repair pairs and related probes are correlated.

## Verified evidence

Read-only checks independently verified six ref/commit/tree chains; all 21 saved per-file provenance records against source bytes, SHA-256, Git blob SHA-1, decoded saved blob responses and recursive trees; all 12 extracted method/helper instances against the pinned source ASTs; and all 26 exact bug-contract source excerpts against their line spans. Both proposed PR heads and their changed-file blob identities match the saved metadata. Each of the 63 raw finite scalar rewards independently satisfies its source-behavior expectation, including the legitimate `exp(-1)` partial score. Both captured stdout files match their summaries and stderr files are empty.

Task meaning is anchored outside reward branches: fair-coin probability questions and binomial construction; explicit True/False Game-of-Life questions; complex-operation prompts with finite reference metadata and upstream scoring tests; palindrome instructions requiring every letter; order-independent anagram grouping instructions; and prime-factorization questions with number/factor fields. The small manual fixtures were checked mathematically. They are native scoring inputs, not generated benchmark rows. Board dynamics, generator correctness and seeded full-package reports were not reproduced.

An independently written semantic check confirms exactly nine full-reward violations. For anagrams it recomputes signatures and word multiplicities from the input words instead of merely trusting `metadata.solution`. For complex answers it requires both finiteness and equality to the finite reference. The replay's intentionally narrower predicate checks only finiteness; it is a necessary check for the targeted NaN defect, not a complete finite-correctness oracle. The two finite-partial rows differ under the stronger predicate, but return approximately 0.367879, so every observed full-reward violation classification agrees.

## Normalization correction retained

Replay-01 already matched all 63 source-reward expectations, but falsely flagged the two valid `((3.0 + 2.0i ) )` rows because the independent predicate omitted documented nested-parenthesis normalization. The original upstream scoring unit test explicitly accepts that representation. Replay-02 corrects normalization before native complex parsing. The old script, both raw replay rounds, and `audit/contract-validator-correction.json` remain present.

The diff affects only that independent predicate. All 63 answers, entries and actual rewards are identical between rounds. Exactly those two false-positive flags changed; no target source or witness was changed. The correction is consistent with the pre-existing contract.

## Additional GroupAnagrams schema boundary

Root performed one additional isolated real-method diagnostic, saved as `results/schema-boundary-diagnostic.json`, using the unchanged question/reference and candidate string `[{"eat":0,"tea":0},{"nat":0,"tan":0}]`. The real method returned **1.0**, although the decoded JSON fails the prompt's explicit list-of-lists-of-strings schema. Source review explains this: `_sort_nested_list` iterates each dictionary's keys and recovers the correct word partition. This audit independently checked the representation failure and key-based grouping; it did not rerun the target.

The candidate is valid as the method's string input type but invalid under the stated task-output representation. The original list-only contract therefore supports semantic-order checks, not broad output-schema soundness. Keep GroupAnagrams only as a **qualified semantic-order control** for valid list inputs and exclude it from primary/general normal-negative labels. The separate observation is exploratory and contract-sensitive; it is not promoted to a confirmed new upstream bug family or training exploit.

The original 63 replay inputs, rewards and raw records remain unchanged. They and the one diagnostic total 64 canonical-plus-diagnostic method evaluations. Replay-01's earlier 63 evaluations are a preserved validation round, not additional independent samples.

## Label and execution boundaries

`baab` and `abba` both satisfy the palindrome task for a,a,b,b. Reordered anagram groups and reordered prime factors are valid. Positive partial scores of 0.02/0.05 for incomplete palindrome answers, 0.01 for wrong parseable groupings, and 0.5 for the composite decomposition 3×4 are deliberate; they are not full-credit defects. Prime-factorization's uncaught nonnumeric-token `ValueError` and permissive separator parsing remain visible limitations of its scoped numeric-factor contract.

PR561 and PR562 are **open, unmerged proposed upstream repairs** at the saved heads. Their populated API `merge_commit_sha` values do not establish merging. The evidence supports closure of the curated issue544/545 witnesses, not a merged release, exhaustive proof or globally correct scorer. Coin-flip has no verified repair in the bounded saved evidence.

Official issue reports, source review, and root's extracted-real-method execution are separate evidence levels. Root replay executes exact scoring/helper ASTs with deferred annotations, a synthetic empty class, allowlisted standard-library globals, CPU limits and subprocess timeouts. No upstream package/module import, installation, constructor, generator or complete framework execution occurred in that replay. The restrictions are not a general-purpose secure Python sandbox. The independent reviewer inspected raw execution evidence rather than rerunning target code.

Exactly eight primary control modules were inspected. Three controls were initially selected, preserving the explicit one-control deficit; final primary normal eligibility is two after GroupAnagrams qualification, and no count was forced. NQueens remains source-reviewed and excluded because its real fallback uses `eval`; no replacement evaluator or target execution was introduced. The other selection/rejection inventory remains intact. A scoped normal label does not assert arbitrary-input totality or whole-module absence of bugs.

Every inspected source is exposed development material. This single-project, source-selected, correlated collection cannot support held-out, unseen-helper or cross-project generalization claims. Curator records/notes and immutable replay inputs retain their earlier handoff roles/states. Root final aggregation remains pending: its manifest and README must point explicitly to `results/replay-02`, distinguish curator snapshots from execution evidence, and record the seven-subject primary eligibility and separate qualified GroupAnagrams role. Initial audited artifact hashes remain in the JSON, with the schema diagnostic hash added.

Machine-readable details and reviewed artifact hashes are in `audit/independent-review.json`.
