# Same-commit Boolean source availability census

Pinned commit: `49b07130b3fcd12f2d064bba7c43869543a0e7e7`. One 8.60 MB public codeload archive was read after an explicit amendment; 122 regular Python blobs matched the cached git tree exactly. No source executed.

Metadata covers 108 Dataset-named classes (including support wrappers), 75 own score definitions, and all 108 answer-field traces. Thirteen classes had non-score True/False/Boolean string hints; their actual requested output domains were reviewed.

| Canonical True/False family | Own scorer | New source content? | Eligible |
|---|---|---|---|
| Game of Life halting | yes | no, developed #544 | no |
| String isomorphism | no, inherited | no | no |
| Ransom note | no, inherited | no | no |
| Course schedule | no, inherited | no | no |

**No new eligible distinct canonical Boolean scorer was confirmed.** Circuit logic uses native 0/1, syllogisms Yes/No, ACRE on/off/undetermined. Other hint matches are internal validators for mappings, moves, arithmetic or counts. None were recoded to force the unchanged interface.

This is broader source-availability evidence, not a complete theorem about arbitrary dynamic return values or all future project versions. The fixed census excludes vendored/rearc-generated/data sources and does not execute delegated generators. No LLM/analyzer outcomes were produced.

Conservative dedup hashes preserve global/builtin/member names. The earlier broad-alpha normalization risk remains documented in ../dedup-erratum.json; no initial eligibility decision depended on that hash. Hash equality is not semantic-equivalence proof.

Current-main metadata differs from the pin but has no added Python filenames; source contents at that newer head were not read. Do not silently switch versions or count the inherited default scorer under multiple tasks as independent implementations.
