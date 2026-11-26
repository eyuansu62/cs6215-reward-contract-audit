# One-case LLM → explicit Boolean obligations → source check

中文说明与结果见 [REPORT.md](REPORT.md)。这是同一已知 #544 / PR561 开发案例的端到端集成；没有改动原 v2 接口、义务或分析器。

模型单次接收真实题目模板、固定环境和两义务词表，返回完整显式 IR。管线只验证原响应，不从参考契约或类型标签补全义务。所选子集会原样保留；坏响应或弃答对应 Unknown。本次响应选择两个义务，与 AI 辅助参考相同。

## 离线重放

在本目录运行，只需 Python 标准库和材料包中已有前序目录：

```bash
python3 -m unittest discover -s tests -v
python3 run_e2e.py verify
python3 run_e2e.py run --output results/local
python3 run_e2e.py replay --old results/run-01/summary.json --new results/local/summary.json --output results/local-replay.json
```

这些命令不发模型请求、不调用 Semgrep，也不安装依赖。静态检查从相邻 `reward-contract-loop-v2` 导入固定代码，底层 AST 模块继续校验旧哈希；目标评分函数通过现有受限子进程 worker 实际运行六次，仅执行已审阅方法，不导入整包或运行生成器。原验证环境为 Python 3.14.3 / macOS ARM64，跨平台未验证。

输出不可覆盖；无需重新执行 `freeze` 或 `seal-model`。同一模型响应的重放不等于重新获得一次模型结果。

## 模型材料与边界

- `protocol/task.json`：从固定源码 AST 提取的真实题目，只有实例占位符，没有评分代码。
- `protocol/analysis-profile.json`：研究者提供的字段绑定、原生域、可信参考、strip/lower 和阈值；不属于模型提取收益。
- `protocol/prompt-prefix.txt` / `response-schema.json`：固定提示和通用两义务选择格式；允许遗漏、弃答，不要求两个都选。
- `protocol/reference-contract.json` / `reference-expected.json`：先于模型响应固定的已有参考及期望，不提供给模型。
- `results/extraction-01/`：唯一一次成功提取的请求、原始回答、元数据和无工具事件审计。
- `model-response-freeze.json`：封存原始响应；`results/run-01` 与 `run-02`：两次离线下游运行。
- `results/obligation-table.json`：六个版本／反例配对的逐义务结果；`contract-comparison.json` 区分语义一致与数字表示差异。

新模型调用使用已登录的 Codex CLI 非交互、临时只读目录、禁用用户配置／项目文档并审计工具事件；需要独立账户权限和服务连接。精确模型身份未公开，重新生成不保证相同，且会消耗额度。本轮已经完成单次调用；不通过再次调用改善结果。材料包不包含凭据。

模型输出中的整数 `1` 保持原表示，没有改成参考的浮点 `1.0`。义务列表也保持原顺序，未排序或补项。指定反例检查与具体值 oracle 共享义务谓词，因此不是独立实现；先固定的期望和真实返回值另作核对。

本次结论只涉及已设计词表和可信参考下的两义务选择／集成，不代表开放式契约合成、Game of Life 求解、模型检测增益或实际人工节省。所有前序冻结结果保持原值。
