"""Run Cosmic Ray in a disposable source copy and enforce the mutation policy."""

import ast
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import toml
from cosmic_ray.work_db import use_db
from cosmic_ray.work_item import TestOutcome, WorkerOutcome

ROOT = Path(__file__).resolve().parents[1]


def target_spans(source, target):
    spans = []
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = [node.name] if node.name in target["functions"] else []
        elif isinstance(node, ast.Assign):
            names = [
                n.id
                for n in node.targets
                if isinstance(n, ast.Name) and n.id in target["assignments"]
            ]
        else:
            continue
        for name in names:
            if name in found:
                raise ValueError(f"Ambiguous mutation target: {name}")
            found.add(name)
            spans.append((node.lineno, node.end_lineno))
    expected = set(target["functions"] + target["assignments"])
    if found != expected:
        raise ValueError(f"Missing mutation targets: {sorted(expected - found)}")
    return spans


def score_counts(counts):
    if set(counts) - {"killed", "survived", "timeout", "error", "pending"} or any(
        type(value) is not int or value < 0 for value in counts.values()
    ):
        raise ValueError("Mutation counts must be nonnegative integers with known outcomes")
    total = sum(counts.values())
    return 100 * counts.get("killed", 0) / total if total else 0.0


def qualifies(counts, break_score):
    return (
        sum(counts.values()) > 0
        and not counts.get("error", 0)
        and not counts.get("pending", 0)
        and score_counts(counts) >= break_score
    )


def negative_median_probe(directory, command):
    path = directory / "src/analyzer.py"
    original = path.read_text(encoding="utf-8")
    tree = ast.parse(original)
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "median_cycle_time" for t in node.targets)
    ]
    if len(nodes) != 1:
        raise ValueError("Expected one median assignment")
    node = nodes[0]
    lines = original.splitlines(keepends=True)
    lines[node.lineno - 1 : node.end_lineno] = [
        " " * node.col_offset + "median_cycle_time = -999.0\n"
    ]
    try:
        path.write_text("".join(lines), encoding="utf-8")
        result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=30)
        # Require an assertion failure from the median behavior test, not an import/runtime error.
        output = result.stdout + result.stderr
        return (
            result.returncode != 0
            and "AssertionError" in output
            and "FAIL: test_median_cycle_time_for_even_odd_empty_and_single_samples" in output
        )
    finally:
        path.write_text(original, encoding="utf-8")


def run_cosmic(directory, *args):
    subprocess.run(
        [sys.executable, "-c", "from cosmic_ray.cli import cli; cli()", *args],
        cwd=directory,
        check=True,
    )


def summarize(database, excluded):
    counts = Counter({"killed": 0, "survived": 0, "timeout": 0, "error": 0, "pending": 0})
    details = []
    with use_db(database) as db:
        counts["pending"] = len(db.pending_work_items)
        for work, result in db.completed_work_items:
            if (
                result.worker_outcome != WorkerOutcome.NORMAL
                or result.test_outcome == TestOutcome.INCOMPETENT
            ):
                outcome = "error"
            elif result.output == "timeout":
                outcome = "timeout"
            elif result.test_outcome in (TestOutcome.KILLED, TestOutcome.SURVIVED):
                outcome = result.test_outcome.value
            else:
                outcome = "error"
            counts[outcome] += 1
            mutation = work.mutations[0]
            details.append(
                {
                    "module": mutation.module_path.as_posix(),
                    "operator": mutation.operator_name,
                    "line": mutation.start_pos[0],
                    "outcome": outcome,
                }
            )
    return {
        "counts": dict(counts),
        "excluded": excluded,
        "score": score_counts(counts),
        "mutants": sorted(details, key=lambda row: (row["module"], row["line"], row["operator"])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-report",
        type=Path,
        help="Re-evaluate a saved report only; does not measure the current source",
    )
    args = parser.parse_args()
    policy = json.loads((ROOT / "quality/mutation-policy.json").read_text(encoding="utf-8"))
    if args.check_report:
        report = json.loads(args.check_report.read_text(encoding="utf-8"))
        passed = qualifies(report["counts"], policy["break_score"])
        print(
            f"Saved report score: {score_counts(report['counts']):.2f}%; "
            f"break: {policy['break_score']}%; qualified: {passed}"
        )
        return 0 if passed else 1
    output = ROOT / "test-results/mutation"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reports-mutation-") as temporary:
        directory = Path(temporary)
        for folder in ("src", "tests", "scripts"):
            shutil.copytree(
                ROOT / folder,
                directory / folder,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        shutil.copy2(ROOT / "cli.py", directory / "cli.py")
        command = [sys.executable, "-B", "scripts/run_tests.py"]
        subprocess.run(command, cwd=directory, check=True, stdout=subprocess.DEVNULL)
        if not negative_median_probe(directory, command):
            raise RuntimeError("The -999.0 median control was not killed by the behavior assertion")
        spans = {
            name: target_spans((directory / name).read_text(encoding="utf-8"), target)
            for name, target in policy["targets"].items()
        }
        config = {
            "cosmic-ray": {
                "module-path": list(spans),
                "timeout": policy["timeout_seconds"],
                "test-command": f'"{Path(sys.executable).as_posix()}" -B scripts/run_tests.py',
                "distributor": {"name": "local"},
            }
        }
        (directory / "mutation.toml").write_text(toml.dumps(config), encoding="utf-8")
        run_cosmic(directory, "init", "mutation.toml", "session.sqlite")
        with use_db(directory / "session.sqlite") as db:
            all_work = db.work_items
            selected = [
                work
                for work in all_work
                if all(
                    any(
                        start <= mutation.start_pos[0] <= end
                        for start, end in spans[mutation.module_path.as_posix()]
                    )
                    for mutation in work.mutations
                )
            ]
            if not selected:
                raise RuntimeError("No mutation work selected")
            excluded = len(all_work) - len(selected)
            db.clear()
            db.add_work_items(selected)
        print(f"Cosmic Ray: {len(selected)} selected; {excluded} outside target spans", flush=True)
        run_cosmic(directory, "exec", "mutation.toml", "session.sqlite")
        report = summarize(directory / "session.sqlite", excluded)
    report.update(
        {
            "policy": policy,
            "negative_median": "killed by assertion",
            "qualified": qualifies(report["counts"], policy["break_score"]),
        }
    )
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "mutants"}, indent=2))
    return 0 if report["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
