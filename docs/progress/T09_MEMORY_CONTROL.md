# T09：记忆控制、纠错与状态更新

记录时间：2026-10-26 23:53:33 +08:00（Asia/Hong_Kong）。本地验证完成；当前提交的 SHA、push 与 CI 在提交后核验，不能预填成功。
前项 T08：`d205546532360551ed35f8aad396eb60ae250e22`，23:08:00 +08:00；远端一致，CI 40346315913 三项 success。

## 目标、方案与修改范围

保留现有页面、聊天和数据库历史，在记忆库提供确认/撤销确认、纠错、逐条AI使用许可、失效和软删除。所有写入由已认证用户发起，先锁用户再锁本人记忆，携带 expected_revision；过期页面收到409，不静默覆盖。

- `app/memory/updater.py`：MemoryUpdater、快照/审计、确定性身体状态与原始证据规则。Repository调用状态更新，不请求额外模型。
- `models/entities.py` 与 `alembic/versions/t09_update_memory_control.py`：新增 memory_revisions，fact revision/value_origin、MemoryUse引用版本；只增表/列及回填默认值，未改写旧迁移、原文或其他数据库。
- `api/v1/memories.py`、`schemas/memory.py`：控制接口及修改记录分页；归属/版本/重复/空值检查。`schemas/chat.py`、`memory/references.py`记录引用时的依据版本，区分用户修改与原文，旧引用注明已更新，已删除记忆不再出现在引用中。
- `memory/retriever.py`、`context.py`、`services/model_chat.py`：当前/历史状态、在途版本复核、规则补全与用量估算时机。显式问过去可读历史，问现在不能用已被新状态替代的旧受伤记录。
- `prompts/chat-memory-v3.txt`：保留v2，明确用户纠错优先、历史状态、恢复对象不明时追问；流水线版本 `chat-memory/v3+state-rule/v1` 如实区分模型与规则。
- `MemoryControls.vue`、`stores/memory.ts`、timeline/index与聊天引用卡：真实编辑/保存/取消/失败重试、修改记录、确认删除和状态说明。删除会清理当前页面的引用缓存，聊天正文原样保留。
- `seed-demo-users.py --ui`、`apps/mobile/scripts/prepare-ui.cjs`、Playwright/helper、配置及鉴权：专用ui_a/ui_b合成账号，18000 Mock服务拒绝运营账号和其旧Cookie，避免回归关闭真实联调账号的授权。

## 数据与用户控制边界

删除是从长期记忆使用链路移除，不等于删除聊天或物理抹除数据库备份。原文/既有AI回复和审计保留；删除后的记忆不在列表、搜索、来源、历史引用和新会话上下文中返回。保留指纹墓碑防止旧原文被自动重新抽取复活；相同内容的纠错冲突返回409，不恢复已删除记录。

手工修改以用户确认为权威，不篡改原始聊天。新回复引用修改时使用对应审计版本的值；旧回复继续显示当时的依据并提示已更新。只确认或允许AI使用不会重新激活失效记录；纠错界面明确告知保存后恢复为已确认，并保持原许可开关。

“上个月”不变时保留最初月份锚点，不因后来编辑漂移；修改时间表达才按修改当日解析，未知仍保留未知精度。原文逐字校验、否定和不确定语气不丢弃。

明确“我的膝盖已经好了”等窄格式可以确定性补全候选；与同部位明确旧状态不一致时，保留两条事实及两次来源，旧状态转historical。左右部位分开；旧事重述不替换当前状态。否定、可能、他人、问句、对象不明不自动推断恢复对象。通用语义冲突仍以用户纠错及后续固定评估驱动，不宣称覆盖全部自然语言。

## 实际命令与测试结果

- 项目 `.venv` Python，`services/api`下执行 `python -m alembic upgrade head`；开发readyz当前为`t09_update`。独立测试库空库/重复升级/降级再升级/metadata check随全回归通过；从未连接ALE_AI_MySQL。
- `python -m pytest tests/test_memory_updates.py tests/test_memory_retrieval.py -q`：首轮40 passed /17.86s。
- `python -m pytest -q`：初步117 passed /48.37s；后续补规则、隔离与费用回归，最终随全门禁129 passed /49.33s，只有既有Starlette/httpx弃用提示。
- `python scripts/check.py`：最终 `logs/t09-check-isolated.log`，安全扫描、5扫描器单测、工作流校验、Ruff/format、129后端、TS/lint/H5 build、diff全部PASS。
- `npm run test:ui -- memory-controls.spec.ts`：初轮6 passed /55.9s；确认、纠错失败保留内容/明确重试、取消、刷新、权限、审计、失效/删除、原文仍在、多用户拒绝，覆盖360/390/430。
- `npm run test:ui`：最终42 passed /2.3m，`logs/t09-ui-isolated.log`；独占5174→18000 Mock、专用UI用户。包含原聊天/输入法/多行/滚动/授权/召回/搜索用例，未删除失败断言。
- 浏览器截图 `docs/demos/T09-controls-mock-360/390/430.png` 与 `T09-recall-isolated-live-390.png`；390截图已实际检查。模拟视口不等于Android真机。

新增后端检查包括审计/原文保留、过期版本409、手工修改依据和旧引用区分、删除后的所有入口/重放/新会话、不可自动复活、多用户所有写入/审计拒绝、空白/超长/重复拒绝、相对时间不漂移、状态两来源、左右隔离、不确定和旧事重述、空抽取规则补全只调用一次、Mock服务拒绝运营身份、已计费但拒绝展示仍保留用量/估算。

## 真实失败、修复与费用（全部保留）

1. `SILVER_LIVE_UPDATE_PHASE=recovery node scripts/smoke-memory-updates.cjs`：1次真实调用，原文“我的膝盖已经好了”保存成功，模型返回空memories，状态断言失败。原始模型JSON和attempt保留；496输入/48输出tokens，1500ms，估算USD0.00020640。没有重发该付费请求。
2. 加入窄格式原文规则及回归后，仅对该已保存的受控Synthetic消息执行确定性修复，来源精确关联，旧伤转历史；没有调用模型或改写原始回复。新事实明确标Synthetic，恢复原授权设置。标记保留`failed_no_retry`并附`repair_status=passed`，不把首次失败伪装通过。
3. `SILVER_LIVE_UPDATE_PHASE=recall ...`：1次真实调用，492/48tokens、1531ms；同时运行的旧UI用例关闭同一账号的授权，安全校验以MEMORY_CONSENT_CHANGED拒绝正文，状态completed_rejected，无自动重试。保守估算USD0.00020520，旧回执估算字段为空；报告按已知tokens重算，不改写回执。修复后所有新回执在隐私过滤前估算。
4. 回归改为独立UI账号并增加服务端身份限制；重跑全部129后端/42UI通过。另开单独attempt `recall-isolated`，不会删除原失败标记：492/49tokens、1389ms、估算USD0.00020640。新登录/新会话真实DeepSeek返回膝盖已好这一合成表述，只引用恢复来源，不引用旧伤；刷新后回复和引用仍在，截图通过。
5. T09真实3次，合计USD0.00061800；项目累计6次，2291输入/261输出tokens，USD0.00100050。均为峰时cache-miss保守估算，非实际账单；包括失败/拒绝，不只统计成功。详情 `docs/demos/T09-live-metrics.json`。自动回归真实调用0，未提高每日10次/20000预留tokens及单次256输出限制。

先前两轮全UI还暴露了固定纠错样例与已删除指纹冲突、旧受伤重述应正确成为历史而非永远candidate的问题。保留39通过/3失败日志；测试改用唯一合成标记，并在专用测试账号内明确准备无当前健康状态的候选场景；重复保护和真实状态逻辑保留，最终全套通过。

## 演示与后续

本机H5：`http://127.0.0.1:5173/#/`。运营演示账号凭据只在忽略文件，界面无模型Key输入。登录后“我的回忆”可操作控制、原文与修改记录；新会话询问当前膝盖状态可检查Synthetic证据。再次发送会产生新的模型费用，截图/已有会话只读查看不会请求模型。

下一任务T10：回忆时间线与事件来源关联；再T10E1/E2生成/固定评估。高德、持久调度、Android真机通知及最终全项目验收仍未实现，不能凭本任务标V0.1完成。

## 事后远端核验（T10固化）

2026-10-26 23:56:30 +08:00提交 `2ce30e51ede2d7f901eb233b5f17f1ef21908f33`，push与远端SHA一致；CI40354267818 api/security/mobile全部success。main仍为初始化SHA，历史未重写。
