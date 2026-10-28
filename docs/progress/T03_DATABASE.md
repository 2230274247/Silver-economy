# T03：独立 MySQL、Alembic 与 API 基础

- 日期：2026-10-26，Asia/Hong_Kong。
- 状态：本地验收通过，待本次 commit/push/SHA/CI；完成时间以 Git 元数据及事后日志为准。
- 前项日志同步：eaf3902f0c915cc8ebf3d4bb975d38b808ca7b39，远端一致，CI 40290065675 PASS。

## 实现与文件

- docker-compose.dev.yml、scripts/init-dev-db.py：独立 MySQL 容器/卷/网络，127.0.0.1:13306；开发库与测试库，UTC/utf8mb4；随机凭据写入忽略的本地 .env，已有文件不覆盖、不输出凭据。
- services/api/app/core：只允许本项目 schema/用户/端口的配置校验、SQLAlchemy engine/session、统一业务错误。
- services/api/app/models、alembic：八张初始表、user_id 索引与复合外键、消息幂等/回复关联唯一键；t03_core 真实迁移，未使用运行时 create_all。
- services/api/app/main.py：真实活性/就绪接口、请求 ID、脱敏错误与只记录方法/状态/耗时的日志。
- tests：真实 MySQL 迁移往返/重复升级/metadata 差异/跨用户关联约束，数据库保护及健康/脱敏测试。
- .github/workflows/ci.yml：CI 自己启动独立 MySQL，REQUIRE_MYSQL_TESTS=1 禁止悄悄跳过集成检查；纳入迁移代码 lint/format。
- README、docs/api/T03-foundation.md、openapi.json：实际启动/迁移/API 合同。

## 实际命令与结果

1. piptools compile --generate-hashes / pip install -r requirements.lock：PASS，依赖仅装入本项目 .venv。
2. python scripts/init-dev-db.py：PASS，首次新建独立容器和双库；再次执行仍 PASS，不覆盖 .env、不重建其他服务。
3. services/api 中 alembic revision --autogenerate、alembic upgrade head：PASS，当前 t03_core (head)。
4. REQUIRE_MYSQL_TESTS=1 pytest -q：12 passed（4.07s，完整检查中再次 3.75s），一条上游 httpx 弃用警告。
5. python scripts/check.py：PASS，5 个扫描器测试、秘密扫描、CI YAML、ruff、12 个 API/数据库测试、前端 typecheck/lint/H5 build、Git diff 检查。
6. 实际运行 uvicorn 后 HTTP：/api/v1/healthz 200 status=ok；/api/v1/readyz 200 status=ready/schema_revision=t03_core；X-Request-ID 存在。
7. docker compose ps：本项目 mysql healthy，绑定 127.0.0.1:13306；git check-ignore .env：PASS。

## 测试中发现并修复

- 首次自动生成的复合唯一约束只用第一列命名，发生重名；改成包含全部列。首次未完成的建表只在本次新建库、确认所有相关表零数据后清理重跑，未触碰旧项目。
- 初始 downgrade 先删除 MySQL 外键需要的索引导致失败；改为按依赖反序删表、索引随表删除。保持原迁移往返测试并通过，未删用例。
- 重载 API 时先发现 8000 监听进程命令行未直接带项目路径，安全检查拒绝停止；核对其父进程为本项目 .venv 后才停止原项目服务并启动新版。未终止未知服务。

## 安全与未完成项

没有连接/修改 ALE_AI_MySQL。地址白名单在打开连接前检查，测试回退仅允许 silver_memory_demo_v01_test。
没有向仓库添加 .env、数据库文件或真实用户数据；没有模型/地图/推送真实调用，新增 API 费用 0。
T03 只完成基础能力：登录和 API 用户鉴权为 T04，消息持久化 UI 为 T05，Provider 为 T06；数据库层约束不能替代未来 API 鉴权。
UI-FIX-01 已独立排队，随真实登录/聊天接入再完成空态引导、IME/多行、发送/生成/重试/去重及软键盘/滚动验收，保留 T02 历史。
下一任务：T04（须本任务远端 SHA 与 CI 核验成功后开始）。
