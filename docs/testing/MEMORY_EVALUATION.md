# 固定题集与长期记忆评估

## 固定输入与客观标准

`tests/memory_eval/fixtures/suite-v1.json` 是在首次排名评估前冻结的独立事实与答案：
SHA-256 `a15c8558b7416f6985aa0afa4301ee3788fe05cc15a9a945bdb70cf9747193c4`。
配套 SHA 文件及单元测试固定该值；构建脚本拒绝用不同内容覆盖 V1。
脚本不导入检索器、数据库或答案生成器，不根据结果生成预期答案。
若以后新增题集，另建版本，不能修改失败用例或用更容易的题替代它。

- 310 个用例、246 种不同问法；180 个有来源标准答案，130 个应明确承认未知的用例。
- 覆盖精确、语义改写、换会话/重登录、当前/历史矛盾、用户纠错、删除、隔离、无效状态、未知细节和性能。
- 100 条受控事实，A/B 各 50。使用现有确认、纠错、删除、失效、许可及身体状态更新服务形成状态，保留原文与来源。
- 其余 N−100 条使用既有 `synthetic/v1` 生成器；每档总数 N 为 100、1000、10000、20000，人均为50、500、5000、10000条。相同受控事实和问题不变。
- 冲突对必须同属一人，实际 A/B 分布略有不同：100档50/50，1000档501/499，10000档5001/4999，20000档10001/9999；不能假定平均数就是每人的实际条数。
- 所有人名、生活事件、原文都是 Synthetic；生成器中的冲突标注不等于模型冲突识别成绩。

噪声种子由冻结题集 SHA 导出，年份/分布固定；各档噪声并非嵌套前缀。
旧版JSON字段 `per_user_memories_before` 是算术人均数，早期HTML曾误标为“每用户”；此显示错误单独记录，评分、题集和语料不因修正标签改变。新报告另外列真实 `per_user_memory_counts`，基线只读JSON保留。
只在白名单 `silver_memory_demo_v01_test` 内创建独立合成账号，禁止指向开发库、ALE_AI_MySQL 或任意外部数据库。
凭据留在被忽略的 `.cache/memory-eval/benchmark-*`，不写入报告。
重复准备核对事实/来源快照，拒绝覆盖已变更数据；原文及题集不会因新增聊天流量改变。

## 实测链路与评分

评估先走真实 MySQL `MemoryRetriever`/`ContextBuilder`，再走实际 FastAPI 登录、新会话、发送、来源持久化及刷新读取。
跨会话组实际退出并重新登录。批量 Provider 强制 Mock，同时阻断真实 HTTP 传输，不能继承运营真实模型模式。

| 指标 | 明确口径 |
|---|---|
| Recall@5 | 180 个正例中，全部指定来源记忆均在前五的比例 |
| Top-1 | 正例中第一条检索结果属于指定来源的比例 |
| 回答正确率（Mock） | 310 题：正例必须包含全部独立答案组并引用正确来源；纠错题还必须引用 user_edit 版本。负例须明确承认未知 |
| 冲突正确率（Mock） | 40 题的答案与来源通过，且未召回题目禁止的旧状态 |
| 无依据回答代理率（Mock） | 无接口错误的未知题中，未明确承认未知的比例；同时报告分母，不能冒充真实模型通用幻觉率 |
| 跨用户/删除召回 | 检索及持久引用的真实归属/删除状态检查，不能只看回复文字 |
| 性能 | 检索 P50/P95、检索 SQL 累计次数/执行时间；聊天接口 P95 另列，使用 Mock |
| 并发 | 4 个线程、A/B 各 10 问重复 4 次，共 80 次真实 SQL 检索；不是 80 个付费对话 |
| 资源 | Python CPU、评估墙钟、评估增量分配峰值、进程生命周期工作集/峰值、事实文本字节数 |

门禁：Recall≥90%、Top-1≥80%、冲突≥95%、零越权/零删除召回、检索P95≤2000ms、未知题正确拒答、上下文≤12000 UTF-8字节/5条、零真实模型调用、无事实漂移、完整题集、无接口错误。
模型 Prompt 未改版的运行也保留源代码哈希；基线和修复报告分别保存，禁止覆盖旧运行。

## 复现命令

在项目根 PowerShell，已配置独立测试 MySQL 时运行：

```powershell
.venv\Scripts\python.exe scripts/evaluate-memory.py --label new-unique-label --scales 100 1000 10000 20000 --require-targets
.venv\Scripts\python.exe scripts/audit-memory-results.py new-unique-label
$env:PYTHONPATH='services/api'
.venv\Scripts\python.exe -c "from app.memory.eval_report import write_report; print(write_report('docs/testing/memory-eval-v1/new-unique-label-verified.json','docs/testing/memory-eval-v1/baseline-v3.json'))"
node scripts/inspect-memory-report.cjs new-unique-label-verified
```

输出 `docs/testing/memory-eval-v1/<label>.json` 和离线 HTML。HTML 无 CDN、模型调用或遥测，支持规模选择、指标比较和逐题失败查看。
`--limit` 仅用于试运行；完整题集门禁会失败，不能当作正式通过。
同名输出拒绝覆盖；中途异常保留已测规模，状态不会伪装成通过。

不要与完整 pytest 并行执行。既有 `test_database.py` 会对独立、可丢弃的测试 schema 做 downgrade/upgrade 演练并清空其中的 Synthetic 数据；开发库不受影响。
测试后评估器按相同固定输入重建，核对初始事实/来源快照后再比较。

## 质量边界

这是有限、可复现的中文生活记忆题集，不代表所有自然语言场景。答案标准检查闭合事实组和来源，不是通用自然语言矛盾判定器。
Mock 只引用实际检索事实或承认未知；它没有测量 DeepSeek 的开放式生成质量、一般知识或候选抽取准确率。
真实 DeepSeek 少量样本另见 T06–T09 记录，不能用这些旧样本声称新规则的真实端到端验收已完成。

SQL 基线使用可审查的中文词项、有限同义词、必要字段/人物约束和有效性过滤，没有向量索引或付费查询改写。
`query.py` 的字段规则是保守必要条件，不是完整语义证明；可能遗漏未列出的同义表达。多人物、多事实组合可能保守漏召回，复杂归属、否定及多跳推理仍需额外独立样本。
性能是本机测量而非线上 SLA；并发仅测检索，资源仅测 Python 进程，不是 MySQL/整机全面性能监控。
所有图表都区分 Mock、真实服务及未测项；高德、持续调度、Android 通知仍按 T11 的独立验收推进。
