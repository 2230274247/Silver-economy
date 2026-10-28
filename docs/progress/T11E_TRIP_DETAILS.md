# T11E：行程详情与任务生命周期

状态：DONE_PUSHED。本地门禁、远端 SHA 与 GitHub Actions 均已核验。

## 完成内容

- 新增 `GET /outing-tasks/{id}/status`、`POST /outing-tasks/{id}/depart` 和
  `POST /outing-tasks/{id}/feedback`；全部按当前登录用户校验任务归属。
- 行程卡可展开查看路线、天气、计算依据、通知来源与状态；Mock/Synthetic
  数据始终明确标注。导航入口打开高德目的地搜索页，不把搜索入口冒充实时路线导航。
- 用户可以修改行程时间与提醒参数；修改会递增修订、失效旧未来通知并创建新通知。
  用户可标记已出发或完成，旧未来通知会取消；已出发任务仍可完成。
- 记录“有帮助/需要改进”的反馈审计，不改变任务修订，也不触发模型或第三方调用。
- H5 在 360、390、430 像素视口通过完整回归，保留现有视觉风格和移动端布局。

## 数据库与 API

- 增量迁移 `t11e_trip_details` 为 `outing_tasks` 增加可空 `departed_at`。
- 同一迁移仅在缺失时补齐 `task_audit_logs.user_id -> users.id` 外键；这是历史
  迁移合同遗漏的数据保留式修复。开发库已执行迁移，`alembic check` 通过。
- `OutingTaskOut` 增加 `departed_at` 和 `navigation_url`；OpenAPI 已重新生成。
- 任务生命周期为 `scheduled -> departed -> completed`，或从 `scheduled` 取消。
  重复出发请求可返回同一结果，跨用户读取或操作仍返回 404。

## 测试

- `pytest -q tests/test_scheduling.py tests/test_notifications.py`：12/12 通过。
- `pytest -q tests/test_database.py tests/test_notifications.py`：10/10 通过。
- `npx playwright test tests/scheduling.spec.ts`：360/390/430 三视口共 9/9 通过。
- `npm run test:ui`：三视口完整 72/72 通过。
- `python scripts/check.py`：276 项后端测试通过，security、workflow、Ruff、
  TypeScript、ESLint、H5 build 与 diff 检查全部通过。
- 截图：`docs/demos/T11E-trip-360.png`、`T11E-trip-390.png`、
  `T11E-trip-430.png`。

## 服务边界

- 本任务自动测试使用 Mock；新增 DeepSeek、真实高德和真实 uni-push 调用均为 0。
- 通知状态只表示站内任务及供应商提交边界；Android 后台送达仍需真机和厂商配置，
  `CR-AC10` 继续保持 `BLOCKED_PROVIDER_CONFIGURATION`。
- 导航按钮只提供目的地搜索入口；路线时长仍来自已经保存、带来源和有效期的快照。

## 远端核验

- 功能提交 `135aa2837f914b00bf0acd7ff5abc66d11c09788` 已推送，
  `origin/dev/v0.1` SHA 与本地一致。
- GitHub Actions run `40454654272` 的 api、security、mobile 全部 success；
  mobile 包含完整三视口 UI 回归。证据见 `docs/testing/T11E-remote.json`。
- 本状态同步提交独立记录，不改写功能提交。下一项进入 T12 设置、隐私和导出。
