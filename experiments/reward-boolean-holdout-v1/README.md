# Boolean holdout eligibility audit

中文结论见 [REPORT.md](REPORT.md)。目录名称记录原计划；**独立测试没有启动**，没有模型／基线成绩。`results/status.json` 明确写为未测，指标为 null。

原计划使用完全冻结的 e2e-v1 提示／profile／schema 与显式义务 v2 接口，挑选至少两个未见、原生 True/False、自有且不重复的真实评分函数。八个概念候选及同提交结构普查均未确认额外合格实现。没有对 Yes/No、0/1、三值状态或集合强制转换，也没有改分析器。

## 离线核验

在本目录运行：

```bash
python3 verify_data.py
```

只用 Python 标准库。脚本核对 collection 冻结文件、122 个原始源码与 Git blob、AST 结构计数、旧实验清单和方法字节，以及所有新指标均为未测。它不导入或执行目标源码、不发网络请求、不调用 LLM、Semgrep 或纯符号分析器。

完整材料包携带此前冻结目录，供相对路径与清单核验使用。原核验环境为 Python 3.14.3/macOS ARM64，跨平台未验证。

## 留存材料

- `planned-comparison.json`：预备的同方法比较计划和固定源码摘要。
- `collection/screening-plan.json`、`screening-results-phase02.json`、`SCREENING.md`：八项具体排除证据；原六项阶段仍保留。
- `collection/census/amendment.json`：在模型／分析器结果出现之前追加的同提交结构普查计划。
- `collection/census/source-manifest.json`、`first-pass-metadata.json`、`answer-field-traces.json`、`census-conclusion.json`：范围、精确源码和答案域线索。
- `collection/dedup-erratum.json`：初版全名 alpha 指纹过强的纠正说明；原冻结结果未覆盖，保守局部指纹另存。
- `collection/archive-exposure-levels.json`：122 个提取／AST 阅读源码与其他仅留在下载归档中的文件分开记录。
- `collection/collection-freeze.json`：来源与筛选材料的冻结摘要。
- `results/status.json`、`audit/selection-review.md`：未运行状态及独立复核。

`census.py` 和整理脚本是一次性材料构建脚本，可能改写整理输出；复核应使用根目录 `verify_data.py`，无需重建冻结数据。

108 是名称后缀 Dataset 的顶层类数，含基类／组合类；75 是其中自有 score_answer 的定义数。文本匹配和答案字段追踪是来源筛查工具，不是任意 Python 返回域的完备证明。结论限定于记录的快照、文件过滤和具体复核，不推断所有版本都缺少布尔任务。

本轮筛查和审校由 Codex 辅助完成，没有新的受测契约提取或人时效率实验。今后不能再把本轮已经阅读的源码称为未见数据。
