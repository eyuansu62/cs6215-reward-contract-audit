# Explicit Boolean obligations: minimal v2

中文结果见 [REPORT.md](REPORT.md)。这是同一 #544 / PR561 开发案例的最小接口版本，不是新独立数据集。

新增接口明确传入 `valid_boolean_token` / `equals_reference` 列表，只有被启用的义务参与检查。源码字段、候选／参考域、规范化和满分阈值固定；缺失或无法表示时 Unknown，不从自然语言或类型标签补全。

底层 AST／Term／路径理论从原冻结模块导入并校验 SHA256；新消费者只覆盖逐义务证明／反例选择和证据归属。旧分析器、桥接器、Semgrep 规则、数据与所有前序结果保持原样。未增加循环、数值、库、helper、SDK 或任务支持。

在本目录运行：

```bash
python3 -m unittest discover -s tests -v
python3 run_case.py verify
python3 run_case.py run --output results/local
```

已有输出不可覆盖；无需重建方法冻结。运行需要工作区中已保存的前序实验和数据；Python 3.14.3 / macOS ARM64 是原验证环境，跨平台尚未验证。新运行不调用 Semgrep 二进制，只引用既有 source-pattern 基线；不发起新的 LLM 契约提取请求，不增加依赖。

`run` 包含两条数据路径：

1. 静态全局与指定输入检查：从源码 AST/Term 推导，不执行评分方法，不接收观测 reward 或标签。
2. 既有受限 worker 的六次实际评分执行：校验源码身份、隔离子进程／超时，只运行已审阅方法，不导入上游模块、不运行构造器或生成器。

oracle 和静态指定输入核对共享两个谓词实现；它们不是完全独立算法。预先固定的预期表、实际评分返回值和独立审查共同用于核对。全局弱契约仍可能因非法 token 告警；核心区别应看 `False / True` 具体输入是否标记 `equals_reference` 违约。

缺失契约 Unknown 是封装政策，不能当作原生 Semgrep 的能力限制。NoAlarm 只针对启用的满分必要条件，不保证整个任务正确。嵌套旧 formatter 的 v1 方法标签保留，实际义务选择见顶层 v2 方法、编译契约和活动列表。

主要文件：

- `implementation-plan.json`、`contracts.json`、`expected.json`：固定边界、三个契约条件和预期。
- `boolean_contracts.py`、`boolean_checker.py`：两个义务与窄适配消费者。
- `tests/`、`audit/`：回归、审查及保存校验。
- `method-freeze.json`、`results/run-01/`：冻结摘要和新结果。
- `results/obligation-table.json`：逐反例、逐条件、逐义务真值与违约 ID。

这是 AI 辅助开发和审查的接口实验，没有真人工时测量或新的模型收益结论。
