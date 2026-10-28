# T03 API 与数据库基础合同

日期：2026-10-26（Asia/Hong_Kong）。实际 schema 见 openapi.json 和 FastAPI /openapi.json。

- GET /api/v1/healthz：200 {status: ok}，只表示进程活性。
- GET /api/v1/readyz：数据库可连接且存在迁移版本时 200 {status: ready, schema_revision: ...}；失败 503 DATABASE_UNAVAILABLE。
- GET /healthz：活性兼容入口；不在 OpenAPI 重复展示。
- 每请求生成 X-Request-ID；错误 JSON 为 error.code/message/request_id。422 不回显原始输入。
- 当前没有登录/聊天/记忆/行程路由；未实现路径返回实际 404，不返回假成功。

数据库为独立 Compose 项目 silver-memory-demo-v01，宿主 127.0.0.1:13306；数据库会话时区 UTC，DATETIME(6) 保存微秒。
八张初始表：users/conversations/messages/memory_facts/memory_sources/life_events/reminders/model_usage。
私有表 user_id 索引；会话、消息、记忆及来源之间以复合外键防跨用户关联。
messages 预留请求幂等和回复关联唯一键；API 鉴权与持久聊天在 T04/T05 实现，这些表存在不等于业务已交付。
CR-001 增量表按后续任务迁移，不预先创建假可执行任务。

迁移版本 t03_core：upgrade 建八表及索引/约束；downgrade 按依赖反序删表，索引随表删除，避免破坏 MySQL 外键索引。
只在本项目可丢弃测试 schema 执行 downgrade，测试会重新 upgrade；不自动回退用户/开发数据。
