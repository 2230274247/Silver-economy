"""Private launch gate: no service starts until its Windows job has been assigned."""

import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.stdin.buffer.readline(16) != b"start\n":
        return 0
    from dev_processes import join_job

    join_job(sys.argv[2])
    action = sys.argv[1]
    if action == "worker":
        sys.path.insert(0, str(ROOT / "services/api"))
        sys.argv = ["silver-worker"]
        runpy.run_module("app.notifications.worker", run_name="__main__")
        return 0
    if action == "h5":
        command = [
            shutil.which("node"),
            str(ROOT / "apps/mobile/node_modules/@dcloudio/vite-plugin-uni/bin/uni.js"),
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
            "--strictPort",
        ]
        return subprocess.call(command, cwd=ROOT / "apps/mobile")
    if action == "mysql":
        from dotenv import dotenv_values

        values = dotenv_values(ROOT / ".env")
        if (
            values.get("MYSQL_DATABASE") != "silver_memory_demo_v01"
            or values.get("MYSQL_PORT") != "13306"
            or values.get("MYSQL_USER") != "silver_demo"
            or not values.get("MYSQL_PASSWORD")
            or not values.get("MYSQL_ROOT_PASSWORD")
        ):
            print("[MAIN] 项目 .env 数据库配置不完整；请查看启动手册。", flush=True)
            return 1
        env = dict(os.environ)
        env.update({k: v for k, v in values.items() if k.startswith("MYSQL_") and v})
        result = subprocess.call(
            [
                shutil.which("docker"),
                "compose",
                "-f",
                str(ROOT / "docker-compose.dev.yml"),
                "up",
                "-d",
                "--no-recreate",
                "--wait",
                "--wait-timeout",
                "90",
                "mysql",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result:
            print("[MAIN] MySQL启动失败：请检查Docker Desktop及项目.env。", flush=True)
        return result
    raise ValueError("Unsupported development child")


if __name__ == "__main__":
    raise SystemExit(main())
