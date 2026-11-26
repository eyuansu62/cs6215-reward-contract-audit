# Independent results review

Verdict: **pass for source-exposed development characterization and same-machine replay**. No blocking result, scoring or raw-engine issue was found. Frozen method SHA-256 is `0925274a7d4b18780fabc611d75c03e0dc9066ef426781ca1a85a2b33edeb1de`; all frozen bytes and prior-reviewed implementation hashes agree.

The primary set remains seven correlated function-version/contract cases from five families in one project. GroupAnagrams is excluded. The eight authored synthetic diagnostics are scored separately. Independent counting reproduces these primary results:

| Method | TP | FP | FN | TN | Positive Unknown | Negative Unknown | Accuracy | Recall including Unknown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Semgrep | 3 | 0 | 0 | 4 | 0 | 0 | 7/7 | 3/3 |
| Bounded symbolic | 1 | 0 | 0 | 3 | 2 | 1 | 4/7 | 1/3 |

Semgrep finds the shorter-prefix ratio, Boolean truthiness equality and nonfinite exponential clamp. The symbolic checker finds the Boolean counterexample and certifies the normalized Boolean repair, palindrome guards and prime-factor multiset equality. Its probability Unknown stops at unsupported `answer.replace`; both complex Unknowns stop at the parse helper. Those are authored model/coverage limits, not evidence of neural necessity. Semgrep NoAlarm remains a completed fixed-rule scan rather than a semantic proof.

On the separate eight synthetic diagnostics, Semgrep has 2 TP, 3 FP, 1 FN and 2 TN. The symbolic checker has 1 TP, 3 TN and 4 Unknown. It gives two determinate corrections for a semantic preguard and dead code; all four numeric diagnostics are Unknown. Both methods score 4/8 accuracy under the fixed accounting. The finite-adjacent and rebound-guard cases are determinate-correct Semgrep results that the symbolic checker abstains on.

All per-case verdicts, Unknown denominators, paired gains/losses and saved metrics were recomputed independently of the runner scoring function. Across both rounds and both sets, all 30 Semgrep scans completed with exact source bytes, the same rules, pinned native engine hash, matching raw JSON/stdout, empty stderr, no errors/skips/timeouts and complete function/return coverage against the source AST. All prediction raw records agree and there are no unexpected errors. Input identities, fixed contracts and absence of forbidden evaluation fields were checked; prior frozen-code review found no ID/gold/witness decision logic.

Both replay-comparison artifacts are present and passed. Independent comparison confirms equal analytical predictions and scores for primary 01/02 and diagnostic 01/02 after only timing/run-path normalization; commands, source/rule bytes and core hash were separately checked. No target scorer, model or network operation was run for this audit.

One presentation limit remains in frozen output: expanded Boolean facts reuse the whole original BoolOp text, so printed conditions can repeat with different truth flags. Their underlying atomic Terms differ. This does not change the checked labels or counts, but the displayed list should not be described as an executable atomic proof trace.

No LLM, neural analyzer, contract-inference procedure or training system was tested. This experiment establishes neither a need nor a benefit for a neural component. Supplied reviewed contracts, selected exposed source and same-machine replay do not establish held-out generalization, global repair correctness, outer-wrapper behavior or RL exploitation.

REPORT.md and README.md match the independently checked outcome tables and limits. Their decision is to retain the non-neural baselines without integrating an LLM. Independent task-description-to-contract generation is explicitly a possible future study, not an implemented or validated improvement; currently exposed families cannot supply its holdout. The report distinguishes Codex-assisted authorship from absence of an experimental LLM detector. Saved pre-freeze checks support the stated 61-test and archive-integrity counts; the projection test and full archive hashes were not rerun in this results audit.
