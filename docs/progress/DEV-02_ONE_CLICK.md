# DEV-02 main.py一键启停与IDE侧边网页指引

时间：2026-10-28T10:47:51+08:00，Asia/Hong_Kong。用户要求根目录main函数Run自动启动和开网页、Stop结束业务服务，并在PyCharm侧边访问网站/断点/看日志。

实现：根main.py保留API在当前进程，模块式uvicorn无reload/多worker；H5/Worker/启动数据库CLI为门控子进程，经Windows Job Object托管，最后句柄关闭即结束本次后代。Windows虚拟环境redirector可能产生额外解释器层，helper在启动业务前也自行加入唯一命名Job，门控stdin避免父进程早退后继续启动。端口占用只拒绝，不接管/误杀。数据库仅调用本项目Compose mysql up --no-recreate --wait，沿用持久卷、不迁移/删数据、停止时保留MySQL。新增2个共享main运行配置，保留旧分项脚本与IDE设置。

自动开网页只在API数据库ready和H5 HTTP200后执行一次；浏览器失败给网址。默认沿用本机真实Provider，可--mock反复调试；--no-browser适合侧边栏。H5一键开发等待设600000ms（有限且仅DEV生效），分项与正式build默认45000ms；未取消上游模型超时或自动重试限制。无其他业务改动。

插件：核对GBrowser作者仓库与Marketplace14458，文档提供安装/右侧停靠/首页/独立Cookie步骤；JCEF及IDE兼容性由Marketplace校验，未自动安装或声称已在用户IDE验收。此插件不是模型接口，也不需要项目API Key。

实际验证命令：.venv/Scripts/python.exe -m unittest discover -s scripts -p test_*.py（10通过）；另以-S无第三方site-packages模式10通过，兼容CI security job。Ruff检查/格式通过；apps/mobile下npm.cmd run typecheck、lint、build:h5通过；安全扫描通过。

实际Windows进程实跑：本机ignored .cache/dev-02-normal.py启动main(['--mock'])，记录就绪后开URL回调、真实HTTP Mock消息保存/刷新/幂等，Python函数trace确认send_message与main同PID；正常退出8个Job成员全部结束。随后.cache/dev-02-hard-stop.py实际启动main.py --mock --no-browser，记录本次进程树并持有稳定句柄，强制结束API进程后10个进程全部退出。两轮8000/5173均关闭、13306保持；没有广泛taskkill或按进程名误杀。原日志与JSON证据路径见操作手册。浏览器自动打开调用以回调记录验证，未伪造实际系统浏览器/IDE插件截图。

新增付费模型/搜索调用0；只新增明确Synthetic Mock调试会话，未修改历史聊天、密钥或冻结需求，未访问ALE_AI_MySQL。实际PyCharm UI内点击Debug/Stop及插件交互仍待用户机器操作确认；已验证等价Python trace与Windows强制终止路径。不宣称全V0.1最终验收通过。

前序DEV-01 b1f3b4febf1c0a9c13e677d805340bb428db0780两个CI40476567242/40476574513均success。本次只提交推送dev/v0.1并事后核对SHA/CI，不改main或历史。
