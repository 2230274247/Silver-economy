# Silver-economy · 银发记忆 V0.1

有长期记忆的AI生活助理。当前为**会议室初步演示可用，正式最终验收未完成**。
保留米白/浅绿Muse式H5布局；不重建工程或改写Git历史。

## 立即演示

本机：http://127.0.0.1:5173/#/ 。API文档：http://127.0.0.1:8000/docs 。
演示步骤、登录与重启见[会议演示指南](docs/operations/MEETING_DEMO.md)。
本机demo_a/demo_b的随机密码仅在被Git忽略的.cache/demo-accounts.json，不上传或投屏显示。

## 当前能力与边界

| 能力 | 当前结果 |
|---|---|
| 真实聊天 | FastAPI调用运营方配置的DeepSeek；消息/关联回复持久保存，刷新和历史会话可读 |
| 长期记忆 | 明确授权后候选提取、来源/时间精度、跨会话召回、确认/纠错/失效/删除和来源时间线 |
| 规模验证 | 可重复Synthetic生成/导入，100/1000/10000/20000与310固定题实际SQL报告；批量答案使用Mock |
| 出行任务 | 意图/追问、可编辑卡、独立信息确认与调度确认；确定性时间、持久Worker、修改/替换/取消/完成 |
| 地图天气 | Provider与Mock合同完成；当前Mock，真实高德未验收 |
| 通知 | outbox/设备加密/撤回/桥接合同；当前Mock，Android后台实际送达未验收 |
| 数据控制 | 账户隔离、本人JSON导出、记忆授权/设备撤回；数据库备份恢复演练未完成 |

未实现的语音、附件、图片生成不作为可用能力。Mock/Synthetic均标识；不把服务商接受写成已送达。
完整未验收清单与续办步骤：[V01_PENDING_ACCEPTANCE](docs/progress/V01_PENDING_ACCEPTANCE.md)；
验收矩阵：[QA_REPORT](docs/demos/QA_REPORT.md)；阶段进度：[TASK_STATUS](docs/progress/TASK_STATUS.md)。

## 安装与独立数据库

环境：Python3.12、Node22/npm10、Git、Docker Desktop Linux容器。所有工作在Silver-economy子目录；不初始化或修改上级共享项目，不使用ALE_AI_MySQL。

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\python.exe scripts/init-dev-db.py
cd services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
cd ../..
.\.venv\Scripts\python.exe scripts/seed-demo-users.py
```

锁定Python依赖services/api/requirements.lock，前端apps/mobile/package-lock.json。初始化不覆盖已有.env，不打印凭据。
独立项目MySQL仅127.0.0.1:13306，开发库silver_memory_demo_v01，测试库silver_memory_demo_v01_test。
不得对开发库自动执行downgrade/base或docker compose down -v。备份恢复与新机复现待验收，见P05/P06。

## 启动

在项目根的三个终端分别执行：

```powershell
.\scripts\start-dev.ps1 -Target api
.\scripts\start-dev.ps1 -Target h5
.\scripts\start-dev.ps1 -Target worker
```

服务绑定本机，端口被占用先检查归属，不停止其他项目。Worker必须持续运行才会执行后台扫描；关页面不删除任务。
readyz：http://127.0.0.1:8000/api/v1/readyz 。Ctrl+C停止自己的进程。修改pages.json后重启H5。
本演示没有生产HTTPS发布，不承诺跨电脑直接访问localhost。

## 服务端配置与额度

真实配置只放本机.env/.env.deepseek/.env.amap/.env.notifications或环境变量；Git忽略真实文件，.env.example仅空字段。
普通用户不输入Key，前端不直接请求模型/地图服务。

- [DeepSeek配置/成本](docs/operations/DEEPSEEK.md)：当前真实配置有效；默认每日10次/20000保守预留tokens，普通输出256、结构化任务512上限，unknown不自动重试。自动测试强制Mock。
- [高德配置](docs/operations/AMAP.md)：当前Mock，真实Key/配额待配置，不宣称实时车程天气。
- [Android通知](docs/operations/ANDROID_NOTIFICATIONS.md)：缺DCloud/厂商/签名/真机条件，不能用H5代替CR-AC10。

准备演示前历史真实调用7次/3218输入376输出tokens/保守估算USD0.00141660，非账单；现场发送的新调用另计。

## 检查与证据

常规代码变更按范围运行必要专项；用户最新要求不重复非必要全套测试。完整门禁入口仍保留：

```powershell
.\.venv\Scripts\python.exe scripts/check.py
cd apps/mobile
$env:PLAYWRIGHT_BROWSERS_PATH='H:\AI For research institute\Silver-economy\.cache\browsers'
npx playwright install chromium
npm.cmd run test:ui
```

T13最终294后端、78完整UI及12调度地点专项通过，360/390/430px；最新T14只做启动/登录/只读与提交检查。
pytest可丢弃测试库有迁移往返，不与批量评估同时运行。缺MySQL不能宣称数据库测试通过；严格门禁REQUIRE_MYSQL_TESTS=1。
GitHub Actions执行后端/前端/安全检查；CI和SHA以远端实际结果为准，不预填成功。

- [固定题集/指标口径与复现](docs/testing/MEMORY_EVALUATION.md)
- [离线四档HTML报告](docs/testing/memory-eval-v1/t11a-v1-verified.html)
- [模块与数据库说明](docs/architecture/V01.md)
- [Prompt版本](prompts/README.md)
- [依赖已知问题](docs/DEPENDENCY_REVIEW.md)
- [详细提交/修复/时间记录](docs/progress/COMMIT_LOG.md)

main保留稳定历史，dev/v0.1承载开发提交。每项必要检查后commit/push/远端SHA/CI；不force、不改历史、不自动合并或发布Tag。
T14交付仍有开放验收项，本仓库不宣称完整V0.1正式验收通过。
