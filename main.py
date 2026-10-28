"""Run/Debug this file in PyCharm: API stays in this process for breakpoints."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from scripts.dev_processes import OwnedChildren

ROOT = Path(__file__).resolve().parent
WEBSITE = "http://127.0.0.1:5173/#/"


def check_port(port):
    with socket.socket() as probe:
        # Windows' default bind permits reuse in cases that POSIX rejects.
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(
                f"端口 {port} 已被占用，请先停止原服务；不会自动结束占用进程。"
            ) from None


def ready(client):
    try:
        api = client.get("http://127.0.0.1:8000/api/v1/readyz")
        page = client.get("http://127.0.0.1:5173/")
        return (
            api.status_code == 200
            and api.json().get("status") == "ready"
            and page.status_code == 200
        )
    except (OSError, ValueError):
        return False


def watch_services(server, children, stop, failed, open_browser):
    import httpx

    deadline = time.monotonic() + 120
    opened = False
    with httpx.Client(timeout=2, trust_env=False) as client:
        while not stop.wait(0.5):
            if any(process.poll() is not None for process in children):
                print("[MAIN] H5或Worker已退出，正在停止整套业务服务。", flush=True)
                failed.set()
                server.should_exit = True
                return
            if opened:
                continue
            try:
                available = server.started and ready(client)
            except httpx.HTTPError:
                available = False
            if available:
                print(f"[MAIN] 服务就绪：{WEBSITE}", flush=True)
                print(
                    "[MAIN] API在当前Python进程，可直接命中聊天代码断点。", flush=True
                )
                opened = True
                if open_browser:
                    try:
                        browser_opened = webbrowser.open(WEBSITE)
                    except (webbrowser.Error, OSError):
                        browser_opened = False
                    if not browser_opened:
                        print("[MAIN] 未能自动打开浏览器，请点击上方网址。", flush=True)
            elif time.monotonic() >= deadline:
                print("[MAIN] 启动等待超时，请检查数据库迁移和H5日志。", flush=True)
                failed.set()
                server.should_exit = True
                return


def main(argv=None):
    parser = argparse.ArgumentParser(description="银发经济一键启动（Windows）")
    parser.add_argument(
        "--mock", action="store_true", help="模型、地图、通知均用Mock，不扣模型额度"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="不自动开外部浏览器，供IDE侧边栏使用"
    )
    args = parser.parse_args(argv)
    if os.name != "nt":
        raise RuntimeError("此一键入口使用Windows进程保护；其他平台请沿用分项启动。")
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise RuntimeError("请在PyCharm选择本项目 .venv/Scripts/python.exe 解释器。")
    for port in (8000, 5173):
        check_port(port)
    if not shutil.which("node") or not shutil.which("docker"):
        raise RuntimeError("请安装Node.js并启动Docker Desktop，确保node/docker可用。")
    if not (
        ROOT / "apps/mobile/node_modules/@dcloudio/vite-plugin-uni/bin/uni.js"
    ).is_file():
        raise RuntimeError("前端依赖缺失，请在apps/mobile执行npm ci。")
    if not (ROOT / ".env").is_file():
        raise RuntimeError("缺少本机.env，请先按已有项目初始化说明配置数据库。")
    if args.mock:
        os.environ.update(
            LLM_PROVIDER="mock", MAPS_PROVIDER="mock", NOTIFICATIONS_PROVIDER="mock"
        )
    sys.path.insert(0, str(ROOT / "services/api"))
    import uvicorn
    from app.core.config import get_settings, validated_database_url

    settings = get_settings()
    validated_database_url(settings.database_url.get_secret_value())
    env = dict(
        os.environ,
        PYTHONUNBUFFERED="1",
        API_PROXY_TARGET="http://127.0.0.1:8000",
        VITE_DEV_REQUEST_TIMEOUT_MS="600000",
    )
    print(f"[MAIN] 启动Silver-economy；模型模式={settings.llm_provider}", flush=True)
    print("[MAIN] MySQL作为持久依赖保留；Stop只结束本次API/H5/Worker。", flush=True)
    owned = OwnedChildren()
    stop, failed = threading.Event(), threading.Event()
    monitor = None
    try:
        mysql = owned.start("mysql", env)
        if mysql.wait(timeout=110):
            raise RuntimeError("独立MySQL未就绪，业务服务未启动。")
        children = [owned.start("h5", env), owned.start("worker", env)]
        server = uvicorn.Server(
            uvicorn.Config(
                "app.main:app",
                host="127.0.0.1",
                port=8000,
                access_log=False,
                workers=1,
            )
        )
        monitor = threading.Thread(
            target=watch_services,
            args=(server, children, stop, failed, not args.no_browser),
            daemon=True,
            name="silver-startup",
        )
        monitor.start()
        # Deliberately no subprocess, reload or extra worker for the API.
        server.run()
        return 1 if failed.is_set() or not server.started else 0
    finally:
        stop.set()
        owned.close()
        if monitor:
            monitor.join(timeout=5)
        print("[MAIN] API/H5/Worker已停止；数据库及数据保留。", flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pass
    except RuntimeError as error:
        print(f"[MAIN] 启动失败：{error}", file=sys.stderr, flush=True)
        raise SystemExit(1) from None
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(
            f"[MAIN] 启动失败：{type(error).__name__}，请检查本机配置。",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from None
