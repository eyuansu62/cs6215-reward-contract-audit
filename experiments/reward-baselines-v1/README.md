# Reasoning Gym 固定契约基线刻画

这是一次源码已知的开发性实验：7 个函数版本／契约单元，来自 5 个函数家族、1 个项目。目标是先测清 Semgrep 与有限纯符号检查器的能力边界，再决定是否需要 LLM。本轮只实施两个非神经基线；检测方法没有接入 LLM，代码和审查由 Codex 辅助完成。

结果与解释见 [REPORT.md](REPORT.md)。原始数据位于工作区 `datasets/reasoning-gym-reward-v1`；它的任务描述、上游来源、反例和修复提案状态均保留原冻结版本。

## 固定材料

- `protocol/contracts.json`：5 类任务的满分必要条件、可信输入和规范化规则。
- `protocol/evaluation.json`：单位、三态结果、计分分母与解释限制。
- `protocol/contracts-evaluation-freeze.json`：实现前冻结的契约、评价规则和金标准摘要。
- `method-freeze.json`：主预测前冻结的代码、测试、输入、映射和标签摘要。
- `inputs.json`：两个检测器接收的相同源码、契约和标准库绑定；不含反例、奖励观测、标签或 PR 状态。
- `evaluation/`：仅准备／评分阶段使用的标签、来源映射及独立记账的合成诊断。
- `tools/`：Semgrep 适配器、有限静态路径检查器及合成回归测试。
- `audit/`：独立审查、修复前失败证据的索引及复核结果。
- `results/`：冻结方法的原始命令、输入源码、规则、引擎完整输出、预测、评分与重放比较。

`alarm` 表示告警，`no_alarm` 表示无告警，`unknown` 表示无法判断。Semgrep 无告警只是完成规则扫描；纯符号无告警是在声明边界内的源码证书。两者均不保证任意 Python 程序正确。

## 复现

本次环境为 Python 3.14.3、macOS ARM64，使用工作区已有 Semgrep CE 1.183.0 原生引擎；其版本、下载来源和 SHA256 见 `tools/tool-release.json`。脚本在工作区 `work/semgrep-tool/distribution` 下查找唯一的缓存引擎，并校验固定哈希。必须保留引擎相邻动态库。归档不包含引擎二进制，跨平台复现尚未验证。纯符号检查器只需 Python 标准库。

从本目录运行。现有输出不可覆盖，重复运行时请换一个输出目录：

```bash
python3 run_baselines.py verify
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m unittest -v test_study.py

python3 run_baselines.py predict --output results/local-primary
python3 run_baselines.py score --predictions results/local-primary/predictions.json --output results/local-primary/scores.json

python3 run_baselines.py predict --diagnostic --output results/local-diagnostic
python3 run_baselines.py score --predictions results/local-diagnostic/predictions.json --output results/local-diagnostic/scores.json
```

将新结果与保存的主运行比较：

```bash
python3 run_baselines.py compare --old results/primary-01/predictions.json --new results/local-primary/predictions.json --old-scores results/primary-01/scores.json --new-scores results/local-primary/scores.json --output results/local-primary/replay-comparison.json
```

`compare` 比较全部解析后的分析记录及评分，并另外核对 Semgrep 扫描参数、源码／规则文件实际字节和引擎哈希。只归一化运行目录、引擎路径和计时，不把不同告警归一化成相同结果。它是同机重放检查。

本轮分析不导入或执行目标 reward 函数，也不读取保存反例来作预测。已有数据集的 63 个执行探针是标签验证证据，不是 63 个独立检测样本。`prepare_inputs.py` 是准备脚本；已冻结输入无需重建。不要再次创建方法冻结或修改冻结代码来改善本轮成绩。
