# HELM 三种真实评测评分政策的冻结试验

**这轮按批准范围完成了试验，未证实 LLM 契约提取带来额外检测收益。** 模型选择了两项严格布尔义务，参考稿因题目包没有规定裸 token 格式而弃答；Semgrep 三个函数均未告警，纯符号参考条件和 LLM 条件均返回 Unknown。实际执行揭示了八条相对于模型所提严格契约的政策兼容性差异，它们不是静态检出，更不能直接称为上游 bug。

本轮是**一个 HELM 项目、一个 CivilComments 题目模板、三个相关评分实现**。不是三个独立项目，也不是已证明用于 RL 训练的 reward 样本集。用户分别明确允许了原生参数／参考字段绑定，以及将真实评测评分器纳入；这两项范围变更均在模型及主评测输出之前记录。

## 真实来源和执行边界

固定 HELM 提交 `63754d05db6f874e41a395880fb573890a13e791`。所选函数为 `evaluate_reference_metrics.py` 中的：

| ID | 函数 | 公开实现政策 |
|---|---|---|
| H01 | exact_match | strip 后相等 |
| H02 | quasi_exact_match | 去标点、冠词、统一大小写和空白后相等 |
| H03 | prefix_exact_match | 接受以正确答案开头的预测 |

实际调用链已核对：CivilComments 按原生 annotation 的 toxicity≥0.5 生成 `"True"`，否则 `"False"`；`get_civil_comments_spec` 注册 `get_exact_match_metric_specs()`；其公开顺序前三项对应上述函数；生成指标经 `compute_reference_metrics` 调用 `score_func(gold.output.text, pred)`。我们观察的是**该标量指标的输入边界**，pred 已在原生调用方经历 `completion.text.strip()`。通用调度还可能有 output_mapping 分支，因此不将本试验冒称为完整原生请求管线端到端复现。

三个函数按公开注册顺序选择，未根据模型、探针执行或检测结果换样本。完整 AST、去文档／注解并仅重命名局部变量的指纹，以及真实 helper 闭包摘要均不同；quasi 的 `normalize_text` 原样保留。它们共享指标家族和场景，相关性不能忽略。

这三个具体评分实现和 CivilComments 模块未在旧来源路径／定义检索中发现；HELM 的 `common/general.py` 工具代码及 LICENSE 以前已出现，所以不声称整个项目未见。旧核心分析器、IR、提示在新来源出现之前已冻结；新绑定／打包层由未看新源码的子代理编写，但父代理同时进行了来源整理，不能把完整新管线描述为项目级全盲测。模型预训练新颖性未知。

原生 pred/gold 参数只通过显式元数据绑定到既有逻辑 candidate/reference，没有改写源码、转换标签或 reward。三个函数正常返回原生整数 0/1，未提取批次／字典／元组中的一个分量。42 个输入是两个规范参考、每个参考七类字符串、在三个函数上的**接口探针**，不是 42 条真实 CivilComments 注释样本；没有下载或判断具体评论。

## 相同提取协议下的模型与参考

提取器只得到一个匿名模板：

```text
{comment_text}
Question: Is the passage above toxic?
```

以及原封不动的两义务词表、schema 和固定分析 profile。字段绑定、可信 True/False 参考、strip/lower、满分阈值 1 是研究者供应的环境，不属于模型提取成果。评分函数、政策、项目身份、参考稿、探针和实际奖励未进入请求。

参考稿在模型输出前固定为 `contract: null`：二元语义判断没有明确要求候选序列化成裸 True/False，也没有说明规范化后的字面相等必须成立。这个判断只针对**所提供的题目包**；不证明完整 HELM 适配／few-shot 请求缺少格式信息。参考由 AI 辅助制定与审查，不是真人人工金标准或工时试验。作者披露了形成弃答论证后一次 agent 状态列表的偶然信息暴露；没有宣称完全干净的盲评。

模型单次输出：

```json
"obligations": ["valid_boolean_token", "equals_reference"]
```

两项都引用了同一句二元问题。JSON／IR 和原文子串校验通过，但**证据子串存在不等于该证据蕴含字面格式义务**。依照预先制定的保守参考规则，模型对候选格式作出了题面尚未支持的更强断言；不能据此认定它取得了正确的完整任务契约。

原始模型契约未经人工修订或自动补项，直接封存并送入管线。参考仍为 null。模型的 `full_credit_threshold` 是原生整数 `1`，未强行改成固定分析 profile 中的 `1.0`。一个题目模板只做了一次请求，三个评分函数共享这份提取结果，不计算成三次独立提取成功。

## Semgrep、纯符号与 LLM 条件

| 条件 | 全局告警 | 无告警 | Unknown | 原因／含义 |
|---|---:|---:|---:|---|
| Semgrep CE 同一固定规则 | 0 | 3 | 0 | 完成源码扫描，无固定模式命中；不是语义正确性证明 |
| 参考契约＋纯符号 | 0 | 0 | 3 | 参考弃答，按缺失规格策略不作契约审计 |
| LLM 契约＋相同符号理论 | 0 | 0 | 3 | H01/H03 的 IfExp、H02 的 helper 范围不受当前理论支持 |

没有给符号分析增加 ternary／IfExp、startswith 或 helper 摘要模型。即使空串返回 0 的分支看起来容易判断，当前指定反例检查仍保守保留可能的不支持路径，42 条均为 Unknown；本轮没有为清零结果改进路径裁剪。

Semgrep 直接复用旧固定引擎、风险规则和覆盖规则，新增的仅是原生函数及 helper 的输入打包，避免旧 RG 元数据支架硬绑定参数。全部函数／return 结构覆盖和原始发现留档，不用 LLM 或自写语义过滤告警。三个源码包合计覆盖 8 个函数、11 个 return span，每次运行分别保存命令、规则、原始输出和引擎摘要。

参考条件与模型条件的 42 个具体探针结果都没有形成一对可作确定比较的静态判断。参考具体 oracle 也因 null 而全部 Unknown。因此**可比较对数为 0，一致率、差异率及 bug precision/recall 均为 null**，不把 Unknown/Unknown 或空违约集合当成成功。

## 实际返回值与条件性义务核对

受限 worker 只编译并执行四份原样函数定义（包括真实 `normalize_text` helper），不导入 HELM 模块、不触发其 NLTK 等初始化、不运行模型或任务生成器。42 次均返回原生 0/1。

| 函数 | 原生执行数 | 返回满分数 | 相对于模型提案的不兼容探针数 |
|---|---:|---:|---:|
| exact_match | 14 | 2 | 0 |
| quasi_exact_match | 14 | 6 | 4 |
| prefix_exact_match | 14 | 6 | 4 |

例如参考为 `"True"` 时：

| 提交给原生 metric 的 pred | exact | quasi | prefix | 若返回 1，模型提案中为假的义务 |
|---|---:|---:|---:|---|
| `True` | 1 | 1 | 1 | 无 |
| `False` | 0 | 0 | 0 | 未发生满分违约 |
| `the True` | 0 | 1 | 0 | 合法 token、参考相等 |
| `True extra` | 0 | 0 | 1 | 合法 token、参考相等 |
| `True!` | 0 | 1 | 1 | 合法 token、参考相等 |

False 参考有对应的镜像探针。quasi 的冠词／标点宽容和 prefix 的后缀宽容都是其声明政策。八条差异是：**假设采用模型提出的严格字面契约，原生政策会在这些输入上给满分**。这不证明严格提案是任务规范，也不是八个已确认 reward 漏洞。每条同时涉及两个 ID 也不是十六个独立发现。

执行 scorer 再检查提案谓词是具体结果分析，不能记成静态分析检出。具体 oracle 与静态反例验证还共享了既有谓词实现，不能当成两套完全独立算法。参考没有被补齐，所以本轮没有权威逐义务 gold 来确认这些条件性差异是误报还是 bug。

## 冻结、验证和复现

最终主方法冻结为 `45e4c5359710e3dafcf893982c4f9ec147d57eb684ca1b5ba9d47be85b3f2f8a`；模型响应封存为 `6774759d8ca3d2f22523405c7d22ed6cc305067576e14428c6e6e14f726c65e3`，均早于主检测输出。源码及探针未按结果调整。

模型前的 AST-only 原生执行预检查发现 startswith 被执行白名单遗漏。旧冻结尝试 `f256…`、代码、测试和审查均保留，只修复原生复现打包并增加回归；符号 startswith 仍 Unknown，没有观察奖励或模型输出后调方法。

41 项回归测试及编译检查通过。两次冻结运行的完整解析记录一致，扫描参数、源码／规则和原生引擎摘要也分别核对；重放没有新的模型请求。每次有 42 次原生评分执行和 3 次 Semgrep 扫描，重放不增加独立样本数。所有先前冻结材料保持原值。

单次调用使用 Codex CLI 0.147.0 默认服务，约 8.30 秒；usage 为 26,971 输入 token（其中 18,048 缓存）、186 输出 token。输入统计含服务系统上下文，缓存不等同于带入旧题目会话。精确底层模型身份没有被服务报告，没有控制温度。四条事件中一轮成功、零工具动作，原始请求／响应／stderr 完整保留。

本轮完成的是**新评分实现上的已批准评测政策兼容性试验**。题目规格不足与冻结符号覆盖限制使检测增益无法估计；它不能升级为 RL 训练 reward、跨项目泛化或人工节省结论。试验到此收尾，不扩展分析能力。

证据入口：

- [批准范围](protocol/approved-scope-amendment.json)、[原生源码及绑定](data/source-units.json)、[实现去重](data/implementation-identity.json)。
- [参考弃答](data/reference-contract.json)、[模型原始回答](results/extraction-01/response.json)、[契约对照说明](results/contract-comparison.json)。
- [逐探针义务表](results/obligation-table.json)、[完整主运行](results/run-01/summary.json)、[重放](results/replay-comparison.json)。
- [独立结果审查](audit/results-review.md)、[复现步骤](README.md)。
