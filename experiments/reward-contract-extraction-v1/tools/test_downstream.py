"""Synthetic bridge checks only; no new task scorer/model/reference is read."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import downstream


def unit(task="synthetic"):
    source = "def score_answer(self, answer, entry):\n    if answer is not None and bool(answer) == bool(entry['answer']):\n        return 1.0\n    return 0.0\n"
    return {"task_id": task, "entry_name": "score_answer", "source": source,
            "score_source": source, "helpers": [], "stdlib_bindings": {},
            "fixed_parameters": {}, "trusted_reference_canonical_boolean": True}


def contract(task="synthetic"):
    return {"task_id": task, "status": "extracted", "answer_kind": "boolean",
            "boolean_tokens": {"true": "True", "false": "False"}}


class DownstreamTests(unittest.TestCase):
    def test_projection_is_exact_preserved_necessary_condition(self):
        projected, reason = downstream.project_contract(unit(), contract())
        self.assertIsNone(reason)
        clauses = json.loads((downstream.BASELINE / "protocol/contracts.json").read_text())["contracts"]["C_BOOLEAN_FULL"]
        self.assertEqual(projected, {"id": "C_BOOLEAN_FULL", "candidate_arg": "answer",
                                    "reference_arg": "entry", "full_credit_threshold": 1.0, **clauses})
        self.assertIn("weakening", downstream.QUALIFICATION)

    def test_nonboolean_types_are_unknown_without_analyzer_call(self):
        for kind in ("fraction", "list", "integer", "unspecified"):
            c = contract(); c["answer_kind"] = kind
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                with patch.object(downstream, "_load_analyzers", side_effect=AssertionError("must not load")):
                    result = downstream.run_condition([unit()], [c], Path(tmp)/"run")
                self.assertEqual(result["summary"]["supported_projections"], 0)
                for method in result["cases"][0]["methods"].values():
                    self.assertEqual(method["verdict"], "unknown")
                    self.assertEqual(method["reason"], "projection_unsupported_answer_kind")

    def test_incompatible_tokens_abstention_and_reference_gate(self):
        bad_tokens = contract(); bad_tokens["boolean_tokens"] = {"true": "Yes", "false": "No"}
        self.assertEqual(downstream.project_contract(unit(), bad_tokens)[1], "projection_unsupported_boolean_tokens")
        abstained = contract(); abstained["status"] = "abstain"
        self.assertEqual(downstream.project_contract(unit(), abstained)[1], "contract_abstained_or_invalid_status")
        for flag in (False, None, "true", 1):
            u = unit(); u["trusted_reference_canonical_boolean"] = flag
            self.assertEqual(downstream.project_contract(u, contract())[1], "canonical_boolean_reference_not_established_by_source_preparation")

    def test_missing_contract_or_source_metadata_is_unknown(self):
        self.assertEqual(downstream.project_contract(unit(), None)[1], "missing_contract")
        incomplete = unit(); del incomplete["helpers"]
        self.assertEqual(downstream.project_contract(incomplete, contract())[1], "source_preparation_missing_required_fields")
        malformed = unit(); malformed["source"] = None
        self.assertEqual(downstream.project_contract(malformed, contract())[1], "source_preparation_invalid_field_types")

    def test_input_parity_isolated_copies_and_forbidden_field_stripping(self):
        seen = []
        def semgrep(value, output):
            seen.append(copy.deepcopy(value))
            value["source"] = "mutated by first method"
            return {"verdict": "alarm"}
        def symbolic(value):
            seen.append(copy.deepcopy(value))
            return {"verdict": "alarm"}
        u = unit(); u.update(expected_violation=True, model_status="proposed", issue_url="unseen", contract_origin="LLM")
        original = copy.deepcopy(u)
        with tempfile.TemporaryDirectory() as tmp, patch.object(downstream, "_load_analyzers", return_value=(semgrep, symbolic, {})):
            result = downstream.run_condition([u], [contract()], Path(tmp)/"run")
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(set(seen[0]), set(downstream.SOURCE_FIELDS) | {"contract", "unit_id"})
        self.assertEqual(u, original)
        self.assertFalse(result["contract_origin_passed_to_detectors"])

    def test_task_ids_and_free_text_do_not_classify_or_reach_detectors(self):
        def semgrep(value, output): return {"verdict": "no_alarm", "input": value}
        def symbolic(value): return {"verdict": "no_alarm", "input": value}
        results = []
        for task in ("synthetic", "known-bug-original"):
            c = contract(task); c["full_credit_requirements"] = ["arbitrary different prose " + task]
            with tempfile.TemporaryDirectory() as tmp, patch.object(downstream, "_load_analyzers", return_value=(semgrep, symbolic, {})):
                results.append(downstream.run_condition([unit(task)], [c], Path(tmp)/"run"))
        left, right = [r["cases"][0] for r in results]
        self.assertEqual(left["detector_input_sha256"], right["detector_input_sha256"])
        self.assertEqual(left["methods"]["symbolic"]["input"], right["methods"]["symbolic"]["input"])

    def test_analyzer_exception_and_invalid_verdict_remain_unknown(self):
        def semgrep(value, output): raise RuntimeError("synthetic transport failure")
        def symbolic(value): return {"verdict": "invalid"}
        with tempfile.TemporaryDirectory() as tmp, patch.object(downstream, "_load_analyzers", return_value=(semgrep, symbolic, {})):
            result = downstream.run_condition([unit()], [contract()], Path(tmp)/"run")
        methods = result["cases"][0]["methods"]
        self.assertEqual({m["verdict"] for m in methods.values()}, {"unknown"})
        self.assertIn("RuntimeError", methods["semgrep"]["unexpected_error"])
        self.assertIn("invalid verdict", methods["symbolic"]["unexpected_error"])

    def test_ambiguous_task_sets_and_existing_outputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp)/"existing"; existing.mkdir()
            with self.assertRaisesRegex(ValueError, "Preserve existing"):
                downstream.run_condition([unit()], [contract()], existing)
            with self.assertRaisesRegex(ValueError, "unique"):
                downstream.run_condition([unit(), unit()], [contract()], Path(tmp)/"duplicate")
            with self.assertRaisesRegex(ValueError, "unique"):
                downstream.run_condition([unit()], [contract(), contract()], Path(tmp)/"duplicate-contract")
            with self.assertRaisesRegex(ValueError, "not in source"):
                downstream.run_condition([unit()], [contract("other")], Path(tmp)/"extra-contract")

    def test_old_baseline_hashes_and_generated_rules_stay_pinned(self):
        before = downstream.verify_frozen_baseline()
        self.assertEqual(before["method_freeze_sha256"], downstream.EXPECTED_BASELINE_FREEZE)
        _, _, meta = downstream._load_analyzers()
        self.assertEqual(meta["semgrep_code_sha256"], before["files_sha256"]["tools/semgrep_baseline.py"])
        self.assertEqual(meta["symbolic_code_sha256"], before["files_sha256"]["tools/symbolic_baseline.py"])
        self.assertEqual(meta["risky_rules_sha256"], "7db489abf43d2fd01f44895bfba30358d300853c9fc5d2b0e65073143d244361")
        self.assertEqual(before, downstream.verify_frozen_baseline())

    def test_integrity_mismatch_fails_before_any_run(self):
        with patch.object(downstream, "EXPECTED_BASELINE_FREEZE", "0"*64):
            with self.assertRaisesRegex(ValueError, "method-freeze SHA256 mismatch"):
                downstream.verify_frozen_baseline()

    def test_exact_preserved_analyzers_on_identical_synthetic_boolean_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = downstream.run_condition([unit("A"), unit("B")], [contract("A"), contract("B")], Path(tmp)/"run")
        self.assertEqual(result["summary"]["supported_projections"], 2)
        self.assertEqual(result["cases"][0]["unit_id"], result["cases"][1]["unit_id"])
        for row in result["cases"]:
            self.assertEqual({m["verdict"] for m in row["methods"].values()}, {"alarm"})
        self.assertTrue(result["preserved_baseline"]["analyzer_files_unchanged"])
        self.assertFalse(result["labels_read_by_downstream"])


if __name__ == "__main__":
    unittest.main()
