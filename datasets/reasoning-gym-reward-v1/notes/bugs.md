# Public reward defects and proposed upstream repairs

This curation contains three issue families and five version records. It is dataset evidence, with no analyzer implementation, classifier/model run, package import, generator execution, or target-method execution. All executable checks are pending the root agent's isolated source-only reproducer. AST parsing and hashing inspect source without importing it.

| Record | Source commit | Evidence and scope |
| --- | --- | --- |
| `rg-issue-543-original` | `49b07130b3fcd12f2d064bba7c43869543a0e7e7` | Coin-flip wrong short probability prefixes get 1.0. No verified upstream repair. |
| `rg-issue-544-original` | `49b07130b3fcd12f2d064bba7c43869543a0e7e7` | Game-of-Life nonempty wrong Boolean strings get 1.0. |
| `rg-issue-545-original` | `49b07130b3fcd12f2d064bba7c43869543a0e7e7` | Complex NaN submissions get 1.0. |
| `rg-pr-561-proposed-repair` | `4ab6143b1858f5bf09ebe23501a8ffd77c86cdf0` | Open, unmerged string-equality repair of issue 544. |
| `rg-pr-562-proposed-repair` | `758f7fb8e0c732571d3ab6b67f78207f203f3502` | Open, unmerged finite-distance repair of issue 545. |

The status is taken from saved PR JSON: `state=open`, `merged=false`, `merged_at=null`. A populated API `merge_commit_sha` is not evidence of a merged repair. No merged fix version or release has been verified. Candidate repair records are scoped to their particular property and do not claim globally correct scorers. Version pairs and probes must not be counted as independent bugs.

## Contract and witness decisions

For issue 543, the task computes the probability of exactly/at least k heads in n fair flips. The explicit reference `0.875` is valid for at least one head in three flips (7/8), and appears in the issue. Candidate strings `0`, `0.8`, and `0.87` have numeric errors greater than the default tolerance `1e-4`; nevertheless the common-prefix count divided by the shorter canonical string's length yields 1.0. The intended corrected partial score is unspecified, so the expected counterexample condition is `<1.0`. We do not invent an exact corrected score or implement the issue's suggested denominator change. The scorer's docstring mentions extra text, but `Fraction` does not extract a value from arbitrary prose; that claim is not promoted into the accepted domain.

For issue 544, the prompt explicitly asks `True` for halting and `False` otherwise, and the generator stores `str(not should_oscillate)`. Both strings are truthy. Minimal fixtures contain only the consumed `answer` field; they preserve a legal generated reference value but are not claimed to be generated/simulated boards. Board placement, dynamics, and oracle correctness are outside this record's verified scope. PR561 changes only the string comparison, including lowercase/whitespace normalization, and adds tests for opposite values, `banana`, empty, missing, and valid normalized answers.

For issue 545, the exact minimal reference `(3.0, 2.0)` comes from the existing upstream scoring unit test. JSON uses a list with the same numeric components, which `complex(*components)` accepts. Bounded integer arithmetic references are finite. The helper accepts NaN via `float` or `complex`; NaN distance reaches `min(1.0, math.exp(-distance))`, yielding full reward. The issue's seeded report is distinguished from our source-reviewed prediction for this explicit unit-test reference. PR562 adds parser-None and nonfinite-distance rejection and returns exponential distance directly. Normal controls preserve legitimate finite partial credit. The apparent infinity example `inf + 2i` is already rejected by the original parser (the helper globally replaces `i`, including within `inf`); it is not evidence of the new guard's effectiveness. Proposed-head control `nanj` exercises that guard.

## Exact extraction handoff

The JSON includes whole-method source, exact line spans, file SHA256 and Git blob SHA1, method-source SHA256, and SHA256 of `ast.dump(node, annotate_fields=True, include_attributes=False)`. The helper fetcher verified the decoded byte size and Git blob identity against the pinned recursive tree. Per-file provenance is under `collection/source-provenance/{snapshot}/...json`. Entire original/head/base modules and upstream changed tests are retained under `upstream/`.

- CoinFlipDataset.score_answer: original lines 113–149; no self state or helpers; only `from fractions import Fraction` is needed. Preserve the `tol=1e-4` default.
- GameOfLifeHaltingDataset.score_answer: original/head lines 385–401; no self state, helpers, or module globals are needed. No `cellpylib` import or board generation is necessary.
- ComplexArithmeticDataset.score_answer: original lines 168–183, candidate lines 168–187. Extract the exact static helper `parse_string_to_complex` (decorator line 111 through line 166), bind it as a staticmethod, and allow only standard-library `math`. No constructor state is needed. `cmath` and generator imports are unused.

Method annotations can be removed or deferred in the extraction harness; they are not scorer runtime dependencies. Do not run module imports, constructors, generators, factory registration, or upstream pytest modules. The saved upstream tests supply contract evidence and were inspected, not executed.

## Remaining evidence limits

The source-reviewed reward predictions in `counterexamples` and `normal_controls` are not execution results: `actual_observed_reward` remains null and validation flags remain false. Root-owned reproduction must populate independent run evidence. Official reports, projected fixtures, and curated extensions are individually marked. No coin-flip fix was verified in the bounded saved evidence set; this is not an exhaustive claim about all future or unrelated upstream work.
