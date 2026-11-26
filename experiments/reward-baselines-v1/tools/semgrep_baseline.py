"""Pinned Semgrep CE source-pattern baseline; never a correctness proof.

All three fixed risky-idiom rules run for every supported input. CPython AST is
used only to validate the source-only envelope and enumerate structural spans;
it does not decide alarms or remove findings. Adjacent finite-guard exclusions
are ordinary Semgrep search patterns. No scorer/helper is imported or executed.
"""

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PINNED_VERSION = "1.183.0"
PINNED_CORE_SHA256 = "8b0c1fa10fa70372ea64ca0dc9cf3de0fd53db9c2556f6af5f973e8df12d4995"
METHOD_ID = "semgrep-ce-fixed-risky-idioms-v1"
QUALIFICATION = (
    "Heuristic source-pattern detector, not proof of reward correctness. "
    "No_alarm means complete syntactic scan with no fixed-rule finding. "
    "No dedicated palindrome/multiset or prime/product semantic checks are implemented; "
    "C_PALINDROME_FULL and C_PRIME_FACTORS_FULL no_alarm results have that limitation. "
    "Boolean semantic preguards are not proved; equivalent aliases, helper-mediated "
    "idioms and nonadjacent finite guards may be missed or warned on."
)


def _rule(rule_id, message, **body):
    return {"id": rule_id, "languages": ["python"], "severity": "WARNING",
            "message": message, "mode": "search", **body}


def risky_rules():
    """Fixed search rules; generated identically for every unit/contract."""
    guard_exclusions = []
    for guarded in ("$S = min(1.0, math.exp(-$D))", "return min(1.0, math.exp(-$D))"):
        guard_exclusions.append({"pattern-not-inside":
                                 "if not math.isfinite($D):\n    return 0.0\n" + guarded})
        guard_exclusions.append({"pattern-not-inside":
                                 "if math.isfinite($D):\n    " + guarded})
    return {"rules": [
        _rule("reward-bool-truthiness-equality",
              "Truthiness equality can award full credit to unequal Boolean strings.",
              pattern="bool($CANDIDATE) == bool($REFERENCE)"),
        _rule("reward-nonfinite-exp-clamp",
              "Clamping an exponential with min(1.0, ...) can promote a nonfinite distance to full credit.",
              **{"pattern-either": [
                  {"patterns": [{"pattern": "min(1.0, math.exp(-$D))"},
                                {"metavariable-regex": {"metavariable": "$D", "regex": r"^[A-Za-z_]\w*$"}},
                                *guard_exclusions]},
                  {"patterns": [{"pattern": "min(1.0, math.exp(-$D))"},
                                {"metavariable-regex": {"metavariable": "$D", "regex": r"^(?![A-Za-z_]\w*$)[\s\S]+$"}}]},
              ]}),
        _rule("reward-prefix-shorter-length-ratio",
              "Prefix-style credit divided by the shorter length can reach full credit for a strict prefix.",
              pattern="$MATCH / min(len($LEFT), len($RIGHT))"),
    ]}


def coverage_rules():
    return {"rules": [
        _rule("coverage-function", "Function structural coverage.",
              pattern="def $FUNCTION(...):\n    ..."),
        _rule("coverage-return", "Return structural coverage.",
              **{"pattern-either": [{"pattern": "return $VALUE"}, {"pattern": "return"}]}),
    ]}


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _identifier(value, label):
    if not isinstance(value, str) or not value.isidentifier():
        raise ValueError(f"{label} must be an identifier")
    return value


def _function_fragment(source, expected_name):
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Each score/helper fragment must be nonempty source text")
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Each fragment must contain one synchronous function definition")
    node = tree.body[0]
    if node.name != expected_name:
        raise ValueError("Declared function name does not match fragment")
    if any(isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
           for child in ast.walk(node) if child is not node):
        raise ValueError("Nested function/class definitions are outside the input envelope")
    return node


def _validate(unit):
    if not isinstance(unit, dict):
        raise ValueError("Unit must be an object")
    entry_name = _identifier(unit.get("entry_name"), "entry_name")
    if not isinstance(unit.get("unit_id"), str) or not unit["unit_id"]:
        raise ValueError("unit_id must be a nonempty log identifier")
    contract = unit.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("contract must be an object")
    frozen = json.loads((ROOT / "protocol/contracts.json").read_text())["contracts"]
    contract_id = contract.get("id")
    if contract_id not in frozen:
        raise ValueError("Unrecognized fixed contract")
    candidate = _identifier(contract.get("candidate_arg"), "candidate_arg")
    reference = _identifier(contract.get("reference_arg"), "reference_arg")
    expected = {"id": contract_id, "candidate_arg": candidate, "reference_arg": reference,
                "full_credit_threshold": 1.0, **frozen[contract_id]}
    if contract != expected or candidate == reference:
        raise ValueError("Contract must match the frozen clauses and native argument shape")
    helpers = unit.get("helpers")
    if not isinstance(helpers, list):
        raise ValueError("helpers must be a list")
    fragments = [(entry_name, unit.get("score_source"))]
    for helper in helpers:
        if not isinstance(helper, dict) or set(helper) != {"name", "source"}:
            raise ValueError("Helper records must contain exactly name and source")
        fragments.append((_identifier(helper["name"], "helper name"), helper["source"]))
    names = [name for name, _ in fragments]
    if len(set(names)) != len(names):
        raise ValueError("Declared function names must be unique")
    expected_nodes = [_function_fragment(source, name) for name, source in fragments]
    score = expected_nodes[0]
    parameters = {arg.arg for arg in score.args.posonlyargs + score.args.args + score.args.kwonlyargs}
    if not {candidate, reference} <= parameters:
        raise ValueError("Native candidate/reference parameters absent from entry function")
    fixed = unit.get("fixed_parameters", {})
    if not isinstance(fixed, dict):
        raise ValueError("fixed_parameters must be an object of native scalar arguments")
    for name, value in fixed.items():
        _identifier(name, "fixed parameter")
        if (name not in parameters or name in {candidate, reference}
                or type(value) not in (str, int, float, bool, type(None))
                or isinstance(value, float) and not math.isfinite(value)):
            raise ValueError("Unsupported fixed-parameter metadata")
    source = unit.get("source")
    if not isinstance(source, str) or any(source.count(fragment) != 1 for _, fragment in fragments):
        raise ValueError("Source must retain each exact score/helper fragment once")
    tree = ast.parse(source)
    if len(tree.body) != len(expected_nodes) or any(not isinstance(n, ast.FunctionDef) for n in tree.body):
        raise ValueError("Source may contain only the declared score/helper definitions")
    actual = {node.name: node for node in tree.body}
    if set(actual) != set(names):
        raise ValueError("Source function declarations differ from metadata")
    for name, expected_node in zip(names, expected_nodes):
        if ast.dump(actual[name]) != ast.dump(expected_node):
            raise ValueError("Source function differs from its exact declared fragment")
    bindings = unit.get("stdlib_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("stdlib_bindings must map identifiers to standard-library names")
    for alias, target in bindings.items():
        _identifier(alias, "stdlib alias")
        if (not isinstance(target, str) or not all(part.isidentifier() for part in target.split("."))
                or target.split(".")[0] not in sys.stdlib_module_names):
            raise ValueError("Unsupported standard-library binding declaration")
    # Guard suppression relies on the standard math namespace. Refuse a changed
    # binding rather than silently treating a user implementation as isfinite.
    loaded_math = any(isinstance(node, ast.Name) and node.id == "math" and isinstance(node.ctx, ast.Load)
                      for node in ast.walk(tree))
    if loaded_math and bindings.get("math") != "math":
        raise ValueError("math operations require the declared standard math binding")
    protected_names = {"bool", "min", "len", "math"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError("Local imports/global/nonlocal declarations are outside the binding envelope")
        target = node
        while isinstance(target, (ast.Attribute, ast.Subscript)):
            target = target.value
        if (isinstance(node, (ast.Attribute, ast.Subscript))
                and isinstance(node.ctx, (ast.Store, ast.Del))
                and isinstance(target, ast.Name) and target.id in protected_names):
            raise ValueError("A fixed-rule builtin/math binding is mutated")
        if isinstance(node, ast.FunctionDef) and node.name in protected_names:
            raise ValueError("A function shadows a fixed-rule builtin/math name")
        if ((isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
             and node.id in protected_names)
                or isinstance(node, ast.arg) and node.arg in protected_names):
            raise ValueError("A fixed-rule builtin/math name is rebound; semantics unsupported")
    return tree, actual


def find_core(explicit=None):
    if explicit is not None:
        core = Path(explicit).expanduser().resolve()
    else:
        candidates = list((ROOT.parents[1] / "work/semgrep-tool/distribution").rglob("semgrep-core"))
        if len(candidates) != 1:
            raise ValueError("Expected one cached pinned Semgrep core; pass core explicitly")
        core = candidates[0].resolve()
    if not core.is_file() or not os.access(core, os.X_OK):
        raise ValueError("Semgrep core must be executable")
    if _sha(core.read_bytes()) != PINNED_CORE_SHA256:
        raise ValueError("Pinned Semgrep core SHA-256 mismatch")
    return core


def _environment():
    env = dict(os.environ)
    env["SEMGREP_SEND_METRICS"] = "off"
    if "SSL_CERT_FILE" not in env and Path("/etc/ssl/cert.pem").is_file():
        env["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"
    return env


def _execute(command, output, prefix, timeout):
    record = {"command": command, "timeout_seconds": timeout}
    _write_json(output / f"{prefix}-command.json", record)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=_environment())
    except subprocess.TimeoutExpired as error:
        for name, value in (("stdout", error.stdout), ("stderr", error.stderr)):
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            (output / f"{prefix}-{name}.txt").write_text(value or "")
        record["timed_out"] = True
        _write_json(output / f"{prefix}-command.json", record)
        raise
    (output / f"{prefix}-stdout.txt").write_text(proc.stdout)
    (output / f"{prefix}-stderr.txt").write_text(proc.stderr)
    record["returncode"] = proc.returncode
    _write_json(output / f"{prefix}-command.json", record)
    return proc


def _scan(core, rules, source_path, output, prefix):
    rule_path = output / f"{prefix}-rules.json"
    _write_json(rule_path, rules)
    command = [str(core), "-json_nodots", "-j", "1", "-timeout", "10", "-lang", "python",
               "-rules", str(rule_path), str(source_path)]
    proc = _execute(command, output, prefix, 30)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("Semgrep did not return valid JSON") from error
    _write_json(output / f"{prefix}-raw.json", payload)
    if proc.returncode:
        raise ValueError(f"Semgrep exited with status {proc.returncode}")
    if not isinstance(payload, dict):
        raise ValueError("Semgrep output must be an object")
    if (payload.get("errors") or payload.get("skipped_rules")
            or payload.get("time", {}).get("fixpoint_timeouts")):
        raise ValueError("Semgrep reported errors, skipped rules, or timeouts")
    if payload.get("version") != PINNED_VERSION:
        raise ValueError("Semgrep JSON version does not match pinned version")
    if payload.get("paths", {}).get("scanned") != [str(source_path)]:
        raise ValueError("Semgrep did not scan exactly the requested source file")
    findings = payload.get("results")
    if not isinstance(findings, list):
        raise ValueError("Semgrep omitted its result list")
    valid_ids = {rule["id"] for rule in rules["rules"]}
    for finding in findings:
        if (not isinstance(finding, dict) or finding.get("check_id") not in valid_ids
                or finding.get("path") != str(source_path)):
            raise ValueError("Unexpected engine finding path or rule")
    return findings, command, _sha(rule_path.read_bytes())


def _span(node):
    return [node.lineno, node.col_offset, node.end_lineno, node.end_col_offset]


def _engine_span(finding):
    return [finding["start"]["line"], finding["start"]["col"] - 1,
            finding["end"]["line"], finding["end"]["col"] - 1]


def _coverage(tree, functions, findings):
    covered_functions = []
    for name, function in functions.items():
        matches = []
        for finding in findings:
            if finding["check_id"] != "coverage-function":
                continue
            binding = finding.get("extra", {}).get("metavars", {}).get("$FUNCTION", {})
            if (binding.get("abstract_content") == name
                    and binding.get("start", {}).get("line") == function.lineno
                    and finding["end"]["line"] == function.end_lineno):
                matches.append(finding)
        if len(matches) != 1:
            raise ValueError(f"Function structural coverage incomplete for {name}")
        covered_functions.append({"name": name, "source_span": _span(function),
                                  "engine_span": _engine_span(matches[0])})
    expected_returns = sorted(_span(node) for node in ast.walk(tree) if isinstance(node, ast.Return))
    actual_returns = sorted(_engine_span(finding) for finding in findings
                            if finding["check_id"] == "coverage-return")
    if not expected_returns or expected_returns != actual_returns:
        raise ValueError("Return structural coverage empty or incomplete")
    return {"status": "complete", "functions": covered_functions, "return_spans": expected_returns,
            "function_count": len(functions), "return_count": len(expected_returns),
            "semantics_proved": False, "mode": "search", "source_rewritten": False}


def run(unit, output_dir, core=None):
    """Scan one exact source-only unit; failures and unsupported shapes => unknown.

    The output directory must be empty to preserve previous runs. Unit identity
    is logged only; it never affects validation, rules, findings, or verdict.
    """
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Output directory must be empty to preserve prior evidence")
    started = time.perf_counter()
    result = {"method": METHOD_ID, "verdict": "unknown", "status": "error", "errors": [],
              "findings": [], "all_findings": [], "coverage": {"status": "not_run"},
              "qualification": QUALIFICATION, "explanation": "Scan not completed.",
              "source_executed": False, "source_rewritten": False}
    if isinstance(unit, dict):
        result["unit_id"] = unit.get("unit_id") if isinstance(unit.get("unit_id"), str) else None
        contract_id = unit.get("contract", {}).get("id") if isinstance(unit.get("contract"), dict) else None
        result["contract_id"] = contract_id if isinstance(contract_id, str) else None
        if isinstance(unit.get("source"), str):
            result["source_sha256"] = _sha(unit["source"].encode("utf-8"))
    try:
        tree, functions = _validate(unit)
        source_path = output / "source.py"
        source_path.write_bytes(unit["source"].encode("utf-8"))
        core = find_core(core)
        proc = _execute([str(core), "-version"], output, "engine", 20)
        if proc.returncode or not re.search(r"\b" + re.escape(PINNED_VERSION) + r"\b", proc.stdout):
            raise ValueError("Semgrep version invocation failed or mismatched")
        result["engine"] = {"version": proc.stdout.strip(), "sha256": _sha(core.read_bytes()),
                            "path": str(core), "metrics": "off"}
        coverage_findings, command, rule_hash = _scan(core, coverage_rules(), source_path, output, "coverage")
        result["coverage"] = {"status": "incomplete", "command": command, "rule_sha256": rule_hash}
        result["coverage"] = _coverage(tree, functions, coverage_findings)
        result["coverage"].update(command=command, rule_sha256=rule_hash)
        findings, command, rule_hash = _scan(core, risky_rules(), source_path, output, "scan")
        result["command"] = command
        result["rule_sha256"] = rule_hash
        result["all_findings"] = findings
        # All source consists of the declared definitions. Span checks only
        # establish source ownership; no AST semantics suppress any finding.
        for finding in findings:
            span = _engine_span(finding)
            scopes = [name for name, node in functions.items()
                      if (node.lineno, node.col_offset) <= tuple(span[:2])
                      and tuple(span[2:]) <= (node.end_lineno, node.end_col_offset)]
            if len(scopes) != 1:
                raise ValueError("Finding lies outside exactly one declared function")
            result["findings"].append({"rule_id": finding["check_id"], "function": scopes[0],
                                       "span": span, "message": finding["extra"]["message"]})
        result.update(verdict="alarm" if findings else "no_alarm", status="complete",
                      explanation=("A fixed risky source idiom matched; this is not an executable violation witness."
                                   if findings else "All declared function and return spans were covered; no fixed risky idiom matched."))
    except (ValueError, KeyError, TypeError, OSError, SyntaxError, UnicodeError, subprocess.SubprocessError) as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
        result["explanation"] = "Unsupported input or incomplete/failed engine scan; no negative conclusion."
    result["wall_seconds"] = round(time.perf_counter() - started, 6)
    _write_json(output / "result.json", result)
    return result
