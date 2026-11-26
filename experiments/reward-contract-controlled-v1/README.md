# Controlled contract extraction and downstream consequences

This supplementary experiment compares one-shot LLM extraction with a fixed deterministic rule extractor, fixed equality/validity assumptions, and the researcher reference. The analysis engine and explicit Boolean contract compiler are imported unchanged from the preserved studies. The original final report and every prior freeze remain separate.

Read [REPORT.md](REPORT.md) for the final interpretation and [protocol/study-plan.json](protocol/study-plan.json) for the precommitted design. This is an author-constructed policy-description experiment, not a new real-world reward-bug benchmark or a human-effort study.

## Units and meaning

There are 12 descriptions: four linguistic families crossed with three policies. E requires equality to the trusted canonical Boolean reference; V requires only token validity; U has no justified obligation expressible by this interface. E and E+V are semantically equivalent for evaluation, while the actual selected list is passed unchanged to the compiler. Invalid responses are distinguished from valid abstentions.

Three previously supported programs are reused: the known truthiness scorer, its proposed normalized-equality repair, and an existing authored token-only control. Source is copied exactly. The 24 nonnull description/program cells repeat only six semantic/program combinations. The 12 U cells per condition are administrative outcomes and never static true negatives. The four language families and shared programs make the observations dependent.

Only necessary full-credit implications are audited. A no-alarm result is not complete reward-policy correctness: a scorer can under-reward allowed answers and still satisfy the checked implication. Concrete execution verifies returned witnesses; it is not the static detector and its reward values are not passed to the analyzer.

## Safe default: inspect saved evidence

```sh
python3 -B run_study.py verify-saved
```

This checks saved hashes, classifications, independent predicate evaluations and aggregation. It does not request a model, execute a scoring function, or rerun the analyzer. Python standard library is sufficient. The relative layout of the preserved dependency files in `protocol/dependencies.json` must be retained.

## Exact execution sequence used for this study

```sh
python3 -B manage.py freeze
python3 -B run_study.py preflight
python3 -B manage.py rules
python3 -B manage.py request-all
python3 -B run_study.py compare
python3 -B run_study.py verify-saved
python3 -B manage.py preserve
```

These are an execution record, not commands to rerun over an existing freeze. Outputs are exclusive-create. The six-combination preflight is a mandatory gate; a failed gate stops the experiment. Requesting new responses consumes account resources and creates a different stochastic run. No prompt/rule/source adjustment or output-based retry is allowed. For an explicitly requested derived reproduction, work in a separate copy and preserve its input, response and result seals; never remove the originals to make a command rerun.

## Contents

- `data/`: exact programs, independently authored test descriptions, designed labels and provenance.
- `development/`: six rule-development descriptions and rule rationale. The rule author did not read the held-out descriptions; the description author did not read the rule implementation.
- `protocol/`: fixed prompt, schema, environment, expected matrix, witness inputs, dependency hashes and decision rules.
- `method-freeze.json`: binds all methodology files before the preflight and formal predictions.
- `audit/`: pre-model review, new harness/development tests, preflight, original-file preservation and final review.
- `results/extraction/`: complete individual prompts, raw model responses, event logs, metadata and unchanged accepted contracts, including failures.
- `model-response-freeze.json`: binds the single batch and the rule predictions before downstream comparison.
- `results/comparison/`: full static certificates, native reproduction records, independent obligation truth, paired outcomes and saved-artifact integrity records.

The model transport uses the existing Codex CLI service with user configuration ignored, an isolated ephemeral working directory, read-only sandbox, project documents disabled, and tool/action-event rejection. Exact model identity is recorded only if exposed; an unknown identity is not replaced with a guessed model name. Lexical quotation checks do not prove semantic entailment.

Fixed E/V/null conditions are assumed policies, not evidence-qualified extractors. Report both ordinary binary labels and whether a returned alarm actually violates the designed policy on its specific native witness. An alarm on a buggy program can still be unsupported if its particular witness violates only an invented obligation.
