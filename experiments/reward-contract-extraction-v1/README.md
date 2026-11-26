# Description-only contract extraction pilot

中文结论见 [REPORT.md](REPORT.md)。本目录保存六个新题目模板、先于模型输出冻结的 AI 辅助参考、六次单轮提取、逐字段审校及原样冻结分析器的下游结果。本实验没有真实人工标注或人时收益数据。

## 固定边界

- 数据固定在 Reasoning Gym `49b07130b3fcd12f2d064bba7c43869543a0e7e7`；题目内容此前未读，文件名曾列出。三布尔／三非布尔为事先固定的定向选择。
- `collection/blind-task-descriptions.json` 是提取的唯一任务内容。生成器与评分实现不是模型输入；先封存回答，再检查这些实现。
- `reference/` 为 AI 辅助研究者参考和独立审校，不是真人实验。`comparison/` 将实质修订、解释不确定和证据校验问题分别记录。
- 原始回答、校验失败和一次模型前初始化失败均保留。T05 未通过证据校验，未修复后送入下游。
- `tools/downstream.py` 仅作输入投影。实际分析器来自相邻的 `reward-baselines-v1`，规则和代码字节保持原样；不支持的接口保留 Unknown。
- 六任务仅三种 scorer，其中四题继承旧默认 scorer；三个支持投影只对应一个不同检测输入。不是六个独立漏洞样本。

## 校验与重放

在本目录执行。需要 Python 标准库；原实验使用 Python 3.14.3 / macOS ARM64。下游 Semgrep 使用工作区已有 `work/semgrep-tool/distribution` 中固定 CE 1.183.0 原生引擎及相邻动态库；下载地址／哈希见相邻旧基线 `tools/tool-release.json`。归档不含二进制或账号凭据，跨平台尚未验证。

```bash
python3 run_extraction.py verify
python3 run_downstream.py verify
python3 -m unittest -v test_extraction.py
python3 -m unittest discover -s tools -p test_downstream.py -v

python3 run_downstream.py run --condition reference --output results/local-reference
python3 run_downstream.py run --condition llm --output results/local-llm
python3 run_downstream.py compare --reference results/local-reference/predictions.json --llm results/local-llm/predictions.json --output results/local-comparison.json

python3 run_downstream.py replay --old results/downstream-reference-01/predictions.json --new results/local-reference/predictions.json --output results/local-reference-replay.json
python3 run_downstream.py replay --old results/downstream-llm-01/predictions.json --new results/local-llm/predictions.json --output results/local-llm-replay.json
```

输出目录不可覆盖。上述步骤重放已经保存的契约，不产生模型请求，也不执行目标 reward 函数。`prepare` 和 `freeze` 是一次性准备操作；复现无需重新运行，更不能根据结果修改冻结方法。

模型调用由 `run_extraction.py request` 实现，通过 `codex exec --ignore-user-config --ephemeral --sandbox read-only --json --output-schema`、隔离临时目录与无工具事件审计限制输入。实际模型身份未由服务公开；精确响应仅能从保存原始文件复核。重新请求会产生新的、不保证一致的响应并消耗账户额度，且不能算另一次未见任务实验。没有配置 API key、添加模型依赖或复用其他任务的回答。

## 材料布局

- `protocol/`：预先固定的设计、通用 schema 和相同提示前缀。
- `collection/`：选择／题目冻结、上游原件、原生源码单元、AST 与来源证据；`sealed-upstream` 这个名称记录先后顺序，不是额外的操作系统隔离保证。
- `extraction-freeze.json`：提取前代码、参考稿、评分细则与题目摘要。
- `downstream-method-freeze.json` / `downstream-input-freeze.json`：桥接方法及运行前固定输入。
- `results/extraction-01/`：初始化失败；`extraction-02/`：六个已完成模型回合，其中五份严格接收。
- `results/model-response-freeze.json`：原始回合封存；`downstream-*`：两种条件各两次原始记录。
- `comparison/`、`audit/`：逐字段判断、独立审查和限制。

完整归档同时携带前一轮冻结的基线与数据，供其相对路径和摘要校验使用。账号身份、服务底层模型和 Semgrep 引擎不是由归档提供。
