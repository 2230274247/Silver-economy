# T01 依赖核验

## 版本与许可依据

以 [DCloud 官方 CLI 文档](https://uniapp.dcloud.net.cn/quickstart-cli) 和
[vite-ts 官方模板](https://github.com/dcloudio/uni-preset-vue/tree/vite-ts) 为兼容依据。
模板当前固定 DCloud 3.0.0-5020620260917001 与 Vite 5.2.8。
实际 npm 元数据：uni-app/uni-h5/vite-plugin-uni 为 Apache-2.0；Vue 为 MIT。
只安装 H5 所需包，未为未交付的小程序/App 安装全部平台编译器。
FastAPI/pytest 为 MIT，Ruff 为 MIT，Python/PyYAML 等传递依赖以锁定分发包内许可为准。
新增组件或发布分发前再次核对所用包及资源许可，不将展示站等同可复制源码授权。

## 实际风险扫描

2026-10-26 执行 npm audit --json：共 33 条，21 high、4 moderate、8 low、0 critical；
包含父包继承依赖风险的条目，不等于 33 个独立漏洞。
执行非强制 npm audit fix 后数量未改变，锁定的上游版本不能由兼容更新自动解决。
原始报告仅保存在本地忽略目录 .cache/npm-audit-T01.json。

主要涉及 Vite 开发服务器、Vue/server-renderer、DCloud 构建链中固定的
Intlify、Express、PostCSS、adm-zip、source-map-js 等版本。
自动建议含 undefined@undefined 或退回旧主版本的 DCloud 包，未执行强制升级。
uni-app 的编译器与 Vue 配套，不能未经验证替换核心版本并宣称兼容。

当前仅本机合成数据 Demo：服务绑定 127.0.0.1，关闭 uniStatistics，
不启用 SSR，不使用富文本/原始 HTML，不公开部署，不处理真实用户资料。
这些约束不等于漏洞已修复；依赖审计状态为 KNOWN_ISSUES，不能报告零漏洞。
后续发布前需专项评估兼容升级与安全修复，涉及切换框架或公开部署时由用户决策。
CI 的秘密扫描/功能检查与依赖风险状态分别记录，不用 continue-on-error 掩盖失败的核心检查。
