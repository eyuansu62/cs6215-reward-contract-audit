#!/usr/bin/env python3
"""Check the public export and recompute archived results (Python 3.11+)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "reproducibility/public-manifest.json"
CONTROLLED = "experiments/reward-contract-controlled-v1"
COMPARISON = f"{CONTROLLED}/results/comparison"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def verify_bytes():
    files = read(MANIFEST)["files_sha256"]
    if not isinstance(files, dict) or not files:
        raise ValueError("Public manifest has no file inventory")
    for name, expected in files.items():
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or str(relative) != name
            or any(part in ("..", ".git") for part in relative.parts)
            or name == MANIFEST
        ):
            raise ValueError(f"Invalid public manifest path: {name}")
        path = ROOT / name
        if not path.is_file() or path.resolve() != path:
            raise ValueError(f"Missing or redirected manifest file: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Public file hash differs: {name}")
    return files


def load_saved_module(name, filename, files):
    if filename not in files:
        raise ValueError(f"Saved verifier is missing from the manifest: {filename}")
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load saved verifier: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_results(files):
    # Call only the read-only aggregators. The original command-line entry
    # points use the private archive's freeze manifests for their byte checks.
    sys.dont_write_bytecode = True
    legacy = load_saved_module("public_legacy_results", "reproducibility/verify_saved.py", files)
    combined = load_saved_module("public_combined_results", "reproducibility/verify_all_saved.py", files)
    if legacy.collect_results() != read("reproducibility/results-index.json"):
        raise ValueError("Saved A–F decisions or resource ledger differ from the result index")
    index = combined.collect_index()
    if index != read("reproducibility/results-index-v2.json"):
        raise ValueError("Combined result index differs from saved evidence")

    # Reuse the controlled study's aggregation function on saved decisions.
    # Its CLI, source analysis, native workers, and model requests stay unused.
    if f"{CONTROLLED}/common.py" not in files:
        raise ValueError("Controlled aggregation helpers are missing from the manifest")
    sys.path.insert(0, str(ROOT / CONTROLLED))
    try:
        study = load_saved_module("public_controlled_results", f"{CONTROLLED}/run_study.py", files)
        globals_ = read(f"{COMPARISON}/globals.json")["records"]
        extractions = read(f"{COMPARISON}/extractions.json")["records"]
        recalculated = study.aggregate(globals_, extractions)
    finally:
        sys.path.pop(0)
    summary = read(f"{COMPARISON}/summary.json")
    if any(summary[key] != value for key, value in recalculated.items()):
        raise ValueError("Controlled study aggregation differs from the saved summary")
    return index, len(globals_), len(extractions)


def main():
    files = verify_bytes()
    index, decisions, selections = verify_results(files)
    result = {
        "passed": True,
        "public_files_verified": len(files),
        "baseline_results_recomputed": True,
        "controlled_saved_decisions_checked": decisions,
        "controlled_saved_contract_selections_checked": selections,
        "recorded_completed_model_turns": index["resources"]["completed_experimental_model_turns"],
        "verification": "Public file hashes and saved evidence. No experimental reruns.",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
