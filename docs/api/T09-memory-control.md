# 记忆控制接口（T09）

全部路径前缀 `/api/v1`；使用HttpOnly登录Cookie，用户归属从会话决定。请求多余字段禁止，未知/他人/已删除记忆404；过期版本409 `MEMORY_REVISION_CONFLICT`，重复指纹409 `MEMORY_DUPLICATE`。

| 方法/路径 | JSON字段 | 返回 |
|---|---|---|
| POST /memories/{id}/confirm | expected_revision≥1, confirmed:boolean | 新MemoryOut；撤销确认不激活失效状态 |
| POST /memories/{id}/correct | expected_revision, kind, key, value, time_expression | 新MemoryOut；本人纠错为user_edit并确认；原文不变 |
| POST /memories/{id}/permission | expected_revision, allowed:boolean | 新MemoryOut；AI使用还需全局授权、有效状态 |
| POST /memories/{id}/invalidate | expected_revision | 新MemoryOut，inactive |
| DELETE /memories/{id} | expected_revision | deleted:true, raw_messages_retained:true |
| GET /memories/{id}/revisions | 可选before_revision≥1 | items/next_revision，每页30条倒序修改记录 |

MemoryOut增加revision/value_origin；原有列表/搜索/来源接口保留。写入先锁User后锁Fact，审计与修改同事务提交，版本防重复覆盖，不为控制动作调用模型。修改时间表达不变则保留原日期锚点。

聊天引用增加evidence_text/evidence_origin/memory_revision/changed_since_reply。user_edit引用以该审计版本值为准，同时保留source_excerpt及原会话；旧引用提示已变化。删除后所有引用列表不再返回该记忆，但既有聊天正文属于L0，保持原样。

完整契约以 `openapi.json` 为准。软删除及指纹墓碑不是物理抹除；审计不进入模型上下文，用户纠错当前值除外。历史/当前身体状态规则边界见T09_MEMORY_CONTROL.md，不将规则结果标成独立医学核实。
