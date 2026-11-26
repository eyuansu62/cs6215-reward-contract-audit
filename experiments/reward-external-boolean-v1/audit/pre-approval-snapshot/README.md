# External Boolean scorer study — preparation pending scope choice

当前状态见 [PREPARATION.md](PREPARATION.md)。用户已经允许仅做参数／参考字段绑定。是否纳入 HELM 的真实评测评分器（非已证实 RL 训练 reward）仍在等待选择，主实验没有运行。

已实现的窄绑定与候选执行 harness 通过合成回归，可离线验证：

```bash
python3 -m unittest discover -s tests -v
```

这些测试使用合成代码或 mocks，不是 HELM 独立检测成绩。不要调用 `request_contract.py request`、`run_study.py freeze/run/worker` 来替代尚未得到的数据类型决定。提取客户端在 `data/dataset-scope.json` 的选择未明确时拒绝发模型请求。

主要文件：

- `native_binding.py`、`binding-method-freeze.json`：仅原生参数／单层字段读取到既有 Term 的映射，旧 v2 代码原样保留。
- `protocol/`：完全复用的提示、schema、profile，以及窄绑定计划。
- `collection/`：固定真实来源、用途、接口、排除证据和 HELM 候选。
- `data/`：候选三个原生函数及真实 helper、一个题目模板、null 参考稿、先声明的接口探针；未进入正式测试。
- `request_contract.py`：固定旧提取校验和同一 CLI 隔离协议，不补模型／参考义务。
- `run_study.py`：来源 AST／哈希核验、受限原生执行、同规则 Semgrep、同能力纯符号／模型条件及三态核对；目前只跑过合成测试。
- `audit/`：绑定、参考弃答、harness 和请求边界的预执行审查；不代表真实案例实验通过。

如果纳入评测评分器，必须先把一项目三指标的范围明确记录，然后在模型输出之前固定数据与方法。不得将有意宽松的 quasi／prefix 匹配直接称为上游训练 reward bug，也不得把 null／Unknown 比较算成正确一致。
