"""Input-only bridge to the unchanged reward-baselines-v1 analyzers.

Only the existing canonical Boolean necessary condition can be projected.
This module adds no Python semantics, source rewriting, reward execution,
specification inference, or rules. Unsupported projections remain Unknown.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT.parent / "reward-baselines-v1"
EXPECTED_BASELINE_FREEZE = "0925274a7d4b18780fabc611d75c03e0dc9066ef426781ca1a85a2b33edeb1de"
VERDICTS = {"alarm", "no_alarm", "unknown"}
SOURCE_FIELDS = (
    "entry_name", "source", "score_source", "helpers", "stdlib_bindings",
    "fixed_parameters",
)
QUALIFICATION = (
    "The projection checks only a necessary condition: agreement with a trusted "
    "canonical True/False reference after the preserved strip/lower normalization. "
    "It does not validate how the task is solved, all output-format requirements, "
    "or an inferred partial-credit policy. The normalization is a weakening for "
    "this necessary condition, not a claim that the question permits it. "
    "Unsupported task types are interface limits, not extraction errors. "
    "Semgrep no_alarm is a completed pattern scan, not a semantic proof."
)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _object_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def verify_frozen_baseline():
    """Verify the old freeze and exact code/protocol bytes without reading labels."""
    freeze_path = BASELINE / "method-freeze.json"
    if _sha(freeze_path) != EXPECTED_BASELINE_FREEZE:
        raise ValueError("Preserved baseline method-freeze SHA256 mismatch")
    freeze = _read(freeze_path)
    paths = [
        *BASELINE.glob("*.py"), *(BASELINE / "tools").glob("*.py"),
        *(BASELINE / "protocol").glob("*.json"), BASELINE / "tools/tool-release.json",
    ]
    actual = {str(path.relative_to(BASELINE)): _sha(path) for path in sorted(paths)}
    if actual != freeze["files_sha256"]:
        raise ValueError("Preserved baseline code/protocol bytes changed")
    for name, expected in freeze["inputs_sha256"].items():
        if _sha(BASELINE / name) != expected:
            raise ValueError("Preserved baseline frozen input changed: " + name)
    return {
        "method_freeze_sha256": EXPECTED_BASELINE_FREEZE,
        "files_sha256": actual,
        "analyzer_files_unchanged": True,
        "new_analyzer_semantics_or_rules": False,
    }


def _load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot import preserved analyzer: " + str(path))
    module = importlib.util.module_from_spec(spec)
    # dataclasses in the preserved symbolic module resolve their module here.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_analyzers():
    semgrep = _load_file("_reward_preserved_semgrep_v1", BASELINE / "tools/semgrep_baseline.py")
    symbolic = _load_file("_reward_preserved_symbolic_v1", BASELINE / "tools/symbolic_baseline.py")
    rules_bytes = (json.dumps(semgrep.risky_rules(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    coverage_bytes = (json.dumps(semgrep.coverage_rules(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    metadata = {
        "semgrep_module_path": str(Path(semgrep.__file__).resolve()),
        "symbolic_module_path": str(Path(symbolic.__file__).resolve()),
        "semgrep_code_sha256": _sha(semgrep.__file__),
        "symbolic_code_sha256": _sha(symbolic.__file__),
        "risky_rules_sha256": hashlib.sha256(rules_bytes).hexdigest(),
        "coverage_rules_sha256": hashlib.sha256(coverage_bytes).hexdigest(),
        "engine_expected_sha256": semgrep.PINNED_CORE_SHA256,
        "semgrep_version": semgrep.PINNED_VERSION,
    }
    return semgrep.run, symbolic.analyze, metadata


def project_contract(unit, contract):
    """Project structured type/tokens only; never interpret free-text semantics."""
    if not isinstance(contract, dict):
        return None, "missing_contract"
    if contract.get("status") != "extracted":
        return None, "contract_abstained_or_invalid_status"
    if contract.get("answer_kind") != "boolean":
        return None, "projection_unsupported_answer_kind"
    if contract.get("boolean_tokens") != {"true": "True", "false": "False"}:
        return None, "projection_unsupported_boolean_tokens"
    if unit.get("trusted_reference_canonical_boolean") is not True:
        return None, "canonical_boolean_reference_not_established_by_source_preparation"
    if any(field not in unit for field in SOURCE_FIELDS):
        return None, "source_preparation_missing_required_fields"
    if (not isinstance(unit["entry_name"], str)
            or not isinstance(unit["source"], str) or not isinstance(unit["score_source"], str)
            or not isinstance(unit["helpers"], list)
            or not isinstance(unit["stdlib_bindings"], dict)
            or not isinstance(unit["fixed_parameters"], dict)):
        return None, "source_preparation_invalid_field_types"
    clauses = _read(BASELINE / "protocol/contracts.json")["contracts"]["C_BOOLEAN_FULL"]
    projected = {
        "id": "C_BOOLEAN_FULL", "candidate_arg": "answer", "reference_arg": "entry",
        "full_credit_threshold": 1.0, **clauses,
    }
    return projected, None


def _unknown(reason, **extra):
    return {"verdict": "unknown", "reason": reason, "source_executed": False, **extra}


def run_condition(units, contracts, output_dir):
    """Run one caller-labelled contract condition using exactly preserved code.

    Condition origin belongs to the caller/output directory and never enters
    either detector input. Inputs are copied independently for each analyzer.
    Output directories are append-only; existing directories are never reused.
    """
    if not isinstance(units, list) or not isinstance(contracts, list):
        raise ValueError("units and contracts must be lists")
    unit_ids = [unit.get("task_id") if isinstance(unit, dict) else None for unit in units]
    if any(not isinstance(task, str) or not task for task in unit_ids) or len(set(unit_ids)) != len(unit_ids):
        raise ValueError("Source units require unique nonempty task_id values")
    contract_ids = [contract.get("task_id") if isinstance(contract, dict) else None for contract in contracts]
    if any(not isinstance(task, str) or not task for task in contract_ids) or len(set(contract_ids)) != len(contract_ids):
        raise ValueError("Contracts require unique nonempty task_id values")
    if not set(contract_ids) <= set(unit_ids):
        raise ValueError("Contract task_id is not in source units")
    output = Path(output_dir).resolve()
    if output.exists():
        raise ValueError("Preserve existing condition output; choose a new directory")
    before = verify_frozen_baseline()
    contracts_by_id = dict(zip(contract_ids, contracts))
    input_sha = _object_sha(units)
    contracts_sha = _object_sha(contracts)
    output.mkdir(parents=True)
    analyzers = None
    analyzer_metadata = None
    rows = []
    for index, unit in enumerate(units):
        task_id = unit["task_id"]
        contract = contracts_by_id.get(task_id)
        projected, reason = project_contract(unit, contract)
        projection = {
            "supported": projected is not None, "reason": reason,
            "contract_id": projected["id"] if projected is not None else None,
            "qualification": QUALIFICATION,
        }
        row = {"task_id": task_id, "projection": projection, "methods": {}}
        if projected is None:
            for name in ("semgrep", "symbolic"):
                row["methods"][name] = _unknown(reason, status="projection_unsupported")
        else:
            if analyzers is None:
                semgrep, symbolic, analyzer_metadata = _load_analyzers()
                analyzers = (("semgrep", semgrep), ("symbolic", symbolic))
            detector_input = {field: copy.deepcopy(unit[field]) for field in SOURCE_FIELDS}
            detector_input["contract"] = projected
            detector_input["unit_id"] = _object_sha(detector_input)
            row["detector_input_sha256"] = _object_sha(detector_input)
            row["unit_id"] = detector_input["unit_id"]
            row["source_sha256"] = hashlib.sha256(unit["source"].encode("utf-8")).hexdigest()
            for name, function in analyzers:
                # Different task families may inherit identical scorer source.
                # Keep each invocation separate without changing detector IDs.
                destination = output / "raw" / (str(index) + "-" + detector_input["unit_id"]) / name
                started = time.perf_counter()
                try:
                    if name == "semgrep":
                        result = function(copy.deepcopy(detector_input), destination)
                    else:
                        result = function(copy.deepcopy(detector_input))
                    if not isinstance(result, dict) or result.get("verdict") not in VERDICTS:
                        raise ValueError("Preserved analyzer returned invalid verdict")
                except Exception as error:
                    result = _unknown("analyzer_execution_failed", unexpected_error=type(error).__name__ + ": " + str(error))
                result["bridge_wall_seconds"] = round(time.perf_counter() - started, 6)
                row["methods"][name] = result
                _write(destination / "bridge-record.json", result)
        rows.append(row)
    after = verify_frozen_baseline()
    if before != after:
        raise ValueError("Preserved baseline changed during condition run")
    if _object_sha(units) != input_sha or _object_sha(contracts) != contracts_sha:
        raise ValueError("Caller-owned source units or contracts were mutated")
    result = {
        "status": "complete", "bridge_sha256": _sha(__file__),
        "preserved_baseline": before, "imported_analyzers": analyzer_metadata,
        "source_units_sha256": input_sha, "contracts_sha256": contracts_sha,
        "condition_output": str(output), "contract_origin_passed_to_detectors": False,
        "qualification": QUALIFICATION, "cases": rows,
        "summary": {
            "tasks": len(rows), "supported_projections": sum(row["projection"]["supported"] for row in rows),
            "verdict_counts": {name: {verdict: sum(row["methods"][name]["verdict"] == verdict for row in rows)
                                      for verdict in sorted(VERDICTS)} for name in ("semgrep", "symbolic")},
        },
        "target_scorers_executed": False, "LLM_called_by_downstream": False,
        "labels_read_by_downstream": False,
    }
    _write(output / "predictions.json", result)
    return result
