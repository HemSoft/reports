"""Local source/secret checks plus executable-dependency policy validation."""

import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from html.parser import HTMLParser

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_FILES = {
    "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.js": "node_modules/chart.js/dist/chart.umd.js",
}


def check_browser_versions():
    """Require browser URLs and npm metadata to identify the same pinned release."""
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    versions = {}
    for name in ("chart.js", "three"):
        declared = package["devDependencies"][name]
        installed = json.loads(
            (ROOT / "node_modules" / name / "package.json").read_text(encoding="utf-8")
        )["version"]
        if declared != installed or declared != lock["packages"][f"node_modules/{name}"]["version"]:
            raise ValueError(f"Browser dependency metadata versions differ: {name}")
        versions[name] = declared
    for url in SCRIPT_FILES:
        npm = re.search(r"/npm/(chart\.js|three)@([^/]+)/", url)
        classic = re.search(r"/three\.js/r(\d+)/", url)
        if npm:
            name, release = npm.groups()
        elif classic:
            name, release = "three", f"0.{classic[1]}.0"
        else:
            raise ValueError(f"Browser dependency URL does not pin a known release: {url}")
        if release != versions[name]:
            raise ValueError(f"Browser URL version differs from npm dependency: {url}")


def verified_digest_pattern(rendered_html=None):
    """Only verified public SRI values are exempt from secret entropy detection."""

    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__()
            self.external = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "script" and "src" in attributes:
                self.external.append(attributes)

    parser = Scripts()
    parser.feed(
        rendered_html
        if rendered_html is not None
        else (ROOT / "src/template.py").read_text(encoding="utf-8")
    )
    tags = []
    for attributes in parser.external:
        integrity = attributes.get("integrity", "")
        if attributes.get("crossorigin") != "anonymous" or not integrity.startswith("sha384-"):
            raise ValueError("External browser script lacks SHA-384 SRI or anonymous CORS")
        tags.append((attributes["src"], integrity.removeprefix("sha384-")))
    bundled = [
        (url, digest)
        for url, digest in tags
        if url.startswith("data:application/javascript;base64,")
    ]
    external = [(url, digest) for url, digest in tags if (url, digest) not in bundled]
    if (
        len(external) != len(SCRIPT_FILES)
        or {url for url, _ in external} != set(SCRIPT_FILES)
        or len(bundled) != (1 if rendered_html is not None else 0)
    ):
        raise ValueError("Browser script/SRI inventory differs from pinned dependencies")
    digests = []
    for url, digest in tags:
        if url.startswith("data:"):
            if not url.endswith("#report-graphics.js"):
                raise ValueError("Unknown embedded graphics asset")
            data = base64.b64decode(url.split(",", 1)[1].split("#", 1)[0], validate=True)
            if data != (ROOT / "assets/report-graphics.js").read_bytes():
                raise ValueError("Embedded graphics bytes differ from verified bundle")
        else:
            data = (ROOT / SCRIPT_FILES[url]).read_bytes()
        expected = base64.b64encode(hashlib.sha384(data).digest()).decode()
        if digest != expected:
            label = "report-graphics.js" if url.startswith("data:") else url
            raise ValueError(f"Browser integrity digest does not match pinned bytes: {label}")
        digests.append(re.escape(digest))
    return "^(?:sha384-)?(?:" + "|".join(digests) + ")$"


def check_reference(reference, visited):
    if not reference.startswith("./"):
        if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", reference):
            raise ValueError(f"Mutable action reference: {reference}")
        return
    target = (ROOT / reference).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise ValueError("Local action escapes the repository")
    if target.is_file() and target.parent == (ROOT / ".github/workflows").resolve():
        return  # Reusable workflows are checked by the full workflow loop.
    manifests = [target / name for name in ("action.yml", "action.yaml")]
    manifest = next((path for path in manifests if path.is_file()), None)
    if manifest is None:
        raise ValueError(f"Missing local action manifest: {reference}")
    if manifest in visited:
        return
    visited.add(manifest)
    action = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    for step in action["runs"].get("steps", []):
        if "uses" in step:
            check_reference(step["uses"], visited)


def check_policy():
    """Reject mutable external actions and excess Pages job permissions."""
    for path in (ROOT / ".github/workflows").iterdir():
        if path.suffix not in {".yml", ".yaml"}:
            continue
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        references = []
        for job in workflow["jobs"].values():
            if "uses" in job:
                references.append(job["uses"])
            references.extend(step["uses"] for step in job.get("steps", []) if "uses" in step)
        for reference in references:
            check_reference(reference, set())
        for name, job in workflow["jobs"].items():
            permissions = job.get("permissions", workflow.get("permissions", {}))
            expected = (
                {"pages": "write", "id-token": "write"}
                if path.stem == "pages" and name == "deploy"
                else {"contents": "read"}
            )
            if permissions != expected:
                raise ValueError(f"Unexpected permissions in {path.name}/{name}")


def scan_secrets(digest_pattern=None, verified_vendor=()):
    """Scan tracked files without network verification; never print secret values."""
    command = [sys.executable, "-X", "utf8", "-m", "detect_secrets", "scan", "--no-verify"]
    if digest_pattern:
        command.extend(["--exclude-secrets", digest_pattern])
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=120,
    )
    findings = {
        filename: items
        for filename, items in json.loads(result.stdout)["results"].items()
        if filename.replace("\\", "/") not in verified_vendor
    }
    for filename, items in findings.items():
        for item in items:
            print(f"Potential secret: {filename}:{item['line_number']} ({item['type']})")
    if findings:
        raise ValueError("Secret scan requires investigation")
    print("Secret scan: no findings in tracked files (network verification disabled)")


def main():
    check_policy()
    check_browser_versions()
    # Rebuild before allowing the exact generated vendor file in the secret scan.
    subprocess.run(
        ["node", "scripts/build_browser_assets.js", "--check"], cwd=ROOT, check=True, timeout=120
    )
    subprocess.run(
        [sys.executable, "scripts/generate_fixture.py"], cwd=ROOT, check=True, timeout=120
    )
    rendered = (ROOT / "test-results/report.html").read_text(encoding="utf-8")
    scan_secrets(verified_digest_pattern(rendered), ("assets/report-graphics.js",))
    subprocess.run(
        [sys.executable, "-m", "bandit", "-r", "src", "scripts", "cli.py", "-ll"],
        cwd=ROOT,
        check=True,
        timeout=120,
    )
    print("Security policy and local source checks: PASS")


if __name__ == "__main__":
    main()
