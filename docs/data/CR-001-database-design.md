# CR-001 增量数据库设计

- 日期：2026-10-26，Asia/Hong_Kong。
- T11A–T11E 已按顺序执行增量 Alembic 迁移；具体实际表和字段见迁移、
  OpenAPI 与对应专项记录。
- T03 建立原合同基础表与独立开发/测试 schema；以下增量在 T11A–T11C 分步实现，不改写已发布迁移。
- 只能使用本项目独立 MySQL，禁止连接/修改 ALE_AI_MySQL。

## 全局约束

主键统一由服务端生成；所有用户私有表含 user_id 并建立查询索引。
跨表以 (user_id, id) 唯一键和复合外键约束归属，禁止把 A 的 message/reminder/device 关联到 B 的任务。
API 的 user_id 来自已验证会话，不从请求字段信任。
时间使用 UTC DATETIME(6)，保留 IANA timezone，API 只接受带时区时间；秒数为非负整数。
地址/坐标不写日志和审计全文；设备推送 ID 加密/限制读取，脱敏显示，不导出到 Git。

| 表 | 关键字段与约束 | 所属任务 |
|---|---|---|
| outing_tasks | id/user_id/source_message_id/reminder_id；title；status；target_at；time_semantics(arrival/departure)；timezone；origin_type/明确确认的地点；destination_text/place_id/坐标；transport_mode；estimated_travel_seconds；pickup_walk_buffer_seconds；contingency_buffer_seconds；preferred_advance_seconds；recommended_departure_at/reminder_at；user_confirmed_at；revision；created_at/updated_at/departed_at/cancelled_at/completed_at | T11A 基础、T11C 调度字段、T11E 出发时间 |
| place_aliases | 可选；本人授权的别名→地点；consented_at/revoked_at；同用户有效别名约束；不推测家庭住址 | T11B，如实施 |
| route_weather_snapshots | id/user_id/outing_id/task_revision；provider/fetched_at；route_duration_seconds/distance_meters；城市 adcode、forecast_for_at、forecast_issued_at、weather_summary；raw_reference_code/provider_mode；禁止无必要保存完整原始响应 | T11B |
| notification_jobs | id/user_id/outing_id或reminder_id/task_revision/device_id；purpose/channel/scheduled_at/expires_at/status；retry_count/next_attempt_at；unique idempotency_key；provider_message_id/last_attempt_at/error_code；lease_owner/lease_until；created_at/updated_at | T11C |
| notification_devices | id/user_id/platform；push_client_id_ciphertext；permission_status/last_seen_at/revoked_at；唯一服务端设备指纹，换号绑定需撤销旧归属；不返回完整加密内容 | T11D |
| task_audit_logs | id/user_id/outing_id/task_revision；action/actor_type/occurred_at/request_id；字段变更摘要/错误码；创建、确认、调度、提交服务商、回执、打开、修改、取消、完成分别记事件 | T11A–T11E |

target_at + time_semantics 对应 CR 示例的 arrival_at + arrival_or_departure，避免“出发时刻存进到达字段”的歧义。
草案可以有 unknown/缺字段，但确认状态的持久可执行任务必须明确时间含义。
reminders 与 outing_tasks 通过唯一 reminder_id 关联；普通提醒允许无 outing；出行提醒的 due_at 由同一事务同步，不能出现两套不同时间。
普通提醒 notification_jobs 关联 reminder_id，出行提醒还关联 outing_id；数据库 CHECK 约束至少有一个合法目标，服务校验一一对应。

## 状态、索引与事务

- outing_tasks：draft（如需要持久草案）、scheduled、departed、completed、cancelled；草案没有有效待发 job。
- job 调度状态：queued/processing/sent_to_provider/failed/cancelled/expired/unknown；送达确认与打开时间另存，避免接受请求冒充到达。
- 索引：(user_id, status, target_at)、(status, next_attempt_at, scheduled_at)、(outing_id, task_revision)、(user_id, created_at)。
- 创建请求 client_request_id 在用户内唯一；同键不同内容拒绝冲突，不重新安排。
- 出行 revision 与幂等键使同用途同设备同修订仅一个有效 job；取消/修改锁定任务并在一个事务中失效旧 job、同步 reminder、追加审计。
- Worker 基于 MySQL 行锁/SKIP LOCKED 和租约恢复，不在浏览器 setTimeout 调度。
- 取消/完成后 Worker 发前再验状态；已提交供应商的在途通知不能谎称一定已撤回。

每条迁移须在独立空测试库验证 upgrade→再次 upgrade→downgrade→upgrade；降级方案写明有损性，只对可丢弃合成测试库执行回退。
表/外键/唯一约束/隔离和重启场景在 T11 增量测试，不能仅凭此设计文档记已实现。
