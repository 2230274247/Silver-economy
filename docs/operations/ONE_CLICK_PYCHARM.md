# main.py一键启动、停止与PyCharm侧边网页

## 日常使用

用PyCharm打开Silver-economy根目录，解释器选项目.venv/Scripts/python.exe。Docker Desktop需已启动；本机.env与前端node_modules沿用现有配置，无需重新搭建。打开根目录main.py，在if __name__ == "__main__"附近或文件右键选择Run main；启动调试时选择Debug main。

默认读取已有本机模型配置：当前若配置真实DeepSeek，用户发消息就真实调用。需要反复调试而不扣额度，选择共享配置Silver - One Click Mock，或在main运行参数加--mock。默认共享配置为Silver - One Click，直接运行根main.py。

启动流程：检查8000/5173端口和本地依赖 → 启动/复用独立Compose MySQL → 启动H5与Worker → 在当前Python主进程启动FastAPI → 等API数据库就绪及H5 HTTP200后，自动打开 http://127.0.0.1:5173/#/ 。网页打开失败时控制台保留可点击网址。不会自动安装依赖、修改密钥、执行迁移或覆盖项目文件。

停止时点击本次Run/Debug窗口的红色Stop。API是主进程；H5/Worker及后代由Windows Job Object托管，主进程被强制终止也会自动结束本次业务子进程。浏览器窗口可以保留，但8000/5173停止后不能继续请求业务服务。MySQL是持久基础设施，刻意保留运行和数据；不是关闭Docker Desktop或删除容器/卷。不停止其他项目、旧进程或外部已运行的服务。

若8000或5173已有程序占用，一键入口会明确拒绝启动，不接管或强杀占用程序。先在原终端/IDE停止旧服务再Run。已有独立Worker请先自行停止，避免同项目两个扫描进程。该入口当前只支持Windows；原分项启动脚本保持可用。

## 网页与断点

Debug main后，在services/api/app/api/v1/chat.py的send_message中打断点，从网站发送消息就进入当前Python进程。模型与记忆断点仍见PYCHARM_DEBUG.md；Run只输出日志，Debug才能暂停/单步。API没有子进程、reload或多worker，不需要配置“自动附加子进程”才能命中聊天断点。

本入口为H5开发服务器设置10分钟请求等待上限，方便在Python断点停留；正常分项启动默认45秒，正式build仍45秒。上游模型自身超时/数据库事务超时没有因此取消。暂停较久后若网页异常，先恢复执行并刷新历史，不要在Live下反复发送或在Evaluate执行model.complete来重复扣费。

main控制台会同时显示[MAIN]启动状态、Vite、Worker和silver.model阶段日志。按消息request_id关联context_ready、request_persisted、model_call_started、model_call_returned、reply_persisted；天气路径另有weather_ready。完整正文/Prompt/原模型结果只在本机断点变量查看，日志不输出密钥或私有原文。

## PyCharm侧边栏网页：GBrowser

作者仓库：https://github.com/edgafner/GBrowser
官方Marketplace：https://plugins.jetbrains.com/plugin/14458-gbrowser

1. Settings > Plugins > Marketplace，搜索GBrowser（作者jonathan gafner），选择与你PyCharm版本兼容的版本安装，按IDE提示重启。
2. 从View > Tool Windows或侧边栏打开GBrowser，输入 http://127.0.0.1:5173/#/ 。工具窗口可拖到右侧，形成左边代码、右边网页、底部Debug/日志的布局。菜单名称随插件/IDE版本变化。
3. 可在Settings > Tools > GIdea Embedded Browser设置默认首页为该URL（作者文档给出的设置名），或添加书签。
4. 再Debug main，在侧边网页登录、聊天即可触发Python断点。内嵌浏览器与外部浏览器Cookie可能分开，需要分别登录。
5. 如果只想使用侧边网页，不希望同时弹出外部浏览器，在main的运行参数加--no-browser；Mock组合为--mock --no-browser。main.py本身默认仍自动打开系统浏览器，不控制第三方插件窗口自动弹出。

GBrowser使用JCEF（内嵌Chromium）。以Marketplace给出的当前IDE兼容提示为准；如果IDE没有可用JCEF，使用匹配的官方运行时/依赖，或先用外部浏览器。不绕过IDE保护或安装不兼容版本。本次仅核对作者及Marketplace说明，未代用户安装、未在实际PyCharm UI中验收插件。

GBrowser是网页显示工具；Python断点仍由PyCharm处理，前端Vue/JS断点需浏览器DevTools或对应前端调试功能。无论网页在IDE还是外部浏览器，均访问同一API，因此不影响Python断点。

## 验证证据

- 10项标准库unittest（含无site-packages模式）通过：占用端口不误杀、就绪后只打开一次浏览器、子进程失败停止API、就绪条件。
- Windows实际正常生命周期：启动API/H5/Worker，Mock消息保存与幂等通过；Python trace命中的send_message PID等于main PID；自动打开URL调用记录正确；正常关闭后8个Job成员退出，8000/5173关闭，MySQL保留。
- Windows强制停止：对本次API主进程调用TerminateProcess（等价于IDE强制结束的关键路径），10个记录在本次进程树中的进程全部退出，8000/5173关闭，MySQL保留。仅本次进程稳定句柄用于验证及清理。
- 证据docs/testing/DEV-02-normal.json、DEV-02-hard-stop.json；本地日志logs/dev-02-normal.log、dev-02-hard-stop.log。临时验证脚本在ignored .cache，不提交凭据。
- npm typecheck/lint/build:h5与Ruff、安全扫描通过，新增付费调用0，无数据库迁移。未执行实际PyCharm插件/鼠标点击验收，也未冒充Android通知或真实高德验证。
