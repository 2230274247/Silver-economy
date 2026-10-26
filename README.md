# Silver-economy
AI companion and personal memory platform for older adults.

时光有声 / 银发记忆 V0.1 内部演示。当前交付阶段见
[任务看板](docs/progress/TASK_STATUS.md)。仅用合成测试数据。

## 当前可运行范围

T01 提供 uni-app Vue3/TypeScript H5 与 FastAPI 工程骨架。
页面明确显示未接入登录、聊天和记忆；当前没有模型调用，没有数据库连接。
四 Tab 从 T02 开始，独立 MySQL/Alembic 从 T03 开始，账号和业务按任务顺序开发。
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

H5：<http://127.0.0.1:5173>。API 骨架：<http://127.0.0.1:8000/>，
OpenAPI：<http://127.0.0.1:8000/docs>。服务仅绑定本机，使用 Ctrl+C 停止。
Chrome 开发者工具切换手机视口；360/390/430px 的视觉验收从 T02 起执行。
若端口被占用，先确认进程归属，不终止其他项目服务。H5 strictPort 防止静默换端口。

无脚本启动方式：在 services/api 下运行项目虚拟环境的
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`；
在 apps/mobile 下运行 `npm run dev:h5`。

## 配置与独立数据库

`.env.example` 只包含变量和空凭据；需要时复制为未跟踪的 `.env`。
API key 只在后端使用，不放入 VITE_ 变量、H5 包或 GitHub。
模型示例 ID 尚未验证，T06 以官方文档和实际请求为准；当前没有 live 验证或费用。

Compose 配置已预留独立项目 `silver-memory-demo-v01`，库 `silver_memory_demo_v01`，
默认只绑定 `127.0.0.1:13306`，命名卷与其他项目分离。
T03 启动前配置本地 MYSQL_PASSWORD/MYSQL_ROOT_PASSWORD，复查端口并运行迁移。
现有 3307 监听不复用。不要对未知数据库执行迁移，不执行 `docker compose down -v` 清空数据。
DATABASE_URL 仅可指向本项目独立数据库。

## 验证与 CI

项目根目录：

```powershell
.\.venv\Scripts\python.exe scripts/check.py
```

检查包括 Git 可见文件的敏感信息扫描、扫描器负例测试、CI 结构校验、
Python lint/format/pytest、前端 typecheck/lint/H5 build，任一步失败即非零退出。
CI 在 dev/v0.1 push 和指向 main 的 PR 上执行；T03 增加真实 MySQL 集成任务。
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
V0.1 仅内部演示；语音、照片/生成影像、系统推送和复杂向量检索均延后。
