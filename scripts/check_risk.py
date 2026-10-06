"""Measure function risk with Radon and coverage.py; enforce reviewed risk caps."""

import argparse
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys

from radon.complexity import add_inner_blocks, cc_visit
from radon.visitors import Function

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "quality/risk-baseline.json"


def crap_score(complexity, coverage):
    if complexity < 1 or not 0 <= coverage <= 1:
        raise ValueError("Complexity must be positive and coverage must be in [0, 1]")
    return complexity**2 * (1 - coverage) ** 3 + complexity


def measure(root, coverage_data):
    if not coverage_data["meta"]["branch_coverage"]:
        raise ValueError("Branch coverage is required")
    files = {name.replace("\\", "/"): data for name, data in coverage_data["files"].items()}
    rows = []
    for path in sorted([root / "cli.py", *(root / "src").rglob("*.py")]):
        relative = path.relative_to(root).as_posix()
        # Missing files/functions fail closed, including never-imported production modules.
        functions = files[relative]["functions"]
        for block in add_inner_blocks(cc_visit(path.read_text(encoding="utf-8"))):
            if not isinstance(block, Function):
                continue
            matches = [
                (name, data)
                for name, data in functions.items()
                if name and data["start_line"] == block.lineno
            ]
            if len(matches) != 1:
                raise ValueError(f"Cannot match coverage for {relative}:{block.lineno}")
            name, data = matches[0]
            summary = data["summary"]
            branches = summary["num_branches"]
            if branches:
                coverage = summary["covered_branches"] / branches
                basis = "branch outcomes"
            else:
                # A branchless, unexecuted function must not receive vacuous 100% coverage.
                statements = summary["num_statements"]
                coverage = summary["covered_lines"] / statements if statements else 0.0
                basis = "statements (no branch outcomes)"
            score = crap_score(block.complexity, coverage)
            rows.append(
                {
                    "function": f"{relative}:{name}",
                    "line": block.lineno,
                    "complexity": block.complexity,
                    "coverage": coverage,
                    "basis": basis,
                    "covered_branches": summary["covered_branches"],
                    "branches": branches,
                    "covered_statements": summary["covered_lines"],
                    "statements": summary["num_statements"],
                    "crap": score,
                    "risk": "actionable" if score > 30 else "review" if score >= 15 else "low",
                }
            )
    return sorted(rows, key=lambda row: (-row["crap"], row["function"]))


def violations(rows, baseline):
    errors = []
    caps = baseline["functions"]
    for row in rows:
        name, score = row["function"], row["crap"]
        cap = caps.get(name, 30)
        if score > cap + 1e-9:
            errors.append(f"{name}: CRAP {score:.3f} exceeds cap {cap:.3f}")
    worst = max((row["crap"] for row in rows), default=0)
    if worst > baseline["worst"] + 1e-9:
        errors.append(f"Worst CRAP {worst:.3f} exceeds baseline {baseline['worst']:.3f}")
    return errors


def write_report(rows, errors):
    output = ROOT / "test-results"
    report = {
        "tools": {
            "complexity": f"radon {metadata.version('radon')}",
            "coverage": f"coverage.py {metadata.version('coverage')}",
        },
        "formula": "complexity^2 * (1 - coverage)^3 + complexity",
        "scope": "All functions/methods/closures in src/**/*.py and cli.py, including unexecuted code",
        "exclusions": "Tests and development scripts; module/class bodies and embedded JavaScript are not Python functions. No pragma coverage exclusions.",
        "functions": rows,
        "violations": errors,
    }
    (output / "risk.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Function risk",
        "",
        report["scope"],
        "",
        report["exclusions"],
        "",
        "| Function | CC | Covered branches | Coverage basis | CRAP | Risk |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['function']} | {row['complexity']} | "
            f"{row['covered_branches']}/{row['branches']} | "
            f"{row['coverage']:.1%} {row['basis']} | {row['crap']:.3f} | {row['risk']} |"
        )
    lines.extend(["", "Gate: " + ("FAIL" if errors else "PASS"), "", *errors, ""])
    (output / "risk.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args()
    (ROOT / "test-results").mkdir(exist_ok=True)
    for command in (["run", "scripts/run_tests.py"], ["json"]):
        subprocess.run([sys.executable, "-m", "coverage", *command], cwd=ROOT, check=True)
    data = json.loads((ROOT / "test-results/coverage.json").read_text(encoding="utf-8"))
    rows = measure(ROOT, data)
    errors = violations(rows, json.loads(args.baseline.read_text(encoding="utf-8")))
    write_report(rows, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
