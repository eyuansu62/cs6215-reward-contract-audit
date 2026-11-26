"""Synthetic development regressions only; no dataset/probe/oracle reads."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

import semgrep_baseline as baseline

DEVELOPMENT = baseline.ROOT / "development/semgrep"


def unit(source, contract_id="C_BOOLEAN_FULL", *, helpers=None, unit_id="synthetic"):
    contracts = json.loads((baseline.ROOT / "protocol/contracts.json").read_text())["contracts"]
    helpers = helpers or []
    return {"unit_id": unit_id, "entry_name": "score", "score_source": source,
            "source": source + "\n" + "\n".join(helper["source"] for helper in helpers),
            "helpers": helpers, "stdlib_bindings": {"math": "math"},
            "contract": {"id": contract_id, "candidate_arg": "answer", "reference_arg": "entry",
                         "full_credit_threshold": 1.0, **copy.deepcopy(contracts[contract_id])}}


class SemgrepSyntheticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline.find_core()
        DEVELOPMENT.mkdir(parents=True, exist_ok=True)

    def run_source(self, source, contract_id="C_BOOLEAN_FULL", **kwargs):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        result = baseline.run(unit(source, contract_id, **kwargs), output)
        self.assertEqual(json.loads((output / "result.json").read_text()), result)
        return result, output

    def assert_verdict(self, source, verdict, contract_id="C_BOOLEAN_FULL", **kwargs):
        result, output = self.run_source(source, contract_id, **kwargs)
        self.assertEqual(result["verdict"], verdict, result["errors"])
        return result, output

    def test_boolean_truthiness_warns(self):
        result, output = self.assert_verdict(
            'def score(answer, entry):\n    return 1.0 if bool(answer) == bool(entry["answer"]) else 0.0\n', "alarm")
        self.assertEqual(result["findings"][0]["rule_id"], "reward-bool-truthiness-equality")
        self.assertIn("engine", result)
        self.assertEqual(result["engine"]["sha256"], baseline.PINNED_CORE_SHA256)
        self.assertTrue((output / "scan-raw.json").is_file())
        self.assertTrue((output / "coverage-raw.json").is_file())
        self.assertEqual(result["coverage"]["return_count"], 1)

    def test_boolean_normalization_no_pattern(self):
        self.assert_verdict('def score(answer, entry):\n    return float(answer.strip().lower() == entry["answer"].strip().lower())\n', "no_alarm")

    def test_boolean_semantic_preguard_is_documented_false_positive(self):
        result, _ = self.assert_verdict(
            'def score(answer, entry):\n    if answer.strip().lower() != entry["answer"].strip().lower():\n        return 0.0\n    return float(bool(answer) == bool(entry["answer"]))\n', "alarm")
        self.assertIn("Boolean semantic preguards are not proved", result["qualification"])

    def test_numeric_unguarded_clamp_warns(self):
        self.assert_verdict('def score(answer, entry):\n    distance = abs(float(answer) - entry["value"])\n    score = min(1.0, math.exp(-distance))\n    return score\n', "alarm", "C_COMPLEX_FINITE")

    def test_numeric_adjacent_finite_guard_assignment(self):
        self.assert_verdict('def score(answer, entry):\n    distance = abs(float(answer) - entry["value"])\n    if not math.isfinite(distance):\n        return 0.0\n    score = min(1.0, math.exp(-distance))\n    return score\n', "no_alarm", "C_COMPLEX_FINITE")

    def test_numeric_adjacent_finite_guard_return(self):
        self.assert_verdict('def score(answer, entry):\n    distance = abs(float(answer) - entry["value"])\n    if not math.isfinite(distance):\n        return 0.0\n    return min(1.0, math.exp(-distance))\n', "no_alarm", "C_COMPLEX_FINITE")

    def test_numeric_positive_finite_branch(self):
        self.assert_verdict('def score(answer, entry):\n    distance = float(answer)\n    if math.isfinite(distance):\n        return min(1.0, math.exp(-distance))\n    return 0.0\n', "no_alarm", "C_COMPLEX_FINITE")

    def test_numeric_guard_reassignment_never_masks_warning(self):
        self.assert_verdict('def score(answer, entry):\n    distance = float(answer)\n    if not math.isfinite(distance):\n        return 0.0\n    distance = entry["other"]\n    return min(1.0, math.exp(-distance))\n', "alarm", "C_COMPLEX_FINITE")

    def test_numeric_guard_wrong_variable_never_masks_warning(self):
        self.assert_verdict('def score(answer, entry):\n    distance = float(answer)\n    if not math.isfinite(entry["value"]):\n        return 0.0\n    return min(1.0, math.exp(-distance))\n', "alarm", "C_COMPLEX_FINITE")

    def test_numeric_distant_guard_is_conservatively_warned(self):
        self.assert_verdict('def score(answer, entry):\n    distance = float(answer)\n    if not math.isfinite(distance):\n        return 0.0\n    unrelated = 3\n    return min(1.0, math.exp(-distance))\n', "alarm", "C_COMPLEX_FINITE")

    def test_numeric_repeated_call_guard_is_not_a_value_guard(self):
        self.assert_verdict('def score(answer, entry):\n    if not math.isfinite(entry["getter"]()):\n        return 0.0\n    return min(1.0, math.exp(-entry["getter"]()))\n', "alarm", "C_COMPLEX_FINITE")

    def test_prefix_min_length_ratio_warns(self):
        self.assert_verdict('def score(answer, entry):\n    matched = 0\n    reference = entry["answer"]\n    for a, b in zip(answer, reference):\n        if a == b:\n            matched += 1\n        else:\n            break\n    return matched / min(len(answer), len(reference))\n', "alarm", "C_PROBABILITY_FULL")

    def test_partial_reward_is_not_intrinsically_a_warning(self):
        source = 'def score(answer, entry):\n    if answer == entry["answer"]:\n        return 1.0\n    return 0.05\n'
        for contract_id in ("C_PROBABILITY_FULL", "C_PALINDROME_FULL", "C_PRIME_FACTORS_FULL"):
            with self.subTest(contract_id=contract_id):
                result, _ = self.assert_verdict(source, "no_alarm", contract_id)
                self.assertIn("No dedicated palindrome/multiset", result["qualification"])

    def test_identity_and_contract_do_not_choose_rules(self):
        source = 'def score(answer, entry):\n    return float(bool(answer) == bool(entry["answer"]))\n'
        first, one = self.assert_verdict(source, "alarm", unit_id="irrelevant-one")
        second, two = self.assert_verdict(source, "alarm", "C_PRIME_FACTORS_FULL", unit_id="different-label")
        self.assertEqual(first["findings"], second["findings"])
        self.assertEqual((one / "scan-rules.json").read_bytes(), (two / "scan-rules.json").read_bytes())
        self.assertTrue(all(r["mode"] == "search" for r in baseline.risky_rules()["rules"]))

    def test_helper_and_decorator_structural_coverage(self):
        helper = {"name": "parse", "source": '@staticmethod\ndef parse(value):\n    if value:\n        return float(value)\n    return\n'}
        result, _ = self.assert_verdict('def score(answer, entry):\n    return 0.5\n', "no_alarm", helpers=[helper])
        self.assertEqual(result["coverage"]["function_count"], 2)
        self.assertEqual(result["coverage"]["return_count"], 3)

    def test_unicode_source_preserved_and_spans_in_bytes(self):
        source = 'def score(answer, entry):\n    café = "雪"\n    return float(bool(answer) == bool(entry["answer"]))\n'
        result, output = self.assert_verdict(source, "alarm")
        exact = unit(source)["source"].encode()
        self.assertEqual((output / "source.py").read_bytes(), exact)
        self.assertEqual(result["source_sha256"], hashlib.sha256(exact).hexdigest())

    def test_empty_structural_coverage_is_unknown(self):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        with mock.patch.object(baseline, "_scan", return_value=([], [], "synthetic")):
            result = baseline.run(unit('def score(answer, entry):\n    return 0.0\n'), output)
        self.assertEqual(result["verdict"], "unknown")
        self.assertIn("structural coverage incomplete", result["errors"][0])

    def test_timeout_is_unknown(self):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        with mock.patch.object(baseline, "_scan", side_effect=subprocess.TimeoutExpired(["synthetic"], 1)):
            result = baseline.run(unit('def score(answer, entry):\n    return 0.0\n'), output)
        self.assertEqual(result["verdict"], "unknown")

    def test_parse_error_is_unknown(self):
        self.assert_verdict('def score(answer, entry):\n    return (\n', "unknown")

    def test_no_returns_is_unknown(self):
        self.assert_verdict('def score(answer, entry):\n    pass\n', "unknown")

    def test_metadata_mismatch_is_unknown(self):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        malformed = unit('def score(answer, entry):\n    return 0.0\n')
        malformed["helpers"] = [{"name": "helper", "source": "def helper(): return 1", "unexpected": True}]
        result = baseline.run(malformed, output)
        self.assertEqual(result["verdict"], "unknown")

    def test_rebound_math_namespace_is_unknown(self):
        self.assert_verdict('def score(answer, entry):\n    math = entry["namespace"]\n    distance = float(answer)\n    if not math.isfinite(distance):\n        return 0.0\n    return min(1.0, math.exp(-distance))\n', "unknown", "C_COMPLEX_FINITE")

    def test_rebound_builtin_is_unknown(self):
        self.assert_verdict('def score(answer, entry):\n    bool = entry["callable"]\n    return float(bool(answer) == bool(entry["answer"]))\n', "unknown")

    def test_frozen_contract_mismatch_is_unknown(self):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        altered = unit('def score(answer, entry):\n    return 0.0\n')
        altered["contract"]["full_credit_threshold"] = 0.1
        self.assertEqual(baseline.run(altered, output)["verdict"], "unknown")

    def test_unsupported_fixed_parameters_are_unknown(self):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        malformed = unit('def score(answer, entry):\n    return 0.0\n')
        malformed["fixed_parameters"] = {"answer": "forced candidate"}
        self.assertEqual(baseline.run(malformed, output)["verdict"], "unknown")

    def test_engine_parse_error_cannot_be_a_negative(self):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        source_path = output / "source.py"
        source_path.write_text('def score(answer, entry):\n    return 0.0\n')
        payload = {"version": baseline.PINNED_VERSION, "results": [],
                   "paths": {"scanned": [str(source_path)]},
                   "errors": [{"type": "PartialParsing", "message": "synthetic engine error"}]}
        with mock.patch.object(baseline, "_execute", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr="")):
            with self.assertRaisesRegex(ValueError, "errors"):
                baseline._scan(baseline.find_core(), baseline.coverage_rules(), source_path, output, "coverage")
        self.assertEqual(json.loads((output / "coverage-raw.json").read_text()), payload)

    def test_missing_scanned_file_cannot_be_a_negative(self):
        output = Path(tempfile.mkdtemp(prefix="synthetic-", dir=DEVELOPMENT))
        payload = {"version": baseline.PINNED_VERSION, "results": [], "paths": {"scanned": []}, "errors": []}
        with mock.patch.object(baseline, "_execute", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr="")):
            with self.assertRaisesRegex(ValueError, "exactly"):
                baseline._scan(baseline.find_core(), baseline.coverage_rules(), output / "source.py", output, "coverage")

    def test_existing_output_is_never_overwritten(self):
        result, output = self.run_source('def score(answer, entry):\n    return 0.0\n')
        before = (output / "result.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "empty"):
            baseline.run(unit('def score(answer, entry):\n    return 0.0\n'), output)
        self.assertEqual(before, (output / "result.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
