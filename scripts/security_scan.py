"""Scan Git-visible source files without reading ignored local credentials."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
AMAP_SECRET = re.compile(
    r"(?i:\b(?:AMAP_WEB_SERVICE_KEY|AMAP_KEY)\b[\"']?\s*[:=]\s*[\"']?[a-f0-9]{32}\b)"
)
PRIVATE_DIRS = {"uploads", "user_media", "backups", "logs", ".venv", "node_modules"}


def violations(path: str, content: str) -> list[str]:
    parts = Path(path).parts
    name = Path(path).name
    issues = []
    if (
        (name == ".env" or name.startswith(".env."))
        and name != ".env.example"
        or name == "auth.json"
        or Path(path).suffix in {".db", ".sqlite3", ".pem", ".key"}
        or PRIVATE_DIRS.intersection(parts)
    ):
        issues.append("private file must not be tracked")
    if SECRET.search(content) or AMAP_SECRET.search(content):
        issues.append("credential-like content detected (value suppressed)")
    return issues


def main() -> int:
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    failed = False
    for relative in sorted(set(filter(None, paths))):
        path = ROOT / relative
        if not path.is_file():
            continue
        # Source text only; binary demo screenshots are reviewed separately.
        raw = path.read_bytes()
        content = "" if b"\0" in raw else raw.decode("utf-8-sig", errors="replace")
        for issue in violations(relative, content):
            print(f"FAIL {relative}: {issue}")
            failed = True
    print("Security scan: " + ("FAIL" if failed else "PASS"))
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
