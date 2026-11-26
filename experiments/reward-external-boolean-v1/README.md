# HELM scalar evaluation policy study

中文结果见 [REPORT.md](REPORT.md)。用户已经明确纳入评测评分器，并允许仅做原生参数／参考字段绑定。此轮不是 RL 训练 reward 实验；一个场景中的三个相关评分政策共享一份模型提取结果。

参考稿因题目包未声明裸 token 格式而为 null；模型选择两个严格字面义务。两者均未被修订或补全。全局符号判断均 Unknown，Semgrep 三份源码无固定模式告警，不能计算真实漏洞 precision/recall 或把 Unknown 一致当收益。

## 离线校验与重放

在本目录执行，现有输出不可覆盖：

```bash
python3 -m unittest discover -s tests -v
python3 run_study.py verify
python3 run_study.py run --output results/local
python3 run_study.py replay --old results/run-01/summary.json --new results/local/summary.json --output results/local-replay.json
```

这些步骤不调用模型、不安装新依赖。每次 run 在受限子进程中执行原生函数 42 次，并调用现有固定 Semgrep CE 1.183.0 引擎三次。静态分析器自身不执行目标代码。

原环境为 Python 3.14.3/macOS ARM64。Semgrep 需工作区已有 `work/semgrep-tool/distribution` 中固定原生引擎及相邻动态库；归档不含二进制，旧基线 `tools/tool-release.json` 保存下载来源／哈希。纯 Python／固定文件校验和合成测试可在无引擎时进行；跨平台未验证。

无需重新执行 freeze 或提取。旧模型响应已封存，重复生成不保证相同且不能算新的未见任务。`request_contract.py` 只在数据范围明确时执行单次隔离 CLI 请求，沿用旧提取校验／schema／profile，不把参考弃答填成契约。

## 材料与保持性

- `data/`：一个原生题目包、参考弃答、三份精确 source packet、显式 pred/gold 绑定及14 个探针模板（7 类字符串×2 个参考，每函数使用一遍）。探针不是实际评论语料，None 不在此原生调用域内。
- `native_binding.py`：仅参数／单层字段到旧 Term 的映射；旧 IR、谓词、路径理论和源代码未改写。
- `run_study.py`：原生源码 AST／哈希核验、独立受限执行、同原生引擎／规则的 Semgrep 打包、同能力静态对照及三态比较。
- `request_contract.py`：单次新任务提取，原始 IR 类型和义务原样封存。
- `protocol/approved-scope-amendment.json`：批准的评测政策范围，取代原训练 reward 搜索目标中的数据范围；旧搜索计划保留。
- `results/extraction-01`、`results/run-01`、`results/run-02`：原始模型及两次真实执行记录。
- `results/obligation-table.json`：42 个接口探针相对于模型提案的条件性义务结果；不是已确认 bug 表。
- `audit/pre-approval-snapshot`、`audit/pre-model-preflight-revision-01`：审批前准备材料和模型前执行白名单修正的历史快照，均未覆盖。
- `collection/`：其他真实项目的来源筛选、排除理由和固定原件；未纳入项目不算独立评测样本。

具体值 oracle 和静态指定输入核对共享谓词实现。quasi/prefix 的宽松政策不能直接拿严格模型提案判成上游 bug；参考 null 不是否定义务的 gold。完整 HELM 适配／few-shot 提示可能有本题目包未包含的格式证据。

PREPARATION.md 和早期审查文件描述批准／执行前的历史状态；当前结果和正式范围以 REPORT、主冻结及新结果审查为准。不要根据这些结果增加 IfExp/helper 模型或修改冻结方法来改善本轮成绩。
