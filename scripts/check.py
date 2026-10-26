"""Run the same required gates as CI, stopping on the first failure."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = (
    ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
)
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable
NPM = shutil.which("npm.cmd" if os.name == "nt" else "npm")


def run(args: list[str], cwd: Path = ROOT) -> None:
    print("RUN", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    if not NPM:
        raise SystemExit("npm is required")
    run([PYTHON, "scripts/security_scan.py"])
    run([PYTHON, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py"])
    run([PYTHON, "scripts/validate_workflow.py"])
    run([PYTHON, "-m", "ruff", "check", "app", "tests"], ROOT / "services/api")
    run(
        [PYTHON, "-m", "ruff", "format", "--check", "app", "tests"],
        ROOT / "services/api",
    )
    run([PYTHON, "-m", "ruff", "check", "scripts"])
    run([PYTHON, "-m", "ruff", "format", "--check", "scripts"])
    run([PYTHON, "-m", "pytest", "-q"], ROOT / "services/api")
    for task in ["typecheck", "lint", "build:h5"]:
        run([NPM, "run", task], ROOT / "apps/mobile")
    run(["git", "diff", "--check"])


if __name__ == "__main__":
    main()
