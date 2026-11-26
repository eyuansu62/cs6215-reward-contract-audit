# Source and execution provenance

Upstream project: https://github.com/open-thought/reasoning-gym

The fixed main/issue commit is49b07130b3fcd12f2d064bba7c43869543a0e7e7.
Proposed repair heads are4ab6143b1858f5bf09ebe23501a8ffd77c86cdf0(PR561)
and758f7fb8e0c732571d3ab6b67f78207f203f3502(PR562). Neither was merged at collection.

Original source and the Apache License2.0 text are retained. Individual sources,
commit/tree identities and Git blob/SHA256 proofs are under collection/ and
source-exposure-inventory.json. No ownership or new license over upstream
material is asserted. Public issue/PR records retain their authorship metadata.

The token-aware source-extraction utility is reused from the project data tool,
with its original file hash documented in collection/extractor-provenance.json.
All upstream scoring/helper ASTs are unchanged. Replay creates a minimal class
binding for those exact methods, defers annotations and binds only listed
standard-library dependencies. It does not execute original module or class
initialization and does not require upstream package installation. Explicit
minimal native fixtures are constructed from source/contract evidence; they
are not sampled rows or a claim to reproduce upstream dataset generation.

This data curation is separate from the frozen v10 analysis/report. No analyzer,
model generation, Semgrep scan, RL training or public publication was performed.
