"""Development-only checks: exactly six authored descriptions, no held-out reads."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("controlled_rule_extractor", ROOT / "rule_extractor.py")
RULES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RULES)
CARDS = json.loads((ROOT / "development" / "dev-cards.json").read_text())["tasks"]


class DevelopmentRulesTest(unittest.TestCase):
    def test_six_balanced_authored_cards(self):
        self.assertEqual(len(CARDS), 6)
        self.assertEqual(len({card["task_id"] for card in CARDS}), 6)
        self.assertEqual(sorted(card["expected_label"] for card in CARDS), ["E", "E", "U", "U", "V", "V"])

    def test_development_labels_and_raw_response_shape(self):
        for card in CARDS:
            with self.subTest(task=card["task_id"]):
                response = RULES.extract(card)
                self.assertEqual(set(response), {"task_id", "status", "contract", "evidence", "not_specified", "abstention_reason"})
                self.assertEqual(response["task_id"], card["task_id"])
                if card["expected_label"] == "U":
                    self.assertEqual(response["status"], "abstain")
                    self.assertIsNone(response["contract"])
                    self.assertEqual(response["evidence"], [])
                    self.assertTrue(response["abstention_reason"])
                    continue
                self.assertEqual(response["status"], "extracted")
                self.assertIsNone(response["abstention_reason"])
                expected = ["valid_boolean_token", "equals_reference"] if card["expected_label"] == "E" else ["valid_boolean_token"]
                self.assertEqual(response["contract"]["obligations"], expected)
                self.assertEqual(set(response["contract"]), set(RULES.DEFAULT_PROFILE) | {"obligations"})
                self.assertEqual([item["obligation_id"] for item in response["evidence"]], expected)
                for item in response["evidence"]:
                    self.assertEqual(set(item), {"obligation_id", "quote", "reason"})
                    self.assertTrue(item["quote"])
                    self.assertIn(item["quote"], card["question_description"])
                    self.assertTrue(item["reason"])

    def test_determinism_and_input_immutability(self):
        cards_before = deepcopy(CARDS)
        profile = deepcopy(RULES.DEFAULT_PROFILE)
        profile["note"] = "Metadata is excluded from contracts."
        profile_before = deepcopy(profile)
        for card in CARDS:
            first = RULES.extract(card, profile)
            self.assertEqual(first, RULES.extract(card, profile))
            if first["contract"] is not None:
                first["contract"]["normalization"].append("changed only in result")
        self.assertEqual(CARDS, cards_before)
        self.assertEqual(profile, profile_before)

    def test_documented_source_hash(self):
        digest = hashlib.sha256((ROOT / "rule_extractor.py").read_bytes()).hexdigest()
        design = (ROOT / "development" / "rule-design.md").read_text()
        self.assertIn(digest, design)


if __name__ == "__main__":
    unittest.main()
