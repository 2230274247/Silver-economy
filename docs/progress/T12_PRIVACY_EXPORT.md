# T12：设置、隐私、数据导出与授权撤回

状态：DONE_PUSHED。本地测试、远端 SHA 与 GitHub Actions 均已核验。

## 完成内容

- 新增需登录访问的 `GET /api/v1/account/export`。身份只取当前会话，
  即使请求附带其他 `user_id` 也不会改变导出范围。
- 导出当前账户的聊天、消息、长期记忆、修订、原文来源、记忆引用、生活事件、
  任务草案、行程、提醒、通知状态、通知设备脱敏信息、任务审计、地图请求和模型用量。
- 下载响应使用 `application/json`、附件文件名、`Cache-Control: private, no-store`
  与 `Pragma: no-cache`，避免共享缓存保留个人数据。
- 明确排除密码哈希、登录令牌哈希、推送客户端 ID 及密文、设备指纹、模型原始响应、
  通知租约和幂等内部字段，也排除任何其他账户的数据。
- 设置页展示记忆和位置授权边界，修正已过时的“记忆不能编辑或删除”文案，并提供
  真实的长期记忆管理入口、当前通知设备列表和本人设备撤回操作。
- H5 通过 `fetch` 下载 JSON，并以 Blob 保存；原生平台分支使用
  `uni.downloadFile` 与 `uni.saveFile`，为后续 App 迁移保留平台封装。

## 文件

- `services/api/app/api/v1/privacy.py`
- `services/api/app/main.py`
- `services/api/tests/test_privacy_export.py`
- `apps/mobile/src/platform/data-export.ts`
- `apps/mobile/src/pages/me/index.vue`
- `apps/mobile/tests/privacy.spec.ts`
- `docs/api/openapi.json`

## 数据库与兼容性

- 本任务不新增或修改数据库结构，不生成 Alembic 迁移。
- 只读取本项目 `silver_memory_demo_v01` / `silver_memory_demo_v01_test`
  数据库中的现有账户数据，未连接或修改 `ALE_AI_MySQL`。
- 导出格式版本为 `silver-memory-export/v1`；时区声明为 `Asia/Hong_Kong`。

## 测试

- `pytest -q tests/test_privacy_export.py tests/test_notifications.py`：6/6 通过。
- `npx playwright test tests/privacy.spec.ts`：360、390、430 三视口共 6/6 通过。
- `npm run test:ui`：三视口完整 78/78 通过，用时约 4.3 分钟。
- `.venv\Scripts\python.exe scripts\check.py`：278 项后端测试通过；security、
  workflow、Ruff、格式检查、TypeScript、ESLint、H5 build、diff check 全部通过。
- 仅有一条既有的 Starlette/httpx 弃用警告，不影响本次结果。
- 浏览器测试验证真实 JSON 下载、敏感字段排除、账户隔离、设备撤回确认与记忆管理导航。
- 截图：`docs/demos/T12-privacy-360.png`、`T12-privacy-390.png`、
  `T12-privacy-430.png`。

## 服务边界

- 本任务只使用 Mock 模型与合成账户数据；新增 DeepSeek、真实高德和真实 uni-push
  调用均为 0。
- H5 浏览器通知不能替代 Android 真机后台通知。`CR-AC10` 继续保持
  `BLOCKED_PROVIDER_CONFIGURATION`。
- 数据导出已接入真实后端和本项目 MySQL，但尚未执行大账户容量压测；
  V0.1 当前以演示规模为边界。

## 后续动作

1. 功能提交 `56ce42b336c49400e3845b2ae75c3cf232a16f99` 已推送，
   `origin/dev/v0.1` SHA 与本地一致。
2. GitHub Actions run `40457533355` 的 api、security、mobile 全部 success；
   证据见 `docs/testing/T12-remote.json`。
3. 本状态同步提交独立记录，不改写功能提交；下一项进入 T13 完整验收矩阵。
