# Controlled scoring-policy descriptions: provenance and limits

These are **researcher-authored synthetic scoring-policy controls**. They are not real upstream task contracts, extracted benchmark descriptions, or independent real programs. The set contains 12 descriptions: four linguistic families crossed once with three intended semantic classes. The family names describe presentation choices, not separate application domains.

## Authorship and isolation

The assigned description author wrote all descriptions directly for this controlled experiment. No external fetching, additional model calls, analyzer runs, scorer runs, or model-output inspection were used. The author did not read the new rule extractor, development material, or results. Wording was chosen for natural, explicit policy meaning rather than to exploit or evade particular implementation patterns.

The task identifiers are opaque bookkeeping identifiers. The initial 12-card list was shuffled once using Python `random.Random(731109).shuffle`, and that fixed order is used in both JSON files. The identifiers do not encode class or family. The cards and labels are frozen at handoff; downstream observations must not be used to revise this held-out set.

## Intended comparison

| Intended class | Full-credit policy | Expected available obligation |
| --- | --- | --- |
| E | Entire normalized response must equal the trusted correct canonical Boolean reference. | `equals_reference` |
| V | Entire normalized response must be either Boolean token; either label earns full credit independently of the reference. | `valid_boolean_token` |
| U | Unrestricted text or natural prose explicitly earns full credit. | None; abstain as `not_expressible` |

Equality entails Boolean-token validity under the supplied reference domain, so an E-plus-V interpretation belongs to E. U is established by affirmative permission for prose or arbitrary text, not by silence about formatting or correctness. Every label includes evidence quoted verbatim from its card, an intended-semantics rationale, and an ambiguity audit.

## Common analysis environment

The candidate domain is a native string or `None`. The reference is a trusted correct canonical `True` or `False` label. Normalization is outer-whitespace stripping followed by lowercasing. Full credit means meeting threshold 1. These are fixed experiment assumptions, not facts that an extractor must infer from a card. The cards do not add an independent policy for the `None` case; the target distinctions are demonstrated by ordinary string candidates.

Only each card's `question_description` is policy input. Its opaque `task_id` is also sent solely as an administrative identifier required by the unchanged response schema; `placeholder_notes` is empty and the same fixed analysis profile is supplied to both extractors. Test-set names, filenames, family names, semantic classes, expected obligations, rationales, evidence quotes, ambiguity audits, and this provenance are excluded from model input. This input-boundary clarification was made before the method freeze and all experimental predictions; no card wording or label changed.

## What the labels do and do not establish

The labels record the author's intended reading of explicit natural-English policies. They are not machine-proved semantic implication gold, and they do not establish a formal soundness theorem from prose. The ambiguity audits document how the text addresses whole-response scope, normalization, reference correctness, or affirmative permission; they are not independent validation.

The 12 observations vary wording across three semantic conditions. They must not be described as 12 independent real reward programs, as evidence of upstream-contract coverage, or as a population sample of naturally occurring descriptions. Any result supports only a bounded claim about this controlled policy set. Results and authoring provenance should remain separate.
