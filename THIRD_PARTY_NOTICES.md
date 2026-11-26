# Third-party source and tool notices

This repository includes the selected upstream scoring sources, their attribution records and license copies. The notices identify the applicable upstream terms for those materials.

## Sources selected for the reported study

- **Reasoning Gym** — `open-thought/reasoning-gym`, source snapshot `49b07130b3fcd12f2d064bba7c43869543a0e7e7`, plus the two recorded proposed-repair commits. Its retained upstream root license is [Apache License 2.0](datasets/reasoning-gym-reward-v1/upstream/main/LICENSE). Original license provenance and module/AST/source URLs are in the dataset collection records. Root-license presence is not a separate license determination for every vendored member of the complete downloaded source archive.
- **HELM** — `stanford-crfm/helm`, selected snapshot `63754d05db6f874e41a395880fb573890a13e791`. The exact current [Apache 2.0 license copy](experiments/reward-external-boolean-v1/collection/scalar_evaluators/stanford-crfm__helm/LICENSE) and [its source hash/URL](experiments/reward-external-boolean-v1/collection/scalar_evaluators/stanford-crfm__helm/license-provenance.json) are retained. Original metric/helper/caller source is unchanged. This project studies the published metric behavior; it does not claim ownership of those implementations or that they were used for RL training.
- **Semgrep CE** — existing baseline tool, pinned native engine 1.183.0. The binary/wheel is not redistributed in this preparation. [Release metadata](experiments/reward-baselines-v1/tools/tool-release.json) records the official distribution URL, platform and wheel/core hashes. Consult the upstream distribution's own license terms when obtaining it. The project-authored adapters and pattern configurations are separate from the original engine.

## Screening provenance

Candidate-project source copies and the bulk census tarball stay in the local archive. This export retains their screening and revision records. The following files identify the source projects and fixed revisions.

- [External Reasoning Gym-style screening](experiments/reward-external-boolean-v1/collection/rg_style/source-review.json)
- [Native reward candidates](experiments/reward-external-boolean-v1/collection/native_rewards/candidate-sources.json)
- [Scalar-evaluator pins](experiments/reward-external-boolean-v1/collection/scalar_evaluators/)
- [Reasoning Gym census source manifest](experiments/reward-boolean-holdout-v1/collection/census/source-manifest.json)
