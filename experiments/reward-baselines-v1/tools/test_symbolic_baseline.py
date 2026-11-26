"""Synthetic-only regressions; no dataset, oracle, or replay imports."""
import unittest

from symbolic_baseline import analyze


def unit(source, contract="C_BOOLEAN_FULL", helpers=(), bindings=None):
    return {
        "unit_id": "synthetic",
        "entry_name": "score",
        "source": source,
        "score_source": source,
        "helpers": list(helpers),
        "contract": {"id": contract, "candidate_arg": "answer", "reference_arg": "entry"},
        "stdlib_bindings": bindings or {},
    }


class SymbolicTests(unittest.TestCase):
    def verdict(self, source, expected, **kwargs):
        result = analyze(unit(source, **kwargs))
        self.assertEqual(result["verdict"], expected, result)
        if expected == "alarm":
            self.assertTrue(result["certificate"])
            self.assertTrue(result["source_spans"])
        if expected == "unknown":
            self.assertTrue(result["unsupported_reason"])
        return result

    def test_truthiness_counterexample(self):
        self.verdict('''def score(answer, entry):
    if answer is not None and bool(answer) == bool(entry["answer"]):
        return 1.0
    return 0
''', "alarm")

    def test_normalized_equality(self):
        self.verdict('''def score(answer, entry):
    if answer is not None and answer.strip().lower() == entry["answer"].strip().lower():
        return 1
    return 0
''', "no_alarm")

    def test_truthiness_behind_equality_is_safe(self):
        self.verdict('''def score(answer, entry):
    if answer is not None and answer.lower().strip() == entry["answer"].lower():
        if bool(answer) == bool(entry["answer"]):
            return 1
    return 0
''', "no_alarm")

    def test_dead_bad_return(self):
        self.verdict('''def score(answer, entry):
    if False:
        return 1
    if answer is None:
        if answer is not None:
            return 1
    return 0
''', "no_alarm")

    def test_assignments_and_unprotected_fallthrough(self):
        self.verdict('''def score(answer, entry):
    reward = 1.0
    if answer is not None and answer.strip().lower() == entry["answer"].lower():
        reward = 0.0
    return reward
''', "alarm")

    def test_assignments_and_partial_credit(self):
        self.verdict('''def score(answer, entry):
    reward = 0.5
    if answer is not None and answer.strip().lower() == entry["answer"].lower():
        reward = 1.0
    return reward
''', "no_alarm")

    def test_exception_handlers_are_not_ignored(self):
        self.verdict('''def score(answer, entry):
    try:
        answer = answer.strip().lower()
        if answer == entry["answer"].lower():
            return 1
    except Exception:
        return 1
    return 0
''', "unknown")

    def test_raise_expression_effects_are_not_skipped(self):
        for statement in ("raise entry.update({'answer': ''})",
                          "raise ValueError from entry.update({'answer': ''})"):
            with self.subTest(statement=statement):
                self.verdict('''def score(answer, entry):
    try:
        %s
    except Exception:
        if not bool(entry["answer"]):
            return 1
    return 0
''' % statement, "unknown")

    def test_effectful_exception_handler_type_is_unsupported(self):
        self.verdict('''def score(answer, entry):
    try:
        answer = answer.strip()
    except (entry.update({"answer": ""}) or Exception):
        if not bool(entry["answer"]):
            return 1
    return 0
''', "unknown")

    def test_shadowed_exception_handler_type_is_unproven(self):
        self.verdict('''def score(answer, entry, Exception):
    try:
        answer = answer.strip()
    except Exception:
        return 0
    if answer == entry["answer"]:
        return 1
    return 0
''', "unknown")

    def test_unknown_calls_and_mutations_cannot_prove_safety(self):
        for action in ('touch(entry)', 'entry["answer"] = answer'):
            self.verdict('''def score(answer, entry):
    %s
    if answer == entry["answer"]:
        return 1
    return 0
''' % action, "unknown")

    def test_short_circuit_dead_unknown_call(self):
        self.verdict('''def score(answer, entry):
    if False and unseen(entry):
        return 1
    return 0
''', "no_alarm")

    def test_loop_is_unsupported(self):
        self.verdict('''def score(answer, entry):
    for item in answer:
        if item:
            return 1
    return 0
''', "unknown")

    def test_intermediate_exception_is_not_a_normal_alarm_path(self):
        self.verdict('''def score(answer, entry):
    if answer is None:
        text = answer.strip()
        return 1
    return 0
''', "unknown")
        self.verdict('''def score(answer, entry):
    if answer is None and answer.strip() == answer.strip():
        return 1
    return 0
''', "unknown")

    def test_locally_shadowed_builtin_is_not_native(self):
        self.verdict('''def score(answer, entry):
    if bool(answer):
        return 1
    bool = None
    return 0
''', "unknown")

    def test_valueless_annotation_does_not_assign_none(self):
        self.verdict('''def score(answer, entry):
    value: int
    if value is None:
        return 1
    return 0
''', "unknown")

    def test_exception_target_shadows_builtin_for_whole_function(self):
        self.verdict('''def score(answer, entry):
    if bool(answer) == bool(entry["answer"]):
        return 1
    try:
        return 0
    except Exception as bool:
        return 0
''', "unknown")

    def test_later_unsupported_binding_surfaces_prevent_early_alarm(self):
        tails = [
            'import builtins as bool',
            'from builtins import bool',
            'global bool',
            'nonlocal bool',
            'def bool(value):\n        return value',
            'async def bool(value):\n        return value',
            'class bool:\n        pass',
            'del bool',
            'match answer:\n        case bool:\n            return 0',
            'match answer:\n        case [*bool]:\n            return 0',
            'match answer:\n        case {**bool}:\n            return 0',
        ]
        for tail in tails:
            with self.subTest(tail=tail):
                self.verdict('''def score(answer, entry):
    if bool(answer) == bool(entry["answer"]):
        return 1
    %s
    return 0
''' % tail, "unknown")

    def test_unknown_call_terms_do_not_prove_contradictions(self):
        self.verdict('''def score(answer, entry):
    if answer.startswith("b"):
        if not answer.startswith("a"):
            return 1
    return 0
''', "unknown")

    def test_reference_mutation_cannot_reuse_stale_facts(self):
        self.verdict('''def score(answer, entry):
    if answer != entry["answer"]:
        entry["answer"] = answer
        if answer == entry["answer"]:
            return 1
    return 0
''', "unknown")
        self.verdict('''def score(answer, entry):
    entry["answer"] = ""
    if not bool(entry["answer"]):
        return 1
    return 0
''', "unknown")

    def test_unknown_call_effects_stop_native_reference_reasoning(self):
        self.verdict('''def score(answer, entry):
    change(entry)
    if not bool(entry["answer"]):
        return 1
    return 0
''', "unknown")

    def test_undeclared_reference_state_cannot_establish_reachability(self):
        self.verdict('''def score(answer, entry):
    if entry["hidden"] != entry["hidden"]:
        return 1
    return 0
''', "unknown")

    def test_constant_helper_does_not_certify_equality(self):
        helper = {"name": "normalize", "source": 'def normalize(answer):\n    return []\n'}
        self.verdict('''def score(answer, entry):
    if normalize(answer) == normalize(entry["answer"]):
        return 1
    return 0
''', "unknown", helpers=[helper])

    def test_palindrome_dominating_guards(self):
        self.verdict('''def score(answer, entry):
    if answer is None:
        return 0
    text = answer.strip().lower()
    letters = entry["metadata"]["letters"]
    if text != text[::-1]:
        return .02
    if sorted(text) != sorted(letters):
        return .05
    return 1
''', "no_alarm", contract="C_PALINDROME_FULL")

    def test_palindrome_missing_guard_is_unknown(self):
        self.verdict('''def score(answer, entry):
    if answer is None:
        return 0
    text = answer.strip().lower()
    if sorted(text) == sorted(entry["metadata"]["letters"]):
        return 1
    return .02
''', "unknown", contract="C_PALINDROME_FULL")

    def test_prime_helper_source_certificate(self):
        helper = {"name": "parse", "source": '''def parse(self, text):
    if not text or text.strip() == "":
        return []
    return sorted([int(part.strip()) for part in text.split("×") if part.strip() != ""])
'''}
        source = '''def score(self, answer, entry):
    reward = 0
    if answer is not None:
        expected = self.parse(entry["answer"])
        actual = self.parse(answer)
        if expected == actual:
            reward = 1
        elif math.prod(expected) == math.prod(actual):
            reward = .5
        else:
            reward = .01
    return reward
'''
        self.verdict(source, "no_alarm", contract="C_PRIME_FACTORS_FULL", helpers=[helper], bindings={"math": "math"})
        helper["source"] = helper["source"].replace('int(part.strip())', 'int(part.strip()) % 2')
        self.verdict(source, "unknown", contract="C_PRIME_FACTORS_FULL", helpers=[helper], bindings={"math": "math"})

    def test_numeric_contract_not_claimed(self):
        self.verdict('''def score(answer, entry):
    if math.isfinite(0):
        return float(answer)
    return 0
''', "unknown", contract="C_COMPLEX_FINITE", bindings={"math": "math"})

    def test_identifier_and_unit_id_do_not_classify(self):
        source = 'def score(answer, entry):\n    return 1\n'
        a = unit(source)
        b = unit(source)
        b["unit_id"] = "arbitrary-unseen-repair-safe-name"
        self.assertEqual(analyze(a)["verdict"], analyze(b)["verdict"])


if __name__ == "__main__":
    unittest.main()
