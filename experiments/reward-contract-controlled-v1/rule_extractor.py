"""Frozen, deterministic English-policy extractor; no analyzer or model access.

The deliberately bounded language rules are documented in development/rule-design.md.
Only question_description is policy text. Bindings are experiment assumptions.
"""

from __future__ import annotations

import re
from copy import deepcopy


DEFAULT_PROFILE = {
    "schema": "boolean-obligations-v1",
    "candidate_arg": "answer",
    "reference_arg": "entry",
    "reference_key": "answer",
    "candidate_domain": "native_str_or_none",
    "trusted_reference": "canonical_True_False",
    "normalization": ["strip", "lower"],
    "full_credit_threshold": 1.0,
}

_OUTPUT = r"(?:answer|response|output|submission|label|token|prediction)"
_EMIT = r"(?:return|respond|reply|answer|output|submit|provide|write|give|emit|produce|choose|select)"
_REFERENCE = (
    r"(?:trusted\s+reference(?:\s+answer)?|reference(?:\s+(?:answer|label))?|"
    r"ground\s+truth|answer\s+key|gold(?:\s+(?:answer|label))?|"
    r"expected\s+(?:answer|label)|canonical\s+(?:answer|label))"
)
_BOOLEAN = re.compile(
    r"\bboolean\b|\btrue\s*(?:or|and|/|,|\|)\s*false\b|"
    r"\bfalse\s*(?:or|and|/|,|\|)\s*true\b"
)
_REQUIRED = re.compile(
    r"\b(?:must|shall|should|requires?|required|needs? to|has to|only if|"
    r"provided that|full credit|maximum (?:score|reward)|score of 1)\b"
)
_NEGATED_BEFORE = re.compile(
    r"\b(?:no|not|never|no longer|don't|doesn't|isn't|aren't|needn't)\s+"
    r"(?:(?:be|have|to|required|necessarily|need|needs|considered|a|the)\s+){0,4}$"
    r"|\bno need to\s*$"
)
_PERMITTED_BEFORE = re.compile(r"\b(?:may|can|could|optionally|allowed to|permitted to)\s+$")
_NEGATED_REQUIREMENT = re.compile(
    r"\b(?:do not|does not|must not|should not|never|doesn't|don't)\s+"
    r"(?:require|enforce|check|demand)\s+(?:that\s+)?(?:the\s+)?$"
)
_OPTIONAL_AFTER = re.compile(
    r"^\s*(?:(?:is|are)\s+)?(?:optional|not (?:required|necessary|checked|graded|scored))\b"
)

# Each candidate pattern identifies its predicate, so negation is local to it.
_REFERENCE_MATCH = re.compile(
    rf"\b{_OUTPUT}\b.{{0,65}}?\b(?P<predicate>match(?:es)?|equals?|agrees? with|"
    rf"is identical to|is the same as)\b.{{0,65}}?\b{_REFERENCE}\b"
)
_CORRECT_EMIT = re.compile(
    rf"\b(?P<predicate>{_EMIT})\b.{{0,45}}?\b(?:correct|accurate)\b"
    rf".{{0,45}}?\b(?:{_OUTPUT}|true|false|boolean)\b"
)
_CORRECT_REQUIRED = re.compile(
    rf"\b{_OUTPUT}\b.{{0,45}}?\b(?:must|shall|should|needs? to|has to)\b"
    r".{0,20}?\b(?P<predicate>(?:be\s+)?(?:correct|accurate))\b"
)
_CORRECT_CREDIT = re.compile(
    r"\b(?:full credit|maximum (?:score|reward))\b.{0,20}?"
    r"(?:only if|requires?)\s+.{0,45}?\b(?P<predicate>correct|accurate)\b"
)
_FORMAT_EMIT = re.compile(
    rf"\b(?P<predicate>{_EMIT})\b.{{0,65}}?\b(?:only|exactly|just|single|one)\b"
)
_FORMAT_REQUIRED = re.compile(
    rf"\b{_OUTPUT}\b.{{0,35}}?\b(?:must|shall|should|needs? to|has to)\s+"
    r"(?P<predicate>(?:be|contain|consist of))\b.{0,35}?\b(?:only|exactly|single|one|valid)\b"
)
_BARE_FORMAT = re.compile(
    rf"^\s*(?:please\s+)?(?P<predicate>{_EMIT})\s+(?:with\s+)?"
    r"(?:either\s+)?(?:true\s*(?:or|/)\s*false|false\s*(?:or|/)\s*true)"
    r"\s*[.!?;]?\s*$"
)
_NAMED_FORMAT_REQUIRED = re.compile(
    rf"\b{_OUTPUT}\b.{{0,30}}?\b(?:must|shall|should|needs? to|has to)\s+"
    r"(?P<predicate>be)\s+(?:(?:a|one|single|valid)\s+)?"
    r"(?:boolean\s+token|true\s*(?:or|/)\s*false|false\s*(?:or|/)\s*true)\b"
)
_FORMAT_ONLY = re.compile(
    r"\b(?P<predicate>correctness|accuracy)\s+(?:is\s+)?"
    r"(?:irrelevant|ignored|not (?:required|checked|graded|scored|evaluated))\b|"
    r"\b(?P<irrelevant>correctness|accuracy)\s+(?:does not|doesn't)\s+"
    r"(?:matter|affect\s+(?:the\s+)?(?:score|reward|grade))\b|"
    r"\b(?:grade|score|reward|credit)\b.{0,35}?"
    r"(?P<exclusive>(?:depends?\s+)?(?:only|solely|exclusively))\s+(?:on\s+)?"
    r"(?:the\s+)?(?:format|syntax|token validity)\b|"
    r"\b(?:grade|score|reward|credit)\b.{0,30}?"
    r"(?P<format>format|syntax)\s+only\b"
)
_STRUCTURED = re.compile(
    rf"\b(?P<predicate>{_EMIT})\b.{{0,45}}?\b(?:json\s+(?:object|array)|"
    r"dictionary|xml|paragraph|essay|prose|explanation|python\s+(?:bool|boolean))\b"
)
_EXPLANATION = re.compile(r"\b(?P<predicate>explain)\s+(?:your|the)\s+(?:reasoning|answer)\b")
_APPENDED_EXPLANATION = re.compile(
    rf"\b(?P<predicate>{_EMIT})\b.{{0,70}}?\b(?:with|and include|followed by)\s+"
    r"(?:a\s+|an\s+|the\s+)?(?:short\s+|brief\s+)?explanation\b"
)


def _clauses(description):
    """Keep exact source spans for evidence; normalization is analysis-only."""
    for match in re.finditer(r"[^.!?;\n]+(?:[.!?;]|$)", description):
        quote = match.group().strip()
        if quote:
            text = quote.lower().translate(str.maketrans({"“": '"', "”": '"', "’": "'", "–": "-", "—": "-"}))
            text = re.sub(r"[`\"]", "", text)
            text = re.sub(r"'(true|false)'", r"\1", text)
            yield quote, text


def _positive_match(text, pattern):
    for match in pattern.finditer(text):
        predicate = match.start("predicate")
        before = text[max(0, predicate - 65):predicate]
        if _NEGATED_BEFORE.search(before) or _PERMITTED_BEFORE.search(before):
            continue
        if _NEGATED_REQUIREMENT.search(text[max(0, match.start() - 65):match.start()]):
            continue
        # Negation inside a bounded subject-to-predicate span also matters.
        leading = text[match.start():predicate]
        if re.search(r"\b(?:not required|need not|must not|should not|shall not|do not|does not)\b", leading):
            continue
        if _OPTIONAL_AFTER.search(text[match.end():]):
            continue
        yield match


def _format_override(text):
    for match in _FORMAT_ONLY.finditer(text):
        start = next(match.start(name) for name in ("predicate", "irrelevant", "exclusive", "format") if match.group(name) is not None)
        if not _NEGATED_BEFORE.search(text[max(0, start - 65):start]):
            return True
    return False


def extract(task, profile=None):
    """Return the six-field raw response, using no execution or external calls.

    An optional profile must retain the experiment's fixed bindings. Additional
    metadata such as the profile's explanatory note is never put in the contract.
    Unrecognized English is an abstention, not a guessed semantic requirement.
    """
    if not isinstance(task, dict) or not isinstance(task.get("task_id"), str):
        raise ValueError("task_id must be a string")
    description = task.get("question_description")
    if not isinstance(description, str):
        raise ValueError("question_description must be a string")
    source_profile = DEFAULT_PROFILE if profile is None else profile
    if any(source_profile.get(key) != value for key, value in DEFAULT_PROFILE.items()):
        raise ValueError("profile must preserve the fixed experiment bindings")

    clauses = list(_clauses(description))
    boolean_context = any(_BOOLEAN.search(text) for _, text in clauses)
    format_only = any(_format_override(text) for _, text in clauses)
    equality_quote = None
    validity_quote = None
    out_of_scope = False

    for quote, text in clauses:
        if any(any(_positive_match(text, pattern)) for pattern in (_STRUCTURED, _EXPLANATION, _APPENDED_EXPLANATION)):
            out_of_scope = True
        # Equality is warranted by a normative reference comparison, or a
        # correctness requirement in an explicitly Boolean task.
        reference_matches = list(_positive_match(text, _REFERENCE_MATCH))
        reference_required = _REQUIRED.search(text) or re.match(rf"\s*{_EMIT}\b", text)
        correct = boolean_context and (
            any(_positive_match(text, _CORRECT_EMIT))
            or any(_positive_match(text, _CORRECT_REQUIRED))
            or any(_positive_match(text, _CORRECT_CREDIT))
        )
        if equality_quote is None and ((reference_matches and reference_required) or correct):
            equality_quote = quote
        if _BOOLEAN.search(text) and validity_quote is None:
            if any(any(_positive_match(text, pattern)) for pattern in (_FORMAT_EMIT, _FORMAT_REQUIRED, _BARE_FORMAT, _NAMED_FORMAT_REQUIRED)):
                validity_quote = quote

    if format_only:
        equality_quote = None
    response = {
        "task_id": task["task_id"],
        "status": "abstain",
        "contract": None,
        "evidence": [],
        "not_specified": ["valid_boolean_token", "equals_reference"],
        "abstention_reason": None,
    }
    if out_of_scope:
        response["abstention_reason"] = "The requested output includes prose or a structured/native non-string representation outside this Boolean-token contract language."
        return response
    if equality_quote is None and validity_quote is None:
        response["abstention_reason"] = "No affirmative supported requirement for a native Boolean token or equality to the trusted reference was recognized."
        return response

    obligations = ["valid_boolean_token"]
    evidence = [{
        "obligation_id": "valid_boolean_token",
        "quote": validity_quote or equality_quote,
        "reason": "The policy restricts the submitted response to a Boolean token." if validity_quote else "Equality to the fixed canonical True/False reference entails Boolean-token validity after the supplied normalization.",
    }]
    if equality_quote:
        obligations.append("equals_reference")
        evidence.append({
            "obligation_id": "equals_reference",
            "quote": equality_quote,
            "reason": "The policy requires reference agreement or the correct Boolean label; the fixed profile binds correctness to the trusted canonical reference.",
        })
    contract = {key: deepcopy(source_profile[key]) for key in DEFAULT_PROFILE}
    contract["obligations"] = obligations
    response.update({
        "status": "extracted",
        "contract": contract,
        "evidence": evidence,
        "not_specified": [] if equality_quote else ["equals_reference"],
    })
    return response
