# V0.1 验收证据与未通过项

日期：2026-10-27，Asia/Hong_Kong。T13 工程验收进行中，结果以专项记录及最终回归为准。
状态含义：PASS=实际代码/数据库检查；MOCK_PASS=实际应用链路配合 Mock 第三方；LIVE_PASS=实际第三方证据；BLOCKED_PROVIDER_CONFIGURATION=缺外部准入；NOT_TESTED=未验证或证据不足。

## 原任务书追溯缺口

T00 已读取的原任务书目前在用户原下载路径缺失，仓库未保存逐字原件或 AC-01–AC-18 的完整条文。
不能凭已实现功能反向编造这 18 项的定义。以下保留全部编号并明确未核验；下方 R 表独立核验用户最新明确需求，不声称代替原 AC 条文。

| ID | 状态 | 证据/缺口 |
|---|---|---|
| AC-01 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-02 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-03 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-04 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-05 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-06 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-07 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-08 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-09 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-10 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-11 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-12 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-13 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-14 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-15 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-16 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-17 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |
| AC-18 | NOT_TESTED | 原条文当前不可读取，无法逐字比对；已归档的明确需求另见 R 表。 |

## 已归档明确需求

| ID | 范围 | 状态 | 可检查证据及限制 |
|---|---|---|---|
| R01 | 独立 MySQL、迁移、科研数据库隔离 | PASS | tests/test_database.py、config.validated_database_url；仅项目双库/13306 |
| R02 | 登录、退出、可撤销身份 | PASS | tests/test_auth.py、mobile/tests/auth.spec.ts |
| R03 | 消息原文先存、回复关联、历史分页、刷新 | MOCK_PASS | tests/test_chat.py、mobile/tests/chat.spec.ts；真实证据另见 R04 |
| R04 | 真实 DeepSeek H5 对话与刷新 | LIVE_PASS | T06-live-metrics.json、T06-deepseek-live-390.png；历史单次97/13tokens，不表示本轮新调用 |
| R05 | 授权后候选提取、来源与时间精度 | LIVE_PASS | T07-live-metrics.json、test_memory_extraction.py；只证明有限合成样本 |
| R06 | 重新登录/新会话记忆召回 | LIVE_PASS | T08-live-metrics.json、T08-retrieval-live-390.png；有限历史真实样本，最新代码另跑Mock回归 |
| R07 | 恢复优先、旧伤历史与新状态 | LIVE_PASS | T09-live-metrics.json完整保留首次失败/修复/重测；test_memory_updates.py |
| R08 | 确认/纠错/失效/删除、来源与审计 | MOCK_PASS | test_memory_updates.py、test_memory_retrieval.py；删除记忆不等于删除原聊天 |
| R09 | A/B消息、记忆、任务、设备、导出隔离 | PASS | test_chat.py/test_memory_updates.py/test_scheduling.py/test_notifications.py/test_privacy_export.py |
| R10 | 100/1000/10000/20000规模与310固定题 | MOCK_PASS | testing/memory-eval-v1/t11a-v1-verified.json及HTML；真实SQL、Mock答案，非真实模型开放式准确率 |
| R11 | Prompt版本/来源、有限上下文 | PASS | prompts/README.md、test_models.py/test_task_drafts.py/test_memory_retrieval.py；最多5记忆/12KB |
| R12 | 紧凑输入、IME、多行、失败重试/去重 | MOCK_PASS | mobile/tests/composer.spec.ts、chat.spec.ts；360/390/430，模拟软键盘不等于Android真机 |
| R13 | 后端密钥、预算、幂等、脱敏 | PASS | test_models.py、scripts/security_scan.py；前端不配置Key，测试阻断真实HTTP |
| R14 | 确定性来源时间线 | MOCK_PASS | test_memory_timeline.py；高级叙事摘要延期，不补造日期 |
| R15 | 本人导出与授权撤回 | PASS | test_privacy_export.py、mobile/tests/privacy.spec.ts；JSON为用户导出，不可冒充数据库备份 |
| R16 | 真实高德路线与天气 | BLOCKED_PROVIDER_CONFIGURATION | Key未配置；Provider合同Mock测试通过，实际调用0 |
| R17 | 持久调度/变化刷新/生命周期 | MOCK_PASS | test_scheduling.py、test_notifications.py、mobile/tests/scheduling.spec.ts；供应商Mock不证明手机送达 |
| R18 | 首次克隆、备份恢复、运行交付 | NOT_TESTED | T14待实际演练，不能以文档存在作为通过 |

## CR-001 扩展矩阵

| ID | 状态 | 实际证据/未验证边界 |
|---|---|---|
| CR-AC01 | MOCK_PASS | test_task_drafts.py缺项追问、无有效job；真实意图样本见testing/T11A-live.json |
| CR-AC02 | MOCK_PASS | test_maps.py/test_scheduling.py、三视口卡片，参考来源/时区/到达公式；高德真实未测 |
| CR-AC03 | MOCK_PASS | scheduling.spec.ts确认后刷新真实MySQL任务；保存、调度、送达分开 |
| CR-AC04 | MOCK_PASS | 时间修改即时换revision；地点修改通过replacement-draft重新授权/查路线/核对/确认，同事务取消旧任务未来job并建立新任务；新卡未确认前原提醒保留。test_scheduling.py及scheduling.spec.ts |
| CR-AC05 | MOCK_PASS | test_scheduling.py取消未来job，已提交服务商仍保留在途状态 |
| CR-AC06 | MOCK_PASS | test_maps.py失败/授权撤回；普通提醒无车程/天气且真实保存；设备定位不采集 |
| CR-AC07 | MOCK_PASS | 持久Worker重启/租约/错过窗口，T11C实进程记录与test_scheduling.py |
| CR-AC08 | MOCK_PASS | 确认幂等；明确429/5xx有限重试；超时unknown不自动重发，专项反例 |
| CR-AC09 | PASS | task草案/行程/通知/设备列表、详情、修改/取消/撤回均按认证用户过滤 |
| CR-AC10 | BLOCKED_PROVIDER_CONFIGURATION | 未有签名App、DCloud/厂商推送与真机观察；H5或桥接success不能替代 |
| CR-AC11 | NOT_TESTED | 后端denied/撤回与不发送有测试；Android权限入口/系统撤回未真机验证，平台适配器尚未接入页面流程 |
| CR-AC12 | MOCK_PASS | 一次T-2h复核、5–60分钟阈值、30分钟最短间隔、关闭偏好；失败/过期复核不影响主提醒；真实高德未测 |
| CR-AC13 | PASS | 提交前安全扫描、暂存差异与截图审查；无实际密钥/设备ID/家庭地址入Git，只有Synthetic |

## 计算专项

- 香港与America/New_York冬夏偏移；DST缺失/重复时间返回待澄清，不静默选择。
- 到达扣车程/接驳/弹性，明确出发不重复扣车程；跨午夜/跨年。
- 过期目标/提醒、负缓冲拒绝；天气超过范围或日期不匹配不建议带伞。
- 非香港时区目前为服务层测试覆盖；普通H5输入与显示仍以香港为默认，没有用户时区设置，不宣称国际化产品已交付。

## 当前问题清单

1. CR-AC10真实Android后台通知未通过，完整V0.1不能标已验收。
2. 高德真实Key及商业配额未配置，路线/天气只有Mock合同验证。
3. 原AC-01–AC-18条文缺失，无法逐条核验。
4. Android权限登记/系统撤回的页面集成与真机测试待完成；原生适配器文件存在不等于可用功能。
5. 已安排任务的地点/交通修改采用重新核对卡，确认后替换原任务。已提交到供应商的在途通知不能保证撤回；详情保留该状态。
6. uni-app锁定依赖审计风险见DEPENDENCY_REVIEW.md，未宣称生产安全审计通过；无HTTPS生产部署。
7. Synthetic固定题成绩不覆盖一般语义、多跳推理或真实模型开放式幻觉率。
