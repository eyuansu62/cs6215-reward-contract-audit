# 获批评测指标实验：运行前独立审查

结论：通过，无阻塞项。用户明确回复“纳入试一下”，数据范围与原多项目训练 reward 目标的差别已另行修订；旧准备审查原样保留。模型和主实验尚未运行。

固定 HELM 提交的三个原生评分函数及 normalize_text helper 与原件 SHA／AST 一致。三个函数在去注解／文档及保守局部 alpha 表示下不同，与此前 RG 的 75 条自有 scorer 记录（71 个唯一保守指纹）无碰撞。pred/gold 只作原生标量绑定，源函数没有改签名、改编码或转换返回值。

来源链核对：CivilComments 把 toxicity≥0.5 的参考写为 True，否则 False；PassageQuestionInput 的默认前缀与换行构成所留题目模板；civil_comments run spec 注册 get_exact_match_metric_specs，其前三项依次为 exact、quasi exact、prefix exact；BasicGenerationMetric 到 compute_reference_metrics 的映射和 score_func(gold.output.text, pred) 调用存在。实际 metric 边界位于 completion.text.strip 后。通用调度另有可选 output_mapping 分支，本实验不据此声称已复现完整原生请求／few-shot 管线。

旧核心、IR、提示和 schema 早已冻结；新绑定作者未读新指标源码，但整个新管线冻结是在来源整理之后，不称完全盲的项目 holdout。HELM 项目以前已有 common/general.py 暴露，当前具体指标／场景路径与定义未在记录的旧路径检索中发现；预训练新颖性没有保证。

模型提示、schema 和 profile 与旧 e2e 字节相同。只提供匿名题目、占位符、固定环境与两项选单，未提供源码／policy、标准答案、反例、奖励或参考选择。题目没有候选 token 格式，研究者参考保持 null。参考作者的 agent 摘要偶然暴露及本审查者此前看过通用指标定义的事实均保留，不假称真人或完全盲的金标准。

40 个合成回归和编译检查通过，另有 8 个绑定检查。新的完整方法与输入 21 项摘要已核对，先于模型输出冻结。Unknown oracle 不计一致；条件文件须对应原始封存模型回答；null 和未选择义务不会被补入。没有调用实际项目评分、模型或 Semgrep 来完成本次审查。

三个指标是一项目一任务的相关评测政策，不是 RL 训练 reward 或三个独立项目。宽松匹配可能完全符合指标自身政策，不能直接贴上 bug 标签。冻结分析器不支持的 IfExp／helper 保留 Unknown。后续实际输出、重放和报告仍需结果审查。
