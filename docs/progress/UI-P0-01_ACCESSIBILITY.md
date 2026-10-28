# UI-P0-01 第一阶段无障碍修复

日期：2026-10-28（Asia/Hong_Kong）。范围仅为确认弹窗与行程六字段的可访问名称，不扩展主题、字体系统、业务功能或数据库。

## 基线与复现

分支 dev/v0.1；开始时工作区干净，HEAD 68d63a3139c8f26b93d4ed5f0b0673b9f2523642。基线 GitHub Actions 40625222710、40625228373 均 success。

先新增 tests/accessibility.spec.ts，再在旧实现执行：
`npm.cmd run test:ui -- tests/accessibility.spec.ts --project=390 --grep "memory confirmation|trip fields" --timeout=10000`。
两项实际失败：找不到名称为“删除这条长期记忆？”的 dialog；找不到名称为“车程变化通知阈值分钟数”的实际 spinbutton。失败先于实现，未删失败用例。测试使用合成拦截响应，不访问真实用户资料。

## 原因与最小修复

1. uni.showModal 的 H5 实现使用无对话框语义的容器和 DIV 操作，未建立焦点管理。新增 platform/confirmation.ts 与局部 confirmation.css，H5 使用原生 HTML dialog.showModal() 的模态背景隔离与真实 button；标题/说明关联，初始聚焦取消，Tab/Shift+Tab 循环，Enter/Space 激活，Esc 取消，close 清理并恢复仍存在的触发元素。通过 textContent 设置内容。原生分支仍直接委托 uni.showModal，确认参数及业务分支保持一致。
2. TripDetailCard 的 ARIA 原先停留在 uni-input 外层，实际 input 未命名。复用 labelTextControl，增加可选可见标签 ID，将 aria-labelledby 与 aria-label 写到实际输入；六字段有稳定的控件和标签 ID。watch 在展开、编辑和条件字段变化后 nextTick 重新绑定。原有字段文案、v-model、类型、验证、保存和取消代码不改。

已迁移三类确认：删除长期记忆、开启长期记忆、撤回通知设备。data-export 的单按钮提示仅位于非 H5 分支，不属于本次 H5 确认缺陷，保留原实现。

H5 弹窗 CSS 使用局部类选择器，避免 uni-app 将原生 button 标签选择器转换成 uni-button；显式居中、适配当前阅读字号。截图初查发现按钮样式未命中后已修正。最终 390px/22px 样本按钮约 139×59px，截图人工检查通过：.cache/ui-regression/p0-confirmation-390.png（合成数据，仅本机）。

## 测试覆盖

新增四项 Playwright 用例，每项覆盖三个既有视口：
- 删除确认的语义、说明、初始焦点、Tab/Shift+Tab、背景不可聚焦、Enter/Space、Esc、取消不发送删除、恢复焦点、确认只删除一次、有效触控尺寸。
- 开启长期记忆与设备撤回的键盘取消/确认，核对业务写请求数量。
- 六个实际 input 的名称和可见标签关联、折叠再展开、放弃不保存、无效时间不请求、失败保留中文/数字输入、重试和原有保存 payload。
- 18/20/22px 阅读字号刷新持久化、弹窗字号和取消焦点恢复。

旧 privacy/scheduling 测试选择器改为查找实际 dialog/button/input，不再依赖旧 DIV 或带 ARIA 的外包装。

## 实际验证

- 修复后 390px 新增四项：4 passed。
- 三尺寸相关回归：63 passed（4.8m），命令为 `npm.cmd run test:ui -- tests/accessibility.spec.ts tests/memory-controls.spec.ts tests/privacy.spec.ts tests/scheduling.spec.ts tests/shell.spec.ts tests/composer.spec.ts tests/memory.spec.ts`。新增用例补充触控尺寸、背景不可聚焦和可见标签关联断言后，`npm.cmd run test:ui -- tests/accessibility.spec.ts` 最终 12 passed（59.2s）。
- `npm.cmd run typecheck`、`npm.cmd run lint`、`npm.cmd run build:h5`：样式修正后最终复核全部通过。
- `git diff --check` 与 `.venv/Scripts/python.exe scripts/security_scan.py`：最终复核 PASS；提交前另执行暂存差异检查。
- 使用已安装 @dcloudio/uni-cli-shared 的 APP-PLUS 预处理器确认 H5 DOM/CSS 已排除；TypeScript 转译后以 uni.showModal stub 验证参数原样传递与取消结果返回：PASS。此为分支兼容检查，不是原生构建或真机验收。

相关回归只用 Mock/Synthetic 与独立 UI 测试账号，真实模型/地图/推送新增调用为 0。未修改后端或数据结构，不重复无关后端全套测试。

## 尚未验证

Android/iOS 真机系统弹窗和系统读屏、H5 Safari/WebView 真机 TalkBack/VoiceOver、真实中文输入法候选和软键盘均未实测。H5 使用现代浏览器 HTMLDialogElement.showModal；旧 WebView 不在本次已验证范围。现有时间控件行为保留，不把本次标签修复描述为已完成原生日期选择器升级。

提交、远端 SHA、CI：待实际提交后核验，不预填成功。

补充测试调整：新增“强制尝试聚焦背景触发器”断言时，原全局同名按钮查询在模态状态下同时命中背景触发器与弹窗确认按钮（strict mode violation）；已将该查询限定到原记忆卡片并允许查询被模态隐藏的背景元素。该轮 9 passed / 3 failed，均为同一定位歧义。此为测试定位修正，未改变业务或降低焦点约束断言。
