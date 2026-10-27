# T11C：确定性时间与持久调度

状态：LOCAL_PASS_PENDING_REMOTE。前项 T11B `c44766fa863f968463099976faab6f4c35e8cc01` 远端一致，CI `40445595994` 全部 success；其真实高德仍为 LIVE_PENDING，不能据此宣称真实出行链通过。

## 目标、实现边界

把草案和路线参考推进为真正持久的后台任务。只由Python确定性代码计算，LLM不决定提醒时刻或执行确认。沿用现有MySQL、身份和H5卡，不增加另一套数据库/队列/Agent。

到达语义：出门=目标到达-车程-接驳缓冲-弹性缓冲；提醒=出门-用户提前量。出发语义：出门=用户指定出发，不能再减车程。普通时间提醒不虚构车程/天气，可在服务失败时明确选择该模式。展示完整日期/时区、可编辑缓冲和提前量。

用户必须在新的可编辑计算预览上明确“确认并安排提醒”；信息confirmed和所有旧草案不能自动转成调度。接口以已认证用户、预览/草案版本与幂等键复验，过期路线/过时时刻/不完整计划不能安排。跨日出发需核对目的地天气日期，不能误用前一天预报。

## 预计文件与数据库影响

- `app/tasks/`计算/确认/生命周期服务、`app/notifications/`独立Python Worker与通知Provider边界、API/Schema、H5计算预览与真实任务状态；平台能力继续封装。
- 增量Alembic保存执行任务、计算依据、Reminder关联和MySQL通知outbox/执行收据；同事务写入任务/reminder/jobs，唯一幂等键含任务/修订/用途。现有聊天、记忆、草案和查询记录不删除；开发库只增量升级/旧数据核对。
- API修改/取消/完成和Worker在一致锁顺序下核对修订，旧修订未来job失效；未确认零有效job。完整详情/导航UI仍归T11E，但调度正确更新与取消必须在本任务后端实测。
- Worker独立于API和网页运行，MySQL是事实源；短租约、重启扫描、错过窗口和过期/missed状态明确记录。不依赖页面计时器，不承诺电脑关机时发送。
- 通知结果区分queued/已提交供应商/送达未知/失败/取消/过期/unknown。发送前持久登记尝试；结果不明不盲目重发，不能承诺外部exactly-once。处于在途的取消不能虚假声称已撤回。

## 已实现结果

- `OutingTask`、`NotificationJob`、`TaskAuditLog` 与草案调度字段通过 Alembic `t11c_scheduler` 增量迁移；任务、reminder 与通知 job 在最终确认的同一事务中写入。
- 到达语义按“目标到达 - 路程 - 接驳缓冲 - 弹性缓冲 - 用户提前量”计算；出发语义不二次扣除路程。普通提醒只计算用户明确的时间与提前量，不虚构路线或天气。
- 信息确认仍为 `not_scheduled`。计算预览可编辑缓冲和提前量；只有独立的“确认并安排提醒”会创建可执行任务。过期预览、旧修订、重复确认、跨用户访问和不完整计划均被拒绝。
- 修改、取消与完成会核对归属和修订，并使旧修订的未来 job 失效；任务列表可刷新读取持久数据。
- 独立 Worker 从 MySQL outbox 获取 job，使用短租约、重启扫描和次数记录；错过发送窗口标为 missed，未知供应商结果不自动重放。
- Mock Provider 返回 `submitted_to_provider`，页面明确说明它不能证明手机收到。Android 后台送达仍归 T11D，不得把本任务结果写成真机验收。

## 测试与证据

- `.\\.venv\\Scripts\\python.exe scripts\\check.py`：安全扫描、工作流校验、Ruff、271 项后端测试、前端 typecheck、ESLint、H5 build 与 diff check 全部通过。
- `npm run test:ui -- tests/scheduling.spec.ts`：6/6 通过。
- `npm run test:ui -- tests/shell.spec.ts`：修复唯一旧空态断言后 12/12 通过。
- `npm run test:ui`：三视口完整 69/69 通过，3.9 分钟。
- 独立 Worker 实进程首轮 `claimed=1, submitted=1`；次轮 `claimed=0, submitted=0`。数据库核对 job/reminder 为 `submitted_to_provider`、attempt=1、provider message id 存在，审计为 `task_scheduled` 与 `notification_submitted`。
- 证据：[T11C-local.json](../testing/T11C-local.json)；截图：[360](../demos/T11C-scheduled-360.png)、[390](../demos/T11C-scheduled-390.png)、[430](../demos/T11C-scheduled-430.png)。
- 本任务新增 DeepSeek 0 次、真实高德 0 次、真实推送 0 次；自动测试只使用 Mock。

## 风险与未完成边界

当前页面与 Worker 以 Asia/Hong_Kong 为产品时区、数据库按 UTC 保存；已测到达/出发/缓冲/跨日/过期/冲突修订。其他 IANA 时区与夏令时缺失/重复仍留 T13 专项。电脑或 Worker 在窗口内停机时不能承诺设备收到提醒。

真实高德连通、Android 后台通知及真机权限拒绝/撤回仍分别保留 LIVE_PENDING 和 T11D 门禁。完整行程详情、导航入口和修改交互 UI 仍归 T11E。

缺推送配置时只能用明确Mock/站内收据验证Worker，不能将“写出通知记录”当手机已收到。T11D必须实际Android后台通知，外部配置/设备门禁继续保留。地图、天气和通知真实验证尚未满足时，V0.1完整目标保持未完成。
