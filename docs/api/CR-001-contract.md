# CR-001 API 扩展合同（待实现）

日期：2026-10-26，Asia/Hong_Kong。当前 OpenAPI 尚无这些路由；实现随 T11A–T11E 更新实际 schema 与前端类型。
继续 /api/v1、JSON、带时区 ISO8601、统一 error.code/message/request_id 与身份隔离。

2026-10-27 T11A实施补充：下表保留最初设计，不表示都已实现。意图提取合并到已有聊天发送的一次Provider调用，未另建`/assist/parse-task`，避免额外用量及原文重复。持久草案实际采用`/task-drafts`读取/编辑/信息确认，见[T11A实际合同](T11A-task-drafts.md)及openapi.json。可执行`/outing-tasks`、地图、预览、调度、设备及通知接口仍待B–E；信息confirmed仍是not_scheduled。

2026-10-27 T11B实施补充：位置同意/搜索/选择及路线天气预览实际归属于`/task-drafts/{id}`，复用已有身份/草案版本；见[T11B实际合同](T11B-maps.md)与OpenAPI。表中GET /places/search仍是旧设计，不另建无草案上下文的查询入口。当前Mock/HTTP合同测试不代表高德live验证，出门时间运算/调度/设备仍待C–E。

| API | 输入/输出边界 | 任务 |
|---|---|---|
| POST /assist/parse-task | 本人消息/本轮文字+用户时区 → assistant_text、task_drafts[]、missing_fields[]、questions[]；只生成候选 | T11A |
| GET /places/search | 本人主动地点搜索、有限候选；不得由模型指定 URL，不回显 Key | T11B |
| POST /outing-tasks/preview | 经用户同意的地点/交通/目标时间含义/缓冲 → 有版本及过期时间的计算预览、路线天气来源/获取时间/Mock 标记；不创建 job | T11B/C |
| POST /outing-tasks | 明确确认、client_request_id、preview_version、用户可编辑字段 → task/reminder/scheduling_status/notification_permission；同事务保存，不等于送达 | T11A/C |
| GET /outing-tasks | 本人分页列表，支持状态过滤 | T11E |
| GET /outing-tasks/{id}/status | 本人行程/来源/最近快照/通知与失败状态；不含服务凭据或完整设备 ID | T11E |
| PATCH /outing-tasks/{id} | expected_revision + 用户确认的新字段；重新验算并失效旧 job，409 处理版本冲突 | T11C/E |
| POST /outing-tasks/{id}/cancel | expected_revision + 明确取消确认；幂等，取消未来 job，说明在途状态 | T11C/E |
| POST /outing-tasks/{id}/depart | 确认已出发，停止不再相关的出门提醒 | T11E |
| POST /outing-tasks/{id}/complete | 明确完成，停止后续无效通知并审计 | T11E |
| POST /notification-devices | 登录且同意后绑定当前设备与权限，不接受任意 user_id；退出/撤回需解绑接口 | T11D |
| DELETE /notification-devices/{id} | 本人撤回设备登记与未来推送，不能删除他人设备 | T11D/12 |
| GET /notifications | 本人站内记录和供应商/送达/打开状态，区分未知和失败 | T11D/E |

聊天发送路由在 T05 保持原协议；T11A 扩展可选 task_drafts，不替换原消息持久化和幂等逻辑。
任务草案枚举字段而非任意命令；一条消息多个安排分卡确认；不确定/矛盾字段追问。
时间含义未确认、目标时间过期、缺必需地点许可时不能调用真实路线或直接调度出行。
路线/天气不可用时，可明确选择普通提醒模式并确认时刻，返回查询 unavailable；不填造假车程/雨情。
LLM 不能自行确认、不掌握 API Key、不调用生产推送；权限过滤由服务和数据库执行，不能靠提示词。
错误码/状态示例：TASK_NEEDS_CLARIFICATION、PREVIEW_EXPIRED、TASK_VERSION_CONFLICT、ROUTE_UNAVAILABLE、WEATHER_UNAVAILABLE、NOTIFICATION_PERMISSION_REQUIRED、PROVIDER_NOT_CONFIGURED；最终以实际 Pydantic/OpenAPI 实现为准。
