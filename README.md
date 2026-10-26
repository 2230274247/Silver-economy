# Silver-economy
AI companion and personal memory platform for older adults.

时光有声 / 银发记忆 V0.1 内部演示。当前交付阶段见
[任务看板](docs/progress/TASK_STATUS.md)。仅用合成测试数据。

## 当前可运行范围

T02 提供 Muse 参考的聊天首屏、原创伙伴、三个主导航及个人设置、登录和历史页壳。
按用户最新设计改为聊天/我的回忆/提醒，个人设置在右上；18/20/22px 字号可持久化切换。
T03 已接入独立 MySQL/Alembic；T04 已接入真实测试账户登录、身份恢复与退出。
T05 已接入真实会话/消息保存、历史分页、幂等与失败保留；运行界面不再混入静态示例对话。
T06 已验证真实 DeepSeek 聊天、刷新后历史和服务端日预算；自动测试独立强制 Mock，不消耗运营 Key。
T07 已接入明确授权后的候选提取、来源/时间精度/去重及只读列表；跨会话召回、纠错删除和行程任务仍待后续任务。
H5 是本期运行目标；保留 uni-app 页面及平台封装结构，微信小程序/App 需要后续适配与验收。

## 环境与安装

- Python 3.12，Node.js 22，npm 10，Git；依赖安装需要网络。
- T03 起需要可运行 Linux 容器的 Docker Desktop / Docker Compose。
- 项目路径：`H:\AI For research institute\Silver-economy`。
- 不在上级共享目录初始化 Git；不连接或修改已有 `ALE_AI_MySQL`。

在项目根目录运行（PowerShell）：

```powershell
.\scripts\setup.ps1
```

若本机 PowerShell 执行策略不允许运行脚本，不必改系统策略，可逐条运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements.lock
cd apps/mobile
npm.cmd ci
```

Linux/macOS：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r services/api/requirements.lock
cd apps/mobile
npm ci
```

Python 依赖及传递依赖通过带哈希的 requirements.lock 锁定，前端使用 package-lock.json。
依赖更新必须重新测试及提交锁文件，不使用 --force 或 --legacy-peer-deps 掩盖兼容问题。

## 本机启动

从项目根目录分别打开两个终端：

```powershell
.\scripts\start-dev.ps1 -Target api
```

```powershell
.\scripts\start-dev.ps1 -Target h5
```

H5：<http://127.0.0.1:5173>。API：<http://127.0.0.1:8000/>，
OpenAPI：<http://127.0.0.1:8000/docs>。服务仅绑定本机，使用 Ctrl+C 停止。
Chrome 开发者工具切换手机视口；360/390/430px 的视觉验收从 T02 起执行。
若端口被占用，先确认进程归属，不终止其他项目服务。H5 strictPort 防止静默换端口。

无脚本启动方式：在 services/api 下运行项目虚拟环境的
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`；
在 apps/mobile 下运行 `npm run dev:h5`。

## 配置与独立数据库

`.env.example` 只包含变量和空凭据；需要时复制为未跟踪的 `.env`。
API key 只在后端使用，不放入 VITE_ 变量、H5 包或 GitHub；普通用户界面没有 API Key 输入。
后端运营配置入口为被忽略的 .env.deepseek，详见 [DeepSeek 配置与额度](docs/operations/DEEPSEEK.md)。
已真实验证 deepseek-flash；自动化始终Mock，单次输出256与共享日预算生效，未知结果不自动重试。
记忆数据分层与候选限制见 [Memory Layers](docs/data/MEMORY_LAYERS.md)，不是独立核实的个人事实。

Compose 配置已预留独立项目 `silver-memory-demo-v01`，库 `silver_memory_demo_v01`，
默认只绑定 `127.0.0.1:13306`，命名卷与其他项目分离。
本项目 MySQL 初始化（已安装 Python 锁定依赖、启动 Docker Desktop 后，从项目根目录执行）：

```powershell
.\.venv\Scripts\python.exe scripts/init-dev-db.py
cd services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
cd ../..
.\.venv\Scripts\python.exe scripts/seed-demo-users.py
```

初始化脚本只在不存在 .env 时生成随机密码及开发/测试 URL，不打印凭据，不覆盖已有 .env。
若已手动复制空 .env.example，需要在本机填好独立 MySQL 配置后再运行；不要把空密码交给数据库。
开发库 silver_memory_demo_v01，测试库 silver_memory_demo_v01_test，共用本项目容器，独立于已有科研数据库。
白名单同时限制驱动、项目数据库名、silver_demo 用户、loopback 和 13306 端口；不接受 ALE_AI_MySQL 或未知 schema。
现有 3307 监听不复用。不要对未知数据库执行迁移，不执行 `docker compose down -v` 清空数据。
不使用运行时 create_all；新增业务通过后续 Alembic 迁移。初始迁移回退会删除这八张表，仅在可丢弃测试库验证，不对有数据的开发库自动回退。

活性：<http://127.0.0.1:8000/api/v1/healthz>；数据库就绪：<http://127.0.0.1:8000/api/v1/readyz>。
就绪失败返回 503 和脱敏 error.code/message/request_id，不暴露数据库 URL。
服务日志只记录请求 ID/方法/状态/耗时，不记录请求正文或完整 URL 查询参数。

## 演示账号与后端模型配置

种子脚本创建 demo_a/demo_b 两个合成账号，密码随机生成，只保存在忽略的 `.cache/demo-accounts.json`，不打印到终端或 Git。
在本机查看该文件后进入 H5 右上设置→登录演示账号。登录为真实 MySQL 校验；HttpOnly Cookie 恢复会话，退出会撤销服务端会话。
不要将演示账号用于真实资料；已有账号不会被种子脚本自动重置。密码只存 Argon2id 哈希，数据库会话只存 token 哈希。
开发 Cookie 仅 localhost HTTP 使用；正式部署需要 HTTPS 与 COOKIE_SECURE=true，不能据 Demo 认为已生产发布。

运营方 DeepSeek 配置入口是忽略的 `.env.deepseek`，填写 DEEPSEEK_API_KEY 后保存；普通用户网页没有 Key 输入。
具体说明及 T06 待实现的保守额度门禁见 [运营配置](docs/OPERATOR_MODEL_CONFIG.md)。当前仍是 Mock 配置准备，未消耗真实 API 额度。

## 验证与 CI

项目根目录：

```powershell
.\.venv\Scripts\python.exe scripts/check.py
```

检查包括 Git 可见文件的敏感信息扫描、扫描器负例测试、CI 结构校验、
Python lint/format/pytest、前端 typecheck/lint/H5 build，任一步失败即非零退出。
CI 在 dev/v0.1 push 和指向 main 的 PR 上执行；API job 启动自己的独立 MySQL，强制运行真实迁移和约束测试。
本机 .env 有 TEST_DATABASE_URL 时也运行真实集成测试；缺数据库可跳过，但不能据此声称 T03 通过。
严格门禁可设置 REQUIRE_MYSQL_TESTS=1，数据库未配置时直接失败。
Chromium UI 测试覆盖 360/390/430px：导航/草稿、字体、减少动态效果、真实登录/刷新/退出/换号、消息保存/刷新/安全重试及跨用户拒绝；当前 18 项。
回归截图保存在忽略的 .cache/ui-regression，阶段截图单独归档，不覆盖 T02 等旧证据。
本机运行 UI 测试（进入 apps/mobile；浏览器依赖也留在项目内）：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = 'H:\AI For research institute\Silver-economy\.cache\browsers'
npx playwright install chromium
npm run test:ui
```

修改 pages.json 增加页面后应重启 H5 开发服务，避免沿用旧的路由表。
扫描器只覆盖规则可识别的凭据和私有路径，不能替代提交前人工审查；二进制截图需另审。
依赖风险用 `npm audit --json` 查看，不自动执行破坏性升级。

## 目录与版本管理

- apps/mobile：uni-app 源码、依赖与构建配置。
- services/api：FastAPI、测试和后续数据库迁移。
- scripts：安装、启动、验证与安全扫描。
- docs：决策、进度、接口与演示证据。八份冻结 V1.0 基线尚未提供。
- main 保留稳定历史；dev/v0.1 每任务测试后独立 commit/push，再比较 GitHub 远端 SHA。
- 本任务提交的最终远端与 CI 结果在下一次提交中记录，不预先标记完成。

后续隐私界面会明确聊天原文与长期记忆的保管、纠错及删除边界。
V0.1 仅内部演示；语音、照片/生成影像、iOS/小程序后台通知和复杂向量检索均延后。
正式 [CR-001](docs/changes/CR-001.source.md) 将主动出行助理与长期记忆并列为 P0：
聊天识别/追问、可编辑确认卡、高德路线天气、确定性出门时间、持久化调度及通知。
T11 已拆为 T11A–T11E；最终至少一台 Android 真机后台通知通过，浏览器只作中间验证。
这覆盖此前 [ADR-002](docs/decisions/ADR-002-assistant-and-ui.md) 的 PC-only 决定，
详见 [影响与依赖](docs/changes/CR-001-impact.md)、[ADR-003](docs/decisions/ADR-003-cr001-delivery.md)、
[数据库设计](docs/data/CR-001-database-design.md) 与 [扩展验收](docs/demos/CR-001-ACCEPTANCE.md)。
当前均为待实施需求，不能据预览页认为已具备提醒能力；缺密钥可先 Mock，真实服务/真机状态单独记录。

开发、修复、时间与验证历史见 [GitHub 开发日志](docs/progress/COMMIT_LOG.md)。
