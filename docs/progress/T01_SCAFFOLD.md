# T01：仓库底座

- 日期：2026-10-26
- 当前：本地验收通过；待本次提交推送及 GitHub CI 核验。
- T00 最终证据：291777e16c7848c5d50ba23a2e9ebf9f45fec720；ls-remote 与 HEAD 一致，已推送。T00 无工作流，CI N/A。

## 实现

仓库分层、README、AGENTS、任务状态、范围 ADR、环境示例、忽略规则、行尾规则。
uni-app Vue3/TS H5 可启动骨架，FastAPI 真实根路由与 OpenAPI。
Python 哈希依赖锁与 npm lock，PowerShell 安装/启动脚本、跨平台检查脚本。
GitHub Actions：安全扫描、Python lint/format/pytest、H5 typecheck/lint/build；失败不忽略。
独立 MySQL Compose 仅提供配置，未启动数据库或执行迁移；未连接 ALE_AI_MySQL。

## 实测

| 检查 | 结果 |
|---|---|
| Python venv 创建、requirements.lock 安装 | PASS |
| pip check | PASS |
| npm install 锁定依赖 | PASS；首次类型包 peer 冲突已调整为 DCloud 要求的 3.4.31 |
| scripts/check.py | PASS；安全扫描、5 个安全负例测试、CI 结构、ruff、3 个 API 测试、TS、ESLint、H5 build |
| 故意加入 number→string 类型错误 | typecheck 返回 2，证明门禁拒绝错误；临时文件随后删除，完整检查重新通过 |
| Compose config --quiet | PASS；仅进程内合成占位值，不创建真实数据库 |
| git check-ignore | .env/.env.local/db/logs/node_modules/dist 均忽略 |
| 本机 HTTP | 127.0.0.1:8000/ 和 127.0.0.1:5173/ 均 200 |
| 浏览器实际页面 | 显示 T01 骨架及功能尚未接入；docs/demos/T01-scaffold.png |

Python TestClient 有一条上游 httpx 弃用警告，3 个 API 测试均通过，不影响当前结果。
前端构建最初发生 CJS/ESM 插件加载问题，按官方模板的模块方式修正，ESLint 配置使用 mjs，复测通过。
最终远端 CI 必须实际运行后才能判断；本地脚本解析不能替代 GitHub CI。

## 已知限制

依赖审计有 33 条告警（21 high / 4 moderate / 8 low，含传播链），见 docs/DEPENDENCY_REVIEW.md。
不宣称依赖安全审计通过，不公开部署服务。
任务书原件此前已读取，本次下载路径已不可读，未伪造原件副本。八份基线仍缺失。
用户后补组件清单已读取；来源/许可/跨端选择在 T02 记录，不在 T01 插入业务 UI。
DeepSeek 请求数 0，费用 0；数据库迁移与业务接口尚未实现。
