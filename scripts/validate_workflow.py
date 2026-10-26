"""Check trigger/job structure; actual execution is verified on GitHub."""

from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
workflow = yaml.load(
    (root / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader
)
assert workflow["on"]["push"]["branches"] == ["dev/v0.1"]
assert workflow["on"]["pull_request"]["branches"] == ["main"]
assert set(workflow["jobs"]) == {"security", "api", "mobile"}
for job in workflow["jobs"].values():
    assert job["steps"]
    for step in job["steps"]:
        assert "continue-on-error" not in step
print("Workflow structure: PASS")
