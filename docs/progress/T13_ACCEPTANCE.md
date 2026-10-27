# T13：验收审计与调度边界修复

日期：2026-10-27（Asia/Hong_Kong）。本地工程门禁已通过：最终294项后端、78完整UI及12项地点/调度复测。正式验收缺项单独保留；远端SHA/CI待提交后核验。

## 范围与实现

- 按最终目标和CR-001审查已有链路，保留全部原提交。验收矩阵见docs/demos/QA_REPORT.md。
- 补足CR-AC12：已确认出行持久化一次T-2h路线天气复核；车程变化阈值5–60分钟，最短30分钟间隔；可关闭，普通提醒保留。
- 复核按任务的最新目标日期查询天气，区分主提醒/internal_refresh/schedule_change。到达任务达到阈值才重算；明确出发时间不移动。
- 新增增量迁移t13_proactive_updates；开发库已升级，测试库完整迁移与metadata检查运行。没有回退开发库、没有接触ALE_AI_MySQL。
- 补足CR-AC04地点修改：从行程详情创建本人修改草案，不调用模型；重新授权位置、搜索候选/查询路线、信息确认和调度确认。新确认前原提醒保留；确认时同事务取消旧任务待发job并保存新任务与outbox，旧历史和在途状态保留。旧任务版本变化时拒绝替换，重复打开复用草案。
- 时间解析保留香港默认，按任务IANA时区算天气日期；覆盖New_York冬夏偏移。DST不存在/重复时刻要求澄清，不静默选择。H5仍为香港时区界面。
- 修复复核job错过窗口/租约失效时把主reminder标expired/unknown；修复明确暂时失败第二次尝试被错误取消；桥接连接超时改unknown且不自动重试。
- UI回归截图改写入.cache/ui-regression，避免覆盖T11历史截图；新T13证据单独归档。

## 失败与修复证据

1. 初次UI专项因开发库未升级到T13列失败；执行加法迁移后9/9通过，属于配置/迁移准备失败，未删除断言。
2. 新增四项可靠性反例在原实现上全部失败（logs/t13-reliability-red.log）：过期复核影响主提醒、失效租约影响主提醒、明确失败重试被取消、连接超时错误重试。
3. 针对性修复后56项调度/通知/时间/草案专项通过（logs/t13-reliability-green.log）。后续增加阈值/显式出发/改期天气/撤回设备/地点替换专项。
4. 首轮完整门禁285项后端通过；第二轮293项后端通过；完整UI78项通过。最终地点替换变更另跑专项与完整门禁，结果以T13-local.json为准。
5. 既有Starlette/httpx弃用警告保留。未修改锁依赖或弱化门禁。

## 实际命令与证据

- 根目录：.venv\Scripts\python.exe scripts/check.py，严格REQUIRE_MYSQL_TESTS=1。
- services/api：pytest -q tests/test_scheduling.py tests/test_notifications.py tests/test_timezones.py；更早包含test_task_drafts.py。
- apps/mobile：npm run test:ui（360/390/430完整），以及npm run test:ui -- tests/scheduling.spec.ts。
- Alembic：upgrade head/current/check；开发库head应为t13_proactive_updates。
- 日志：logs/t13-full-check.log、t13-full-ui.log、t13-reliability-red.log、t13-reliability-green.log、t13-final-focused.log、t13-release-check.log、t13-location-ui.log（本机忽略）。
- 截图：docs/demos/T13-acceptance-390.png、T13-location-390.png；旧截图恢复原字节。
- 机器可读结果：docs/testing/T13-local.json。提交后的SHA/CI另行固化T13-remote.json。

## 尚未通过的验收

- 高德Key/配额未配置，实际调用0；路线天气为Mock合同验证。
- CR-AC10缺签名Android包、推送配置与真机观察；CR-AC11原生权限入口/拒绝/撤回尚未真机验证。不得标整项目正式验收完成。
- 原任务书AC-01–AC-18逐字内容当前不可得，矩阵明确NOT_TESTED，不重构伪造原条文。已归档最终需求和CR条文可追溯。
- 真实DeepSeek本任务新增0，历史7次/3218输入376输出tokens/估算USD0.00141660保留，非账单。自动回归不耗真实额度。

后续T14：运行与架构说明、备份恢复演练、首次克隆复现、A–E演示说明、已知问题及draft PR；外部验收缺项持续可见。
