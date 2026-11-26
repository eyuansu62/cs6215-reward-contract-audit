# One-case contract-sensitivity feasibility check

中文结论与预期结果表见 [REPORT.md](REPORT.md)。这是已知 Reasoning Gym #544 / PR561 的开发验证，不是新独立测试集。三个契约是主动构造（AI 辅助）的消融；没有新的模型请求。

新增文件只负责案例、已知具体输入的 oracle、既有 worker／接口的调用与结果记录。评分函数源码、分析器、规则和上一轮桥接器均未改动。

在本目录运行：

```bash
python3 run_case.py verify
python3 -m unittest -v test_case.py
python3 run_case.py run --output results/local
```

输出目录不可重复使用。不要重建已有 `method-freeze.json` 来覆盖实验记录。

运行依赖同一工作区内已经冻结的 `datasets/reasoning-gym-reward-v1`、`experiments/reward-baselines-v1`、`experiments/reward-contract-extraction-v1`，以及已有固定 Semgrep CE 1.183.0 macOS ARM64 引擎及相邻动态库。无新依赖。跨平台未验证。

`run` 分两步：

1. 在带超时及既有 AST／命名空间检查的子进程中，复用旧数据集 worker 执行两个已审阅的纯评分方法，每个三个已知输入；不导入整个上游包或运行构造器／生成器。
2. 用原样桥接器和分析器运行三种契约条件，记录实际输入哈希与补回的相等条款。该步骤不执行目标代码。

具体 oracle 结果与静态全函数输出分开记录。`banana` 控制例用于说明弱契约也可能有另一种违规输入，防止把全局告警不变错误解释为契约无作用。缺失规格 Unknown 是接口政策；0 分不触发满分事件这一事实没有不确定性。

先冻结的规范文件：`case.json`、`contracts.json`、`expected.json`、`inputs.json`、`archived-observations.json` 和 `method-freeze.json`。原始输出位于 `results/run-01`，独立复核位于 `audit`。
