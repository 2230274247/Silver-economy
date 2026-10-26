# 记忆数据分层与证据约束（T07 基线）

L0 为 messages：用户原文不修改；assistant.content 是模型回复正文，开启结构化提取时另存 raw_model_output 保留完整原始 JSON。原文、候选、用量均通过用户/消息编号关联，错误日志不记录正文。

L1 为 memory_facts / memory_sources：MemoryExtractor 校验 JSON、字段长度/类型、允许的类别和原文跨度；key/value/time_expression/state_text 都必须逐字来自本条用户消息的 source_excerpt。无来源内容、编造的医院/严重性/具体日期会被拒绝；明显假设、否定受伤和拒绝记录的表达另有保守拦截。复杂混合表达可能漏提取，不能据单条实测宣称普遍准确率。

- 候选保存为 candidate，confirmed_at 为空，confidence_label=explicit_span。这是来源支持的用户表述，不等同独立核实的事实。
- 默认不开启长期记忆。用户在个人设置明确授权后才合并提取；关闭不删除原文/候选。调用在途时再次锁定用户核验授权，撤回后不新增候选。
- 当前同一次 Provider 请求返回 reply+memories，不额外发提取请求。输出不合格式保留 L0/原始输出和错误状态，不自动花费额度修复。
- 精确重复按用户、Provider、主题/原文和事件锚点摘要去重，新增来源；不同 Provider 不混并。语义重复/冲突更新属 T09。
- extractor_provider / extractor_version 保留首提取来源；ModelUsage.prompt_version 与每条来源消息的请求编号保留各次 Prompt 版本。早期未登记版本留空，不猜测。
- event_at 为 UTC 锚点，event_timezone 当前默认 Asia/Hong_Kong；必须连同 event_precision 解读。“上个月”锚到当地月初只便于索引，不能显示成事情发生在1日。年/月/明确年月日由代码解析，不支持或不确定时间保留表达且 unknown，不补造日期。
- Mock 结果明确标记，默认列表按当前运行模式分开。Synthetic 生成/导入只进入独立测试库；本机 live 验收使用合成账户/经历，并对确切测试候选标记 Synthetic。
- retrieval_allowed 是每条候选的使用许可，后续检索还必须检查全局授权、当前用户、删除/失效状态及 Provider 模式。T08 才实现召回，不能凭字段声称已记住并使用。

L2 目前只有 life_events 结构和来源外键；T10 才实现事件组织与时间线。不得让摘要覆盖 L0，不得把来源已删除/失效的记忆绕经摘要复活。

T09 实现纠错、确认、失效、删除；长期记忆删除与聊天原文删除分别处理，删除记忆后检索/缓存/摘要都不能继续召回。当前只读来源和全局授权已可用，未提供假编辑/删除按钮。

版本迁移：t07_memory 在保留既有数据下添加授权/证据/精度字段；t07_prompt 继续增量添加 Prompt 溯源，避免对已存合成验收数据回退重建。降级只在可丢弃测试库验证。
