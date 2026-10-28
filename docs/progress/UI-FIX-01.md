# UI-FIX-01：紧凑输入与交互完整性

- 香港时间：2026-10-26 17:36 +08:00；本地验证完成，当前提交/推送/CI 待事后核验。
- 范围：原页面风格保留；不改已推送 T02，不改数据库/鉴权/原文保存接口。
- 文件：apps/mobile/index.html；AccessibleButton、AppButton、BottomTabs；pages/index/index.vue；platform/composer.ts；tests/composer.spec.ts。

## 结果与修复

三个建议只填草稿，不发请求；有消息后隐藏。空文本禁用麦克风，有文本显式发送；无附件/图片假入口。
输入采用单行基础高度与多行最大高度；支持 Enter 发送、Shift+Enter 换行，中文组合输入期间不发；忙碌时禁止重入。
实际测试暴露快速多行末尾丢字：uni-app 输入节流 100ms，原生输入需同步草稿；监听须在内置事件初始化后绑定，否则父级受控更新会覆盖原生值。
为每个页面实例建立独立输入 ID，避免 uni-app 缓存页面栈的同名节点绑定错误。H5 适配封装在 platform，非 H5 保留 uni 输入事件。
按钮增加错误/按下/加载语义，导航 15px、时间 15px；头像和布局不重做。

## 实际检查

- npm run lint -- --fix、npm run typecheck：PASS。
- npm run test:ui -- --max-failures=1：27 passed，1.3m。360/390/430 全部覆盖建议/IME/多行原文响应/空草稿/忙碌去重/网络失败相同 ID/长消息/新回复定位/导航/隔离。
- python scripts/check.py：28 后端/真实 MySQL 测试、5 扫描器测试、安全、YAML、Ruff、TS、lint、H5 build、diff PASS。
- 最初多行定位器失败后，确认 uni text 使用 br；测试改为精确断言服务端实际保存的完整换行原文，仍检查可见气泡及清空输入，未降低内容完整性要求。
- 截图：docs/demos/UI-FIX-01-keyboard-360.png、390.png、430.png，390 已视觉检查；原 T02/T05 截图保留。

## 限制与下一步

软键盘由 Playwright 聚焦+视口缩至 470px 模拟，不能宣称真实 Android 键盘通过。
目前模型仍未接入，费用 0。下一项 T06：Mock/DeepSeek 后端 Provider、真实用量日志、单次输出上限和全局每日门禁、测试服务强制 Mock，首次 live 仅一条短请求且禁止自动重试。
