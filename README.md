# Reward Contract Audit

This is the CS6215 course project artifact for **LLM-Proposed Contracts for Static Auditing of Python Reward Functions**. The checker looks for Python scoring paths that award full credit to answers that violate a stated requirement. An LLM and a fixed set of textual rules propose contracts from descriptions. Both feed the same symbolic checker. Semgrep provides a separate source-pattern baseline.

[Report PDF](report/report.pdf) · [LaTeX source](report/report.tex) · [Result index](RESULTS_INDEX.md) · [Public export record](PUBLICATION_NOTES.md)

## Check the reported results

Use Python 3.11 or later. From the repository root:

~~~sh
python3 -B reproducibility/verify_public.py
~~~

The command checks the public file hashes, recalculates reported metrics from saved records, and checks the 20-request extraction ledger. It works offline with the Python standard library. It reads archived outputs without executing a scorer, invoking a model, or running Semgrep.

In the controlled study, the LLM recovered the intended contract on 8 of 8 descriptions that specified an expressible obligation. The frozen textual rules recovered 1 of 8. Both abstained on four unrestricted-text descriptions. The seven additional contracts each applied to the same three known programs, yielding 10 supported alarms and 11 no-alarm certificates in cells where the rules had abstained. The real-project studies leave incremental detection benefit unresolved.

## Where to look

| Path | Contents |
| --- | --- |
| [report](report/) | English ACM report and source |
| [datasets/reasoning-gym-reward-v1](datasets/reasoning-gym-reward-v1/) | Pinned scoring sources, contracts, and observations |
| [experiments/reward-baselines-v1](experiments/reward-baselines-v1/) | Semgrep and symbolic baselines, inputs, and judgments |
| [experiments/reward-contract-extraction-v1](experiments/reward-contract-extraction-v1/) | Pilot prompts, responses, and comparisons |
| [experiments/reward-contract-loop-v2](experiments/reward-contract-loop-v2/) | Explicit Boolean obligations and omission checks |
| [experiments/reward-contract-e2e-v1](experiments/reward-contract-e2e-v1/) | Known-case integration |
| [experiments/reward-external-boolean-v1](experiments/reward-external-boolean-v1/) | HELM policy probe and transfer observations |
| [experiments/reward-contract-controlled-v1](experiments/reward-contract-controlled-v1/) | Controlled policies, extractor source, responses, witnesses, and outputs |

## Execution environment

The reference environment used Python 3.14.3 on macOS ARM64. Repeating a Semgrep analysis requires the pinned Semgrep CE 1.183.0 macOS ARM64 native core, adjacent libraries, and original layout recorded in [the tool record](experiments/reward-baselines-v1/tools/tool-release.json). The controlled rules and symbolic implementation are in the experiment directories. Prompts, request settings, and archived replies are included. The exact underlying model identity and seed were unavailable, so new requests can differ.

The stage READMEs document the original commands. Commands that require the original frozen archive's exact bytes may fail its hash or inventory checks on this public export. Use [the public verifier](reproducibility/verify_public.py) for the published evidence. The export record lists the files affected and their hashes.

Upstream source revisions, license copies, and baseline tool links are listed in [Third-party notices](THIRD_PARTY_NOTICES.md).
