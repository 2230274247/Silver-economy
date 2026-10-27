# T11A：任务信息草案接口

2026-10-27，UTC响应/香港北京时间展示。沿用HttpOnly登录会话；归属只取认证用户，任何接口都不接受user_id。跨用户或不存在均404。

- 聊天发送/历史的每条消息增加`task_drafts`，关联产生或更新草案的助手回复。原始消息保留；后续补充后卡片只在最新回复出现。重放相同client_request_id读取原结果，不再次调用模型或建草案。
- `GET /api/v1/task-drafts?conversation_id=...&limit=30`：读取本人该会话最新草案（limit1–100）。历史消息原有游标分页可继续取旧卡片。
- `GET /api/v1/task-drafts/{id}`：刷新一条，含revision、来源、逐字段evidence、missing_fields、原始时间表达、time_reference_at、resolved_date、UTC target_at及timezone。
- `POST /api/v1/task-drafts/{id}/edit`：完整编辑表单。字段为expected_revision、title、time_text、time_semantics、origin、destination、transport、lead_minutes；不得提交路线/天气或服务端计算时刻。超长/额外字段/负提前量422，过期版本409。修改已确认信息会重新打开为draft。
- `POST /api/v1/task-drafts/{id}/actions`：`{"expected_revision":1,"action":"confirm"}`或defer。缺项/已过时间不可confirm（422），状态或版本冲突409。对刚完成的同一动作幂等，不重复增加版本。deferred不可继续编辑，请重新提出事项。

transport为unknown/taxi/driving/transit/walking/cycling；time_semantics为unknown/arrival/departure/at。出行必须区分到达或出发；普通提醒使用at。lead_minutes范围0–10080，默认出行60、普通提醒0，当前仅保存偏好，不计算通知时刻。

所有草案均`scheduling_status="not_scheduled"`。`confirmed`仅表示信息核对保存，不代表已调度、已推送或送达。T11C须在路线/天气预览及确定性计算后另获明确调度确认，禁止自动执行旧信息确认。

数据库迁移`t11a_draft`仅新增task_drafts；原/最近消息归属外键、来源序号唯一键、用户会话索引及revision用于审计/隔离/防重。当前地点都是未经地图核实的文本标签；位置许可、地点选择、路线与天气留待T11B，不把“我家”当真实地址。
