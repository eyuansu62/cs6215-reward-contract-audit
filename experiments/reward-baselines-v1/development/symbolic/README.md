# Bounded symbolic control

API: `tools/symbolic_baseline.py: analyze(unit) -> dict`.
The result contains `verdict` (`alarm`, `no_alarm`, `unknown`), `certificate`,
`evidence`, `source_spans`, and `unsupported_reason`.

This is source-exposed engineering development under the frozen contracts,
not a blind evaluation or general Python verifier. Development read the
frozen protocol and exact extracted scorer/helper source for API context.
No oracle, curated probe values, replay/evidence files, issue/PR text/status,
or primary predictions were consumed while authoring this control.
Subject identifiers and paths are never classification conditions.

The checker parses ASTs without importing or executing subject modules. It
tracks simple local assignments and all `if` branches, including fallthrough,
collects conditions for each normal return, and compares literal numeric
rewards with the frozen threshold of 1.0. Positive partial rewards below 1.0
do not constitute violations. Short-circuit conditions are expanded in source
evaluation order. Try handlers are overapproximated from body prefixes;
their reachability is not assumed proven, and `finally` is unsupported.

Supported certificates:

- Boolean: equality of candidate/reference native strings after only
  `strip`/`lower` implies equality of normalized Boolean tokens, using the
  trusted canonical True/False reference assumption. The Boolean alarm model
  constructs native semantic classes from the contract and source, including
  a fresh nonempty non-Boolean string distinct from all source literals. A
  counterexample must satisfy every modeled path fact and every intermediate
  expression's definedness; it does not execute the scorer or replay probes.
- Palindrome: both equality to the reverse of the fully normalized candidate
  and equality of its sorted multiset to trusted letters dominate full reward.
- Prime factors: equality of parsed candidate/reference factor lists is
  accepted only after the complete helper source matches the narrow grammar
  `split('×')`, strip, discard empty tokens, native integer parsing, then sort.
  Equality preserves every prime factor and multiplicity under the trusted
  reference assumption. A constant helper or altered factor computation does
  not receive this certificate.

The native library models apply only within the protocol's pure scorer and
declared helper/standard-library boundary. Local, helper, and import shadows
of modeled builtins are not treated as native functions. Annotations are not
proofs. The checker assumes the fixed native input/reference domains supplied
by the contract; it does not model outer wrappers, dynamic module initializers,
monkeypatching, resource exhaustion, or arbitrary hidden global state.

Binding discovery examines the entire scorer before collecting paths.
Exception-target names are prebound as locals. Local imports, global/nonlocal
declarations, nested definitions/classes, match statements, and delete
statements conservatively make the whole function unsupported, including when
the later binder would be unreachable. This prevents an earlier name lookup
from incorrectly receiving a builtin model.

Unknown calls, aliased input mutation, undeclared reference fields, arbitrary
helpers, general loops, numeric comparisons/parsers, formatted values, and
complex/numeric invariants cannot supply a full-credit proof. An unproved
potential full-reward path produces `unknown`, not `no_alarm`. A source with
only known sub-full-credit normal returns can receive a vacuous target-property
certificate; this is not a claim of totality or overall scorer correctness.
The static path limit is 128; exceeding it returns `unknown`.

Evaluated unsupported conditions, assignments, expressions, and mutating
targets terminate the active symbolic path with an Unknown exit. They cannot
reuse stale trusted-reference facts after possible effects. Opaque unsupported
terms never establish contradictions/infeasibility, even when their text
matches. Constant short-circuit operands remain handled in evaluation order.

Synthetic verification: `python3 -m unittest -v test_symbolic_baseline.py`
from `tools/`. These regressions exercise supported guards, assignment branches,
unprotected fallthrough, guarded truthiness, dead branches, exception handlers,
intermediate exceptions, builtin shadowing, unknown calls/mutation, unsupported
loops/numeric contracts, and good/bad helper grammars. No primary units are
analyzed by this test suite. Coverage gaps are engineering limits of this
control, not evidence of an LLM benefit.

Independent pre-freeze review identified missed lexical binders, conflated
opaque-call conditions, and stale reference facts after mutation. Synthetic
regressions reproduced these failures before the narrow conservative fixes.
The failing run is preserved in `pre-freeze-regressions-before-fix.txt`; the
valueless annotation regression is in `annotation-regression-before-fix.txt`.
The raise-expression/cause regression is in `raise-regression-before-fix.txt`.
Explicit raise exception/cause evaluation is unsupported; it cannot silently
skip effects before an exception handler. A bare raise remains exception-only.
Handler types are limited to bare handlers or unshadowed native builtin
exception names (optionally a tuple of names). Other expressions and unproven
aliases are unsupported, including expressions with effects before a handler.
The corresponding failing regressions are in
`handler-type-regressions-before-fix.txt`.
The updated `synthetic-tests.txt` records all 28 tests passing. Valueless
annotations are unsupported rather than interpreted as assigning None.
No primary analysis
was performed during this revision.
