# Source-selected scalar reward controls

The selected replay set contains **three controls**, with an explicit deficit of one against the requested four. All are real `score_answer` overrides at pinned main commit `49b07130b3fcd12f2d064bba7c43869543a0e7e7`. No upstream module, generator, scoring method, analyzer or model was executed by this curator. Root owns isolated replay; all selected probe execution flags remain pending until that replay is recorded.

“Normal” is limited to the declared entry and answer contracts in `records/controls.json`. It does not assert that a whole task/module has no bugs. In particular, deliberate positive partial rewards and alternative valid answers must not be treated as incorrect behavior merely because a response differs from `entry.answer`.

| Selected scorer | Full-credit meaning | Dependencies for isolated real-source replay | Probes |
| --- | --- | --- | --- |
| `PalindromeDataset.score_answer` | After documented case/outer-whitespace normalization, response is a palindrome using exactly the supplied letter multiset. `baab` is as valid as `abba` for a,a,b,b. | Builtins only; no helper or self property. `typing.Optional`/`Any` are annotation globals. | 7 |
| `GroupAnagramsDataset.score_answer` | Same word partition after canonicalizing group order and within-group word order. | `json`; unchanged `_sort_nested_list` at lines 67–69; no self property. `typing.Optional`/`Any` are annotation globals. | 6 |
| `PrimeFactorizationDataset.score_answer` | Parsed integer factors equal the oracle prime multiset, including multiplicity, regardless of order. | `math`; unchanged `_normalize_answer` at lines 50–55; no self property. `typing.Optional`/`Any` are annotation globals. | 5 |

The replay inputs are small manually constructed witnesses in the native method-entry shape, not generated benchmark samples. Question fields use the pinned literal templates where available. Each record includes entry domains, two or three specific full-credit properties, explicit scalar expectations, method/helper line locations, source hashes and file provenance, semantic rationale, and limitations. The four letters a,a,b,b, anagram words eat/tea/tan/nat, and integer 12 can be checked directly without running a task generator.

The 18 selected probes deliberately include:

- A valid alternative palindrome and an order-permuted correct anagram partition/factor list.
- Intended partial credit: nonpalindrome 0.02, wrong-letter palindrome 0.05, wrong but canonicalizable JSON partition 0.01, same-product composite factorization 0.5, and wrong-product integer factors 0.01.
- Missing answers returning zero, plus empty palindrome and malformed JSON checks where the source explicitly supports those contracts.

The prime-factor scorer does **not** catch nonnumeric-factor `ValueError`; its normal label covers numeric factor syntax and missing input, not arbitrary malformed strings. The parser also ignores empty multiplication-separated fields. This limitation is recorded rather than treating the scorer as universally total. Group-anagram claims assume a correct partition oracle with disjoint nonempty groups, and palindrome claims use the scorer's explicit normalization.

## Bounded selection inventory

Exactly eight primary module bodies were read, in this order. No more source selection was performed after reaching that budget.

| Module | Disposition | Source-review reason |
| --- | --- | --- |
| `algorithmic/palindrome_generation.py` | Selected scoped control | Explicit palindrome and exact-multiset checks, explicit partial-credit branches. |
| `algorithmic/spell_backward.py` | Needs review; unexecuted | Repeated float additions of `1 / answer_len` combined with an exact `reward == 1.0` check raise a boundary concern for overlong responses with the complete expected prefix. This is a source-review concern, not a reproduced defect claim. |
| `algorithmic/word_sequence_reversal.py` | Excluded inherited family | Has no `score_answer` override. A different task wrapper does not create another independent inherited scorer family. Base source was not fetched by this curator. |
| `arithmetic/decimal_arithmetic.py` | Needs review; ambiguous contract | The prompt asks for significant-digit precision, while full credit uses an absolute tolerance derived from operand decimal places. Its scorer docstring's nonmatch reward also differs from its implementation. No normal label was forced. |
| `algorithmic/group_anagrams.py` | Selected scoped control | Distinct order-independent nested-list partition scorer and one pure helper. |
| `arithmetic/prime_factorization.py` | Selected scoped control | Distinct numeric-multiset scorer, explicit same-product partial reward; malformed-token limitation remains visible. |
| `games/n_queens.py` | Source-reviewed candidate excluded from replay | Real fallback uses builtin `eval`, outside the selected pure replay scope. The full source-reviewed candidate, manually checked 4-queen boards, alternative valid answer and formatting partial-credit probes remain in `source_reviewed_not_selected`. No target execution and no substitution with `literal_eval`. |
| `algorithmic/binary_matrix.py` | Inspected, not selected | Also uses builtin `eval` fallback; exact-serialization and formatting-credit pattern adds less semantic diversity. Evidence retained in inventory, no normal/replay label. |

The one-control deficit is intentional: no unsafe eval fallback, ambiguous task contract, suspicious floating-point behavior or inherited duplicate was promoted merely to reach four. N-queens probes are explicitly excluded, so root's selected replay loop must iterate only `controls`, not `source_reviewed_not_selected`.

## Provenance and verification boundary

Each source was retrieved with `repro/collect_source.py fetch main <path>` against the fixed refs/tree files, with Git blob SHA-1 and SHA-256 verification. The complete unmodified upstream files and per-file provenance are retained under `upstream/main/` and `collection/source-provenance/main/`. All inspected sources are development/exposed material. Probes, helpers and future versions of one scorer belong to the same function-family split group.

Curator verification was structural and read-only: JSON parses; selected IDs and probe IDs are unique; every probe references an existing native entry; numeric expected rewards are bounded; scorer/helper line spans match their pinned AST definitions; source hashes and provenance match; selected methods/helpers contain no import or eval/exec call. This verifies the record's wiring and source correspondence, not runtime reward observations. Runtime proof must use the unchanged real scoring bodies and real named helpers in root's isolated harness.
