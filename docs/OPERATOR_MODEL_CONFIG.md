# 运营方后端模型配置入口

本机专用文件：项目根 `.env.deepseek`；只在本机填写 `DEEPSEEK_API_KEY` 并保存。
不要在聊天中发送 Key，不在用户网页填写；不修改数据库凭据所在的 .env。
后端按 .env、.env.deepseek 顺序读取，进程环境变量优先。真实文件由 .gitignore 排除，提交前仍执行安全扫描。

T06 已实现后端 Provider 和实际额度门禁，T06–T09 已保存少量真实联调证据。
`LLM_PROVIDER=mock` 不请求模型服务；运营使用 `deepseek` 模式时由后端读取 Key。
配置与取值校验见 `services/api/app/core/config.py`；API Key 不提供给普通用户界面。

已实现并测试的限制（2026-10-27 核对）：

- 自动测试/CI 全部 Mock；live smoke 只发一轮短合成消息。
- 默认单次最大输出 256 token；每日最多 10 次真实调用、20000 个保守预留 token，所有用户和 API 进程共享 MySQL 预算。
- 同一请求幂等，不因重复点击再次调用；不自动重试供应商请求。
- 记录请求 ID、模型、输入/输出 token、耗时和可核验的估算费用，不记录 Key/私密全文。
- token 上限和次数上限不是固定金额承诺；单价、缓存及其他计费项以调用时官方/账户规则为准。
- 未配置/余额不足/超时等显示实际错误，不以静态回复冒充 DeepSeek。
- `DEEPSEEK_DAILY_REQUEST_LIMIT` 或 `DEEPSEEK_DAILY_TOKEN_LIMIT` 设为 0 可停用真实调用；配置变更需重启后端。
- 批量记忆评估强制 Mock，并阻断真实 HTTP 传输，不因数据规模增加真实模型调用。

保存后无需把内容发给助手；后端重启后读取。运营配置不影响普通用户界面和 A/B 隔离。
详细预算、未知结果和用量记录规则见 `docs/operations/DEEPSEEK.md`。
