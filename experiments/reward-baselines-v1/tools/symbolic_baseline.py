"""Small source-only path-certificate control, not a Python verifier.

No target module is imported or executed. The supported theory is native
str/None, literal rewards, normalization equality, reverse/multiset guards,
and one source-checked integer-factor parser grammar. Numeric algorithms,
loops, unknown calls, mutation, and unproved full-credit paths stay Unknown.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Term:
    op: str
    args: tuple = ()
    value: Any = None


@dataclass
class State:
    env: dict
    facts: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    evaluated: list = field(default_factory=list)

    def copy(self):
        return State(dict(self.env), list(self.facts), list(self.issues), list(self.evaluated))


@dataclass
class Exit:
    value: Term
    state: State
    span: dict


def constant(value):
    return Term("const", value=value)


def span(node):
    return {"line": getattr(node, "lineno", 1), "end_line": getattr(node, "end_lineno", 1)}


def unknown(reason):
    return Term("unknown", value=reason)


def issues(term):
    out = [term.value] if term.op == "unknown" else []
    for child in term.args:
        out.extend(issues(child))
    return out


def _literal(node, value):
    return isinstance(node, ast.Constant) and type(node.value) is type(value) and node.value == value


def _call(node, name, count=1):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == name and len(node.args) == count and not node.keywords)


def _strip(node, arg):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "strip" and isinstance(node.func.value, ast.Name)
            and node.func.value.id == arg and not node.args and not node.keywords)


def prime_helper_certificate(source):
    """Recognize the complete parser grammar, never merely its function name.

    The only admitted non-docstring statements are an empty-input return and
    sorted([int(token.strip()) for token in arg.split('×') if token.strip() != '']).
    Under normal return this preserves all parsed integer factors, including
    multiplicity, so equality with trusted reference factors is sufficient.
    """
    try:
        module = ast.parse(source)
    except (SyntaxError, ValueError, TypeError):
        return None
    if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
        return None
    fn = module.body[0]
    if fn.decorator_list or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.defaults:
        return None
    names = [a.arg for a in fn.args.posonlyargs + fn.args.args]
    if len(names) == 2 and names[0] == "self":
        names = names[1:]
    if len(names) != 1:
        return None
    arg = names[0]
    body = [n for n in fn.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                                     and isinstance(n.value.value, str))]
    if len(body) != 2 or not isinstance(body[0], ast.If) or not isinstance(body[1], ast.Return):
        return None
    guard, final = body
    # Optional empty guard is exactly: not arg or arg.strip() == ''.
    test = guard.test
    if not (isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or) and len(test.values) == 2
            and isinstance(test.values[0], ast.UnaryOp) and isinstance(test.values[0].op, ast.Not)
            and isinstance(test.values[0].operand, ast.Name) and test.values[0].operand.id == arg
            and isinstance(test.values[1], ast.Compare) and len(test.values[1].ops) == 1
            and isinstance(test.values[1].ops[0], ast.Eq) and _strip(test.values[1].left, arg)
            and _literal(test.values[1].comparators[0], "") and not guard.orelse
            and len(guard.body) == 1 and isinstance(guard.body[0], ast.Return)
            and isinstance(guard.body[0].value, ast.List) and not guard.body[0].value.elts):
        return None
    if not _call(final.value, "sorted") or not isinstance(final.value.args[0], ast.ListComp):
        return None
    comp = final.value.args[0]
    if len(comp.generators) != 1 or not _call(comp.elt, "int"):
        return None
    generator = comp.generators[0]
    if not isinstance(generator.target, ast.Name) or generator.is_async or len(generator.ifs) != 1:
        return None
    token = generator.target.id
    iterator = generator.iter
    check = generator.ifs[0]
    if not (isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Attribute)
            and isinstance(iterator.func.value, ast.Name) and iterator.func.value.id == arg
            and iterator.func.attr == "split" and len(iterator.args) == 1 and not iterator.keywords
            and _literal(iterator.args[0], "×") and _strip(comp.elt.args[0], token)
            and isinstance(check, ast.Compare) and len(check.ops) == 1
            and isinstance(check.ops[0], ast.NotEq) and _strip(check.left, token)
            and _literal(check.comparators[0], "")):
        return None
    # A factor or parameter named int/sorted would shadow a trusted builtin.
    if token in {"int", "sorted"} or arg in {"int", "sorted"}:
        return None
    return {"kind": "integer_factor_multiset_parser", "helper": fn.name,
            "source_span": span(fn), "grammar": "split ×; strip; discard empty; native int; sorted, multiplicity preserved"}


class Checker:
    MAX_PATHS = 128
    NATIVE_EXCEPTION_TYPES = frozenset({
        "BaseException", "Exception", "ArithmeticError", "AssertionError",
        "AttributeError", "ImportError", "IndexError", "KeyError", "LookupError",
        "ModuleNotFoundError", "NameError", "NotImplementedError", "OSError",
        "OverflowError", "RuntimeError", "TypeError", "UnboundLocalError",
        "ValueError", "ZeroDivisionError",
    })

    def __init__(self, unit):
        self.unit = unit
        self.contract = unit.get("contract", {})
        self.kind = self.contract.get("id")
        self.candidate = self.contract.get("candidate_arg", "answer")
        self.reference = self.contract.get("reference_arg", "entry")
        self.bindings = unit.get("stdlib_bindings", {})
        self.global_names = set()
        for source in (unit.get("source", ""), unit.get("score_source", "")):
            try:
                for node in ast.parse(source).body:
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        self.global_names.add(node.name)
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        self.global_names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
            except (SyntaxError, ValueError, TypeError):
                pass
        self.helper_certificates = {}
        self.helper_names = set()
        for helper in unit.get("helpers", []):
            name = helper.get("name", "").split(".")[-1]
            self.helper_names.add(name)
            cert = prime_helper_certificate(helper.get("source", ""))
            if cert and cert["helper"] == name:
                self.helper_certificates[name] = cert
        if {"int", "sorted"} & (self.helper_names | set(self.bindings) | self.global_names):
            self.helper_certificates.clear()
        self.exits = []
        self.budget_exceeded = False

    def fold(self, term):
        if term.op == "not" and term.args[0].op == "const":
            return constant(not term.args[0].value)
        if term.op in {"eq", "ne", "is", "isnot"}:
            a, b = term.args
            if a.op == b.op == "const":
                if term.op in {"is", "isnot"} and not (a.value is None or b.value is None or type(a.value) is bool or type(b.value) is bool):
                    return term
                value = a.value == b.value if term.op in {"eq", "ne"} else a.value is b.value
                return constant(not value if term.op in {"ne", "isnot"} else value)
        # Reference canonical strings are nonempty; stripping them is inert.
        if self.kind == "C_BOOLEAN_FULL" and term.op == "bool" and self.is_reference_answer(term.args[0]):
            return constant(True)
        return term

    def expr(self, node, state):
        if node is None:
            return constant(None)
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
            return constant(node.value)
        if isinstance(node, ast.Name):
            return state.env.get(node.id, unknown("unbound or unsupported name: " + node.id))
        if isinstance(node, ast.UnaryOp):
            child = self.expr(node.operand, state)
            if isinstance(node.op, ast.Not):
                return self.fold(Term("not", (child,)))
            if isinstance(node.op, (ast.UAdd, ast.USub)) and child.op == "const" and type(child.value) in {int, float}:
                return constant(child.value if isinstance(node.op, ast.UAdd) else -child.value)
        if isinstance(node, ast.BoolOp):
            return Term("and" if isinstance(node.op, ast.And) else "or", tuple(self.expr(n, state) for n in node.values))
        if isinstance(node, ast.Compare):
            operands = [node.left] + node.comparators
            ops = {ast.Eq: "eq", ast.NotEq: "ne", ast.Is: "is", ast.IsNot: "isnot"}
            comparisons = []
            for i, op in enumerate(node.ops):
                if type(op) not in ops:
                    return unknown("unsupported ordered/numeric comparison")
                comparisons.append(self.fold(Term(ops[type(op)], (self.expr(operands[i], state), self.expr(operands[i + 1], state)))))
            return comparisons[0] if len(comparisons) == 1 else Term("and", tuple(comparisons))
        if isinstance(node, ast.Subscript):
            base = self.expr(node.value, state)
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and base.op in {"reference", "field"}:
                value = Term("field", (base,), node.slice.value)
                allowed = {("answer",)}
                if self.kind in {"C_PALINDROME_FULL", "C_COMPLEX_FINITE"}:
                    allowed = {("metadata",), ("metadata", "letters" if self.kind == "C_PALINDROME_FULL" else "result")}
                return value if self.field_path(value) in allowed else unknown("reference field outside declared native contract")
            sl = node.slice
            if isinstance(sl, ast.Slice) and sl.lower is None and sl.upper is None:
                step = self.expr(sl.step, state)
                if step == constant(-1):
                    return Term("reverse", (base,))
            return unknown("unsupported subscript or slice")
        if isinstance(node, ast.Call):
            if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
                return unknown("keyword/starred call not modeled")
            args = tuple(self.expr(a, state) for a in node.args)
            if isinstance(node.func, ast.Name) and node.func.id not in state.env:
                name = node.func.id
                if name in {"bool", "len", "sorted"} and len(args) == 1 and name not in self.bindings and name not in self.helper_names and name not in self.global_names:
                    return self.fold(Term({"sorted": "sort"}.get(name, name), args))
                if name == "isinstance" and name not in self.global_names and name not in self.bindings and len(node.args) == 2 and isinstance(node.args[1], ast.Name) and node.args[1].id == "str" and "str" not in state.env and "str" not in self.bindings and "str" not in self.global_names:
                    return Term("is_str", (args[0],))
                if name in self.helper_certificates and len(args) == 1:
                    return Term("prime_parse", args, name)
            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                base_node = node.func.value
                if attr in {"strip", "lower"} and not args:
                    return Term(attr, (self.expr(base_node, state),))
                if isinstance(base_node, ast.Name) and base_node.id == "self" and attr in self.helper_certificates and len(args) == 1 and state.env.get("self") == Term("self"):
                    return Term("prime_parse", args, attr)
                if isinstance(base_node, ast.Name) and self.bindings.get(base_node.id) == "math" and base_node.id not in state.env and attr == "prod" and len(args) == 1 and args[0].op == "prime_parse":
                    return Term("product", args)
            return unknown("unverified call: " + ast.unparse(node.func))
        if isinstance(node, ast.BinOp):
            a, b = self.expr(node.left, state), self.expr(node.right, state)
            if a.op == b.op == "const" and type(a.value) in {int, float} and type(b.value) in {int, float}:
                try:
                    if isinstance(node.op, ast.Add):
                        return constant(a.value + b.value)
                    if isinstance(node.op, ast.Sub):
                        return constant(a.value - b.value)
                    if isinstance(node.op, ast.Mult):
                        return constant(a.value * b.value)
                    if isinstance(node.op, ast.Div):
                        return constant(a.value / b.value)
                except (ArithmeticError, ValueError):
                    return unknown("constant arithmetic raises")
            return unknown("numeric/arithmetic expression outside bounded theory")
        return unknown("unsupported expression: " + type(node).__name__)

    @staticmethod
    def field_path(term):
        path = []
        while term.op == "field":
            path.append(term.value)
            term = term.args[0]
        return tuple(reversed(path)) if term.op == "reference" else None

    def is_reference_answer(self, term):
        return self.field_path(term) == ("answer",)

    @staticmethod
    def normalized(term, require_both=False):
        operations = set()
        while term.op in {"strip", "lower"}:
            operations.add(term.op)
            term = term.args[0]
        if require_both and operations != {"strip", "lower"}:
            return None
        return term

    def simple_value(self, term):
        """Only universally fixed constants; never bounded-sample infeasibility."""
        folded = self.fold(term)
        return folded.value if folded.op == "const" else _UNKNOWN

    def consistent(self, state):
        seen = {}
        equalities = []
        for term, truth, _where, _text in state.facts:
            # Opaque unsupported terms are not semantic identities. In
            # particular, calls with the same spelling may differ in arguments
            # or effects, so they cannot prove infeasibility by contradiction.
            if issues(term):
                continue
            value = self.simple_value(term)
            if value is not _UNKNOWN and bool(value) != truth:
                return False
            if term in seen and seen[term] != truth:
                return False
            seen[term] = truth
            if term.op in {"eq", "ne", "is", "isnot"}:
                positive = truth == (term.op in {"eq", "is"})
                pair = frozenset(term.args)
                relation = "identity" if term.op in {"is", "isnot"} else "equality"
                for old_pair, old_relation, old_positive in equalities:
                    if old_pair == pair and old_relation == relation and old_positive != positive:
                        return False
                equalities.append((pair, relation, positive))
        return True

    def assume(self, term, truth, state, node):
        if term.op == "not":
            return self.assume(term.args[0], not truth, state, node)
        # Expand short-circuit conditions in evaluation order. Unknown calls in
        # unevaluated operands cannot introduce spurious effects/counterexamples.
        if term.op in {"and", "or"}:
            all_value = term.op == "and"
            continuing = [state]
            outcomes = []
            for child in term.args:
                if truth != all_value:
                    outcomes.extend(s for active in continuing for s in self.assume(child, truth, active, node))
                continuing = [s for active in continuing for s in self.assume(child, all_value, active, node)]
            return continuing if truth == all_value else outcomes
        unsupported = issues(term)
        if unsupported:
            self.exits.append(Exit(unknown("unsupported evaluated condition: " + "; ".join(unsupported)), state, span(node)))
            return []
        value = self.simple_value(term)
        if value is not _UNKNOWN:
            return [state] if bool(value) == truth else []
        out = state.copy()
        out.facts.append((term, truth, span(node), ast.unparse(node)))
        out.issues.extend(issues(term))
        return [out] if self.consistent(out) else []

    def native_handler_type(self, node, state):
        if node is None:
            return True
        names = node.elts if isinstance(node, ast.Tuple) else [node]
        return all(isinstance(name, ast.Name) and name.id in self.NATIVE_EXCEPTION_TYPES
                   and name.id not in state.env and name.id not in self.bindings
                   and name.id not in self.helper_names and name.id not in self.global_names
                   for name in names)

    def block(self, body, states, prefixes=None):
        for node in body:
            if len(states) + len(self.exits) > self.MAX_PATHS:
                self.budget_exceeded = True
                return []
            next_states = []
            for state in states:
                if prefixes is not None:
                    prefixes.append(state.copy())
                if isinstance(node, ast.Return):
                    value = self.expr(node.value, state)
                    final = state.copy()
                    final.issues.extend(issues(value))
                    self.exits.append(Exit(value, final, span(node)))
                elif isinstance(node, ast.If):
                    test = self.expr(node.test, state)
                    for branch_truth, branch in ((True, node.body), (False, node.orelse)):
                        assumed = self.assume(test, branch_truth, state, node.test)
                        next_states.extend(self.block(branch, assumed, prefixes))
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    if isinstance(node, ast.AnnAssign) and node.value is None:
                        self.exits.append(Exit(unknown("valueless annotation does not assign a runtime value"), state, span(node)))
                        continue
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    out = state.copy()
                    value = self.expr(node.value, state)
                    unsupported = issues(value)
                    if unsupported:
                        self.exits.append(Exit(unknown("unsupported evaluated assignment: " + "; ".join(unsupported)), state, span(node)))
                        continue
                    out.evaluated.append(value)
                    if all(isinstance(t, ast.Name) for t in targets):
                        for target in targets:
                            out.env[target.id] = value
                    else:
                        self.exits.append(Exit(unknown("assignment may mutate aliased input/reference"), state, span(node)))
                        continue
                    next_states.append(out)
                elif isinstance(node, ast.Try):
                    if any(not self.native_handler_type(handler.type, state) for handler in node.handlers):
                        self.exits.append(Exit(unknown("exception handler type is effectful, shadowed, or unverified"), state, span(node)))
                        continue
                    if node.finalbody:
                        self.exits.append(Exit(unknown("try/finally control flow is unsupported"), state, span(node)))
                        continue
                    snapshots = [state.copy()]
                    active = self.block(node.body, [state.copy()], snapshots)
                    next_states.extend(self.block(node.orelse, active, prefixes))
                    # Each handler is overapproximated from every possible body
                    # prefix; no handler is silently skipped. An exception-only
                    # full-credit path needs a separate feasibility proof.
                    for handler in node.handlers:
                        for snapshot in snapshots:
                            snapshot = snapshot.copy()
                            snapshot.issues.append("exception-handler reachability not proved")
                            if handler.name:
                                snapshot.env[handler.name] = unknown("exception object")
                            next_states.extend(self.block(handler.body, [snapshot], prefixes))
                elif isinstance(node, ast.Raise):
                    if node.exc is not None or node.cause is not None:
                        self.exits.append(Exit(unknown("explicit raise exception/cause evaluation is unsupported"), state, span(node)))
                    # A bare raise has no expression effects and cannot return normally.
                elif isinstance(node, ast.Pass):
                    next_states.append(state)
                elif isinstance(node, ast.Expr):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        next_states.append(state)  # docstring
                    else:
                        out = state.copy()
                        value = self.expr(node.value, state)
                        unsupported = issues(value)
                        if unsupported:
                            self.exits.append(Exit(unknown("unsupported evaluated expression: " + "; ".join(unsupported)), state, span(node)))
                            continue
                        out.evaluated.append(value)
                        next_states.append(out)
                else:
                    self.exits.append(Exit(unknown("unsupported statement/control flow: " + type(node).__name__), state, span(node)))
            states = next_states
        return states

    @staticmethod
    def equal_pairs(state):
        return [term.args for term, truth, *_ in state.facts
                if term.op in {"eq", "ne", "is", "isnot"} and truth == (term.op in {"eq", "is"})]

    def certificate(self, path):
        if path.state.issues:
            return None
        pairs = self.equal_pairs(path.state)
        if self.kind == "C_BOOLEAN_FULL":
            for a, b in pairs:
                for left, right in ((a, b), (b, a)):
                    if self.normalized(left) == Term("candidate") and self.is_reference_answer(self.normalized(right)):
                        return {"kind": "boolean_normalized_equality_implication",
                                "argument": "Equality of native candidate/reference strings after only strip/lower implies equal normalized Boolean tokens; reference is trusted canonical True/False."}
        if self.kind == "C_PALINDROME_FULL":
            palindrome = multiset = False
            for a, b in pairs:
                for left, right in ((a, b), (b, a)):
                    if right.op == "reverse" and left == right.args[0] and self.normalized(left, True) == Term("candidate"):
                        palindrome = True
                    if left.op == right.op == "sort" and self.normalized(left.args[0], True) == Term("candidate") and self.field_path(right.args[0]) == ("metadata", "letters"):
                        multiset = True
            if palindrome and multiset:
                return {"kind": "palindrome_and_exact_multiset_implication",
                        "argument": "Every full-credit path has equality to the reverse of the normalized candidate and equality of sorted normalized candidate/trusted letters. Both contract requirements follow."}
        if self.kind == "C_PRIME_FACTORS_FULL":
            for a, b in pairs:
                for left, right in ((a, b), (b, a)):
                    if left.op == right.op == "prime_parse" and left.value == right.value and left.args[0] == Term("candidate") and self.is_reference_answer(right.args[0]):
                        return {"kind": "source_certified_prime_factor_multiset_equality",
                                "argument": "Source-certified parsing preserves every integer factor and multiplicity. Equality to the trusted prime-factor multiset implies prime factors and equal reference product.",
                                "helper_certificate": self.helper_certificates[left.value]}
        return None

    def witness_value(self, term, candidate, reference):
        if term.op == "const":
            return term.value
        if term.op == "candidate":
            return candidate
        if term.op == "reference":
            return _REFERENCE
        if term.op == "self":
            return _SELF
        if self.is_reference_answer(term):
            return reference
        values = [self.witness_value(a, candidate, reference) for a in term.args]
        if any(v is _UNKNOWN or v is _RAISE for v in values):
            return _UNKNOWN
        if term.op in {"strip", "lower"}:
            value = values[0]
            if value is _OTHER:
                return _OTHER
            if not isinstance(value, str):
                return _RAISE
            return value.strip() if term.op == "strip" else value.lower()
        if term.op == "bool":
            return True if values[0] is _OTHER else bool(values[0])
        if term.op == "is_str":
            return values[0] is _OTHER or isinstance(values[0], str)
        if term.op == "len":
            return len(values[0]) if isinstance(values[0], str) else _UNKNOWN
        if term.op in {"eq", "ne"}:
            same = values[0] == values[1]
            return same if term.op == "eq" else not same
        if term.op in {"is", "isnot"}:
            if None not in values:
                return _UNKNOWN  # string identity is not string equality
            same = values[0] is values[1]
            return same if term.op == "is" else not same
        if term.op == "not":
            return not values[0]
        return _UNKNOWN

    def boolean_counterexample(self, path, source):
        if self.kind != "C_BOOLEAN_FULL" or path.state.issues:
            return None
        # These are source-only native semantic classes, not replay inputs.
        # OTHER denotes a fresh nonempty strip/lower-stable non-Boolean string,
        # distinct from all source literals. Only exact modeled facts can pass.
        candidates = [(_OTHER, "fresh nonempty non-Boolean normalized string"),
                      (None, "None"), ("", "empty string"),
                      ("true", "normalized true token"), ("false", "normalized false token"),
                      ("True", "canonical True token"), ("False", "canonical False token")]
        literals = {n.value for n in ast.walk(source) if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) <= 128}
        candidates.extend((s, "source string literal " + repr(s)) for s in sorted(literals))
        for candidate, description in candidates:
            for reference in ("True", "False"):
                normalized = candidate.strip().lower() if isinstance(candidate, str) else candidate
                if normalized == reference.lower():
                    continue
                values = [self.witness_value(term, candidate, reference) for term, *_ in path.state.facts]
                evaluated = [self.witness_value(term, candidate, reference) for term in path.state.evaluated]
                if (all(v is not _UNKNOWN and v is not _RAISE for v in evaluated)
                        and all(v is not _UNKNOWN and v is not _RAISE and bool(v) == fact[1] for v, fact in zip(values, path.state.facts))):
                    return {"kind": "native_boolean_path_counterexample",
                            "candidate_class": description, "trusted_reference": reference,
                            "argument": "The displayed native string/None class satisfies every modeled path condition and reaches a literal full reward, while normalized Boolean equality is false. No subject code was executed."}
        return None

    def run(self):
        source = self.unit.get("score_source") or self.unit.get("source", "")
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, TypeError) as error:
            return result("unknown", unsupported=["source parse failed: " + str(error)])
        name = self.unit.get("entry_name")
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and (name is None or n.name == name)]
        if len(functions) != 1:
            return result("unknown", unsupported=["entry function is not uniquely identified"])
        fn = functions[0]
        if any(not isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom)) for node in tree.body):
            return result("unknown", unsupported=["module-level executable bindings/effects outside declared source boundary"])
        arguments = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
        if fn.decorator_list or fn.args.vararg or fn.args.kwarg or self.candidate not in arguments or self.reference not in arguments:
            return result("unknown", unsupported=["unsupported entry signature/decorators"])
        # These binding/effect surfaces are outside this checker's language.
        # Inspect the entire function before path collection: a later lexical
        # binder affects an earlier name lookup even when its statement is dead.
        for node in ast.walk(fn):
            if (isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Match, ast.Delete, ast.ClassDef, ast.AsyncFunctionDef))
                    or (isinstance(node, ast.FunctionDef) and node is not fn)):
                return result("unknown", unsupported=["unsupported whole-function binding/control surface: " + type(node).__name__])
        # Arguments and imports may shadow builtins; a shadow must never gain a
        # native library model merely because its identifier is familiar.
        env = {arg: unknown("unmodeled parameter: " + arg) for arg in arguments}
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                env.setdefault(node.id, unknown("local read before supported assignment: " + node.id))
            elif isinstance(node, ast.ExceptHandler) and node.name:
                env.setdefault(node.name, unknown("local exception-target binding: " + node.name))
        env[self.candidate] = Term("candidate")
        env[self.reference] = Term("reference")
        if "self" in arguments:
            env["self"] = Term("self")
        active = self.block(fn.body, [State(env)])
        self.exits.extend(Exit(constant(None), state, span(fn)) for state in active)
        if self.budget_exceeded:
            return result("unknown", unsupported=["static path budget exceeded"])
        certificates, unsupported = [], []
        full_count = 0
        for path in self.exits:
            reward = path.value.value if path.value.op == "const" else _UNKNOWN
            if reward is None or (type(reward) in {int, float, bool} and reward < 1.0):
                continue
            if type(reward) not in {int, float, bool} or not reward >= 1.0:
                unsupported.extend(issues(path.value) or ["return reward has no proved bound below full credit"])
                continue
            full_count += 1
            cert = self.certificate(path)
            evidence = [{"condition": text, "required_truth": truth, "source_span": where}
                        for _term, truth, where, text in path.state.facts]
            if cert:
                certificates.append({**cert, "return_span": path.span, "conditions": evidence})
                continue
            alarm = self.boolean_counterexample(path, tree)
            if alarm:
                return result("alarm", certificate=alarm, evidence=evidence,
                              spans=[path.span] + [e["source_span"] for e in evidence])
            unsupported.extend(path.state.issues or ["full-credit path lacks a supported contract implication/counterexample certificate"])
        if unsupported:
            return result("unknown", certificate={"proved_full_credit_paths": certificates}, unsupported=unsupported)
        return result("no_alarm", certificate={"kind": "all_normal_full_credit_paths_certified",
                      "full_credit_path_count": full_count, "paths": certificates,
                      "argument": "All collected normal full-credit returns imply the fixed contract; known partial returns and exceptions are outside the violation."},
                      spans=[cert["return_span"] for cert in certificates])


_UNKNOWN = object()
_RAISE = object()
_OTHER = object()
_REFERENCE = object()
_SELF = object()


def result(verdict, certificate=None, evidence=None, spans=None, unsupported=None):
    return {"verdict": verdict, "certificate": certificate,
            "evidence": evidence or [], "source_spans": spans or [],
            "unsupported_reason": "; ".join(dict.fromkeys(unsupported or [])) or None,
            "method": "bounded-static-source-path-certificates-v1"}


def analyze(unit):
    """Return alarm/no_alarm/unknown from source and the fixed contract only."""
    return Checker(unit).run()
