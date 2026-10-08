"""Run pinned actionlint, retaining one hash-bound queue compatibility diagnostic."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MESSAGE = (
    'unexpected key "queue" for "concurrency" section. '
    'expected one of "cancel-in-progress", "group"'
)


def check_workflows(root=ROOT):
    workflow = root / ".github/workflows/sfl-pr-review-auto.yml"
    contract = json.loads((root / ".sfl/lint-contract.json").read_text())
    manifest = json.loads((root / ".sfl/sfl.json").read_text())
    if (
        manifest["version"] != contract["version"]
        or manifest["sourceSha"] != contract["source_sha"]
        or hashlib.sha256(workflow.read_bytes()).hexdigest() != contract["workflow_sha256"]
    ):
        raise ValueError("Reviewer workflow differs from its reviewed lint contract")
    result = subprocess.run(
        [
            "go",
            "run",
            "github.com/rhysd/actionlint/cmd/actionlint@v1.7.12",
            "-format",
            "{{json .}}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    diagnostics = json.loads(result.stdout or "[]")
    if not isinstance(diagnostics, list):
        raise ValueError("actionlint did not return its diagnostic list")
    if result.returncode and (not diagnostics or "exit status 1" not in result.stderr):
        raise RuntimeError("actionlint could not complete: " + result.stderr)
    for item in diagnostics:
        if (
            item["filepath"] != ".github/workflows/sfl-pr-review-auto.yml"
            or item["kind"] != "syntax-check"
            or item["message"] != MESSAGE
            or item["line"] != 243
            or item["column"] != 7
        ):
            raise ValueError("Workflow lint finding: " + json.dumps(item))
    if len(diagnostics) > 1:
        raise ValueError("Unexpected duplicate actionlint diagnostics")
    print("Workflow lint passed; canonical queue compatibility is hash-bound")


if __name__ == "__main__":
    check_workflows()
