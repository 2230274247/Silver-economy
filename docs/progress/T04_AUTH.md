# T04：测试账号、可撤销会话和 H5 登录

- 日期：2026-10-26（Asia/Hong_Kong）。本地验收通过，待本次 commit/push/SHA/CI。
- T03：3aa87eee69790e7fc1cbce46fda8eb8f7315cdb3，远端一致，CI 40293010288 三项全部 PASS。

## 实现

- 增量迁移 t04_auth 新增 auth_sessions，不改写已推送 t03_core。密码 Argon2id；随机会话 token 只存 SHA256；12 小时默认有效，可撤销。
- POST /api/v1/auth/login、GET /api/v1/me、POST /api/v1/auth/logout；登录失败统一提示，过期/伪造/停用账号拒绝，退出后复制的 cookie 也无法继续使用。
- H5 同源代理调用 FastAPI，使用 HttpOnly/SameSite Cookie，不在 localStorage、前端代码或响应 JSON 存储会话 token；开发环境 HTTP，生产须 HTTPS/secure。
- 真实登录表单、加载/失败反馈、刷新恢复身份、设置页显示当前账号和退出。切换用户清空草稿，登录页不出现 API Key 配置。
- 仅本地种子脚本生成两个随机密码的合成账户，凭据文件在忽略的 .cache，不写 Git，不覆盖未知已有用户。
- 用户最新指令恢复无人值守，撤销此前临时提出的人工逐任务门槛；已写 AGENTS。
- 用户要求提前配置模型：准备忽略的 .env.deepseek 运营入口，后端可读取；额度限制仍待 T06 实现，当前未发真实调用。

## 实际测试

1. Alembic upgrade t04_auth + 合成账户种子：PASS。
2. pytest -q：20 passed（7.34s，完整门禁再次 6.58s）；含真实 MySQL 全迁移往返、原测试和 8 项鉴权/脱敏专项。
3. npm run test:ui：15 passed，32.6s；3 个尺寸都实际经 H5→FastAPI→MySQL 登录 A、刷新、退出、登录 B，检查无 A 草稿和身份残留。
4. python scripts/check.py：秘密扫描、5 扫描器测试、CI YAML、ruff、20 后端测试、前端 typecheck/lint/build、git diff：PASS。
5. Cookie httpOnly、数据库 token 哈希、过期/伪造、停用、复制 cookie 注销重放、恶意 user_id、跨 Origin 变更、验证错误不回显密码：PASS。
6. git check-ignore .env/.env.deepseek/.cache/demo-accounts.json：PASS，未读取/回显 Key。
7. CI mobile job 增加自己的真实 API/MySQL/合成账户，浏览器测试不以 Mock 登录替代真实链路。

首次前端类型检查发现 uni-app RequestOptions 不声明 PATCH，删除当前尚未使用的 PATCH 方法声明；后续实际需要 PATCH 时再在平台适配层实现，未用强制类型转换掩盖不兼容。
API 已重载为新鉴权代码，H5 已重启加载同源代理。截图 docs/demos/T04-login-360/390/430.png，只含空白登录表单。

## 未完成与下一步

当前只交付鉴权，不冒充已完成聊天/记忆/任务的完整 A/B 越权验收；资源隔离在其对应任务继续测试。
T05 将删除真实流程中的示例对话，接入持久会话/消息/历史；UI-FIX-01 会独立完成聊天状态、IME/多行/引导/滚动验收。
真实 DeepSeek/高德/推送请求和费用 0，模型 Key 运营入口准备不等于服务接通。
