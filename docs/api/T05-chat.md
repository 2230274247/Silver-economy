# T05 持久聊天 API

日期：2026-10-26（Asia/Hong_Kong）。请求/响应的实际 Pydantic schema 已导出 openapi.json。

- GET/POST /api/v1/conversations：本人会话分页/创建。GET /conversations/{id}：本人详情。
- GET /conversations/{id}/messages：按 (created_at,id) 游标读历史；limit 1–100、before_id 必须属于本人同会话，返回按时间正序的当前页和 next_cursor。
- POST /conversations/{id}/messages：content（1–2000 字符，禁止纯空白）、UUID client_request_id；返回 user_message、关联 assistant_message、replayed 和 provider。
- 同用户同幂等键/同内容/同会话返回同一记录，不重复写；同键不同内容或会话 409。
- 当前模型尚未接入：原文真实保存，assistant 为 failed/MODEL_NOT_CONFIGURED，content 为空，不用预设文字冒充模型输出。
- 每次保存锁定本人会话，分配递增 UTC 微秒时间；唯一键作为重复请求的最终约束。所有列表/详情/写入均服务端按当前身份过滤。
- 会话/游标越权 404；参数错误 422，登录失效 401，错误返回统一 request_id。

T06 接入 Provider 后继续复用原消息和幂等键。失败重试不能创建重复用户消息；结果不确定时不得偷偷再次计费。
