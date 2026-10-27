# T11A：出行意图、缺项追问与持久确认草案

状态：PUSHED_CI_FAILED；功能829bbc6530784175878f3eba0cd11df388c0251d已推送/远端一致，2026-10-27T10:51:20+08:00。首轮CI40440860292 api/security通过，mobile55通过/2失败，独立返修中；不标任务正式完成。提醒/地图/真机验收未完成。
前项T10E2功能b3903de及修复e38b2c173c55c127db90dd975fc72587468d38d9已推送/远端一致；CI40417316422全部success。首轮40414362100失败历史保留。

## 本任务范围与验收

沿用现有聊天、MySQL、用户身份及H5样式。单次模型请求同时返回回复、当前明确事实及最多三条任务草案，不再单独发意图提取请求。
“明天上午十点去张阿姨家，提醒我”应生成有来源的草案，询问到达/出发、出发地和交通方式；“十点到，打车，从我家出发”在同一会话补充原草案。
支持编辑、信息确认、暂不安排、刷新恢复、版本冲突及A/B隔离；重复发送和信息确认不得重复建草案。

当前阶段确认的是草案信息，不是提醒调度授权。UI/API必须明确`not_scheduled`，不创建旧reminders或任何通知job。
T11B核实地址/路线天气、T11C计算出门时间并在新的明确确认后安排任务；不得在后续上线时偷偷调度这些旧信息草案。

## 实现计划、数据与风险

- `app/tasks/intent.py`、`time_parse.py`、`repository.py`、`schemas/tasks.py`：候选原文校验、相对日期参考时间、UTC持久化、有限中文时刻、草案/信息确认、来源字段和版本控制。
- `models/entities.py`及`t11a_draft` Alembic：仅新增task_drafts及用户/会话/消息归属外键和索引，不修改/删除旧表，不碰ALE_AI_MySQL。测试schema会按既有迁移测试清空，开发库只做增量upgrade。
- `api/v1/tasks.py`、聊天序列化/ModelChat/Provider：原消息先保存、一次结构化请求、预算共享、原文来源/用户归属、持久响应及分页历史附带最新草案。
- `TaskDraftCard.vue`、`stores/task-drafts.ts`、`platform/task-time.ts`及既有聊天页面/状态：聊天内可编辑卡、加载/错误/防重复、明确尚未安排；保留紧凑输入及原Muse风格。
- 使用现有平台适配器的POST编辑操作，避免为H5单独引入浏览器请求代码。用户归属只取登录身份，客户端不得提供user_id或计算后的车程/天气/提醒时刻。

假设：当前演示按香港/北京时间（UTC+8），明确显示在卡片；以原消息的本地日期解释“明天”，缺上午/下午时不猜测。其他时区/DST在后续时间服务扩展并验收，未声称已支持。
风险：模型字段猜测/错指草案、JSON截断、在生成中被手动编辑、相对日期跨日和未确认被当已执行。通过逐字来源、服务端版本/权限/时刻校验、原文保留和无调度写入控制。

## 额度与Prompt

普通聊天默认输出上限256保持。结构化任务默认`DEEPSEEK_TASK_MAX_OUTPUT_TOKENS=512`（可配置256–1024），仍只调用一次，纳入原每日10次/20000保守预留token预算；上限不是实际消耗，不自动重试。
JSON对象、提示包含JSON及合理输出上限依据[DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)；文档也提示空输出/截断风险，失败保留原文，不反复付费重发。
保留`chat-memory/v3`旧文件。新增`task-intent/v1`组件和组合流水线`chat-task/v1`，普通记忆路径不替换；相关回归及固定记忆评估仍需实际重跑/比较，不能预宣称无回归。
批量全部Mock/禁止真实HTTP。已有Key可在专项/完整门禁后做一次有标记的真实出行草案样本，使用一次性本机尝试记录防重，未执行前不得报告真实接通。

## 当前证据

- 初次24项后端测试通过，扩展最大Unicode输入后25项通过；`logs/t11a-backend-initial.log`、`logs/t11a-backend-v2.log`。
- 最大Unicode测试初稿缺json导入，已修正测试设置；不把它写成产品输入丢失漏洞。完整输入/12000字节预算断言实际通过。
- 前端初次类型检查发现Map值推断及平台适配器不开放PATCH，已修正为明确Message类型及沿用POST编辑；正进行实际H5验证。
- 提醒调度、地图天气、Android通知仍未实现，不以草案保存冒充成功通知。

## 实际验证（2026-10-27，Asia/Hong_Kong）

- `.venv\Scripts\python.exe scripts/check.py`：230后端测试、5扫描器测试、迁移升/降/重复升级、Ruff、TypeScript、ESLint、H5生产构建及diff检查PASS；`logs/t11a-check-final.log`。新增任务相关33例，包括缺项/相对日期跨日跨年/不猜AM-PM/过期时刻/多事项/无来源猜测/多用户/重复请求/共享预算拒绝/混合当前事实与未来计划/历史回忆不误建任务。
- `npm run test:ui`：57项PASS，360/390/430视口，`logs/t11a-ui-final.log`。随后为卡片显式补“北京时间”标签，重跑任务卡9例和前端门禁，结果见`logs/t11a-ui-cards-final.log`。卡片编辑、错误保留、503、重复点击只写一次、确认/暂不安排、刷新及B用户404均使用实际MySQL/API。
- 新增Alembic`t11a_draft`在开发库增量upgrade/check通过，迁移前后messages804、memory_facts144、model_usage380、conversations402全部行哈希相同；`docs/testing/T11A-migration.json`。这是迁移时快照，随后UI/联调正常新增合成数据，不要求持续计数不变。
- `SILVER_LIVE_SINGLE_REQUEST=1 node scripts/smoke-task-draft.cjs`：一次真实DeepSeek请求PASS；`docs/testing/T11A-live.json`。输入带Synthetic标记，生成张阿姨家草案并准确追问到达/出发、出发地、交通方式；通过H5手动补字段、确认信息、刷新恢复，没有第二次模型请求。
- 只读SQL用量核对`docs/testing/T11A-usage.json`：本任务927输入/115输出tokens、1827ms，估算USD0.00041610，非账单；历史累计7次、3218输入/376输出。6次旧估算USD0.00100050加本次合计USD0.00141660；没有调用高德或推送。
- live测试用户reminders行数0，所有草案not_scheduled。真实截图`docs/demos/T11A-live-390.png`已实际视觉检查，未用Mock截图冒充真实模型。
- `.cache/t11a-live-smoke.json`先于发送持久写入，脚本拒绝再次执行；未删除或覆盖旧尝试标记。服务端仍统一日限10次/20000保守预留tokens，普通输出256、任务JSON输出512，不自动重试。
- 再次显式执行live脚本，在读取凭据和启动浏览器前被已有attempt拒绝；`logs/t11a-live-replay-guard.log`，不是再次发送后失败。
- `.venv\Scripts\python.exe scripts/evaluate-memory.py --label t11a-v1 --require-targets`：原封不动310题/246问法，100/1000/10000/20000四档全部门禁PASS，Recall@5/Top-1/Mock回答/Mock冲突均100%，泄漏/删除召回/错误0；P95分别213.109/158.113/217.044/503.028ms。每档4线程80请求亦通过，新增真实模型0；原始日志`logs/t11a-memory-eval.log`和`t11a-v1.json`保留。
- `scripts/audit-memory-results.py t11a-v1`独立SQL核对每用户数量、初始/最终事实与来源快照及原报告字节SHA，通过；`t11a-v1-verified.json`。`docs/testing/T11A-memory-comparison.json`逐档比较旧rules-v3-verified，全部质量指标一致，未换题/改答案；延迟有本机负载差异，不宣称性能提升。新旧报告同保留，离线HTML为`docs/testing/memory-eval-v1/t11a-v1-verified.html`。

## 演示与限制

H5：`http://127.0.0.1:5173/#/`，API：`http://127.0.0.1:8000`。现有运营合成账号可在历史会话查看本次“明天上午十点…”真实草案，或编辑卡片/刷新；读取、编辑、信息确认都不消耗模型额度。新发送聊天会按后端DeepSeek设置计费。

新任务默认紧凑摘要，展开补充或修改信息；缺项时确认禁用，失败保留表单并提供重新读取。以原文、来源消息及手工修改证据追溯，不改写L0。已经确认信息后修改会重新变为待核对；暂不安排后不再编辑。

当前日期/时刻解析为有界中文和24小时表达，不承诺任意自然语言、其他时区或夏令时。模糊“十点”需要补上午/下午；“我家/张阿姨家”仍是未经地图核实的标签。取消/完成执行任务、路线/天气、持久Worker、真实Android通知按T11B–E继续，不属于本任务完成声明。

## CI返修：快速改值后立即保存

首轮CI在390/430视口的同一场景失败：将提前量从-1改为30后立即保存，表单仍按旧值报范围错误，没有发出预期503测试请求。`logs/t11a-ci-failed.log`保留诊断。

依据锁定uni-h5的useValueSync/triggerInputFn中100ms节流，新卡片没有复用已有composer/memory编辑器的原生输入同步。新增同一事件循环内连续输入-1/30并立即点击保存的确定性反例；首个较弱反例未复现，`t11a-input-throttle-red.log`保留，通过进一步固定节流窗口后`red-v2.log`实际失败。

修复仅TaskDraftCard五个输入绑定现有bindComposer、关闭/重建/卸载时释放监听；小程序/App仍使用原uni-app输入生命周期。没有修改后端、Prompt、评分、阈值或增加测试sleep/retry。确定性反例修复后通过（green.log）；完整57UI/2.7m、Vue/测试TypeScript、Lint/H5构建与安全复验PASS，`logs/t11a-ui-fix-final.log`。本轮修复真实模型新增0，不重复付费live，也无需重复未改变的记忆批量评分。修复提交/远端/CI随后核验。
