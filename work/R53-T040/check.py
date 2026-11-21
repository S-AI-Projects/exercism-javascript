#!/usr/bin/env python3
"""Verify Binary's named place-value cases and run the reference test suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib


EXERCISE = Path("exercises/practice/binary")
NAMED = {"0 is decimal 0": ("0", 0), "1 is decimal 1": ("1", 1), "10 is decimal 2": ("10", 2)}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared(exercise: Path, role: str) -> Path:
    config = json.loads((exercise / ".meta/config.json").read_text())
    paths = config.get("files", {}).get(role)
    if not isinstance(paths, list) or len(paths) != 1:
        fail(f"config.json must map files.{role} to one path")
    relative = Path(paths[0])
    path = (exercise / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(exercise.resolve()) or not path.is_file():
        fail(f"files.{role} is missing or outside the exercise: {relative}")
    return path


def inspect(exercise: Path) -> dict[str, object]:
    canonical = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    solution, spec, example = (declared(exercise, role) for role in ("solution", "test", "example"))
    source = spec.read_text()
    titles = [title for _quote, title in re.findall(r"\b(?:x?test)\(([\"'])(.*?)\1", source)]
    if len(canonical) != 15 or not titles:
        fail(f"unexpected case counts: {len(canonical)} canonical, {len(titles)} spec cases")
    observed = {}
    for title, (binary, decimal) in NAMED.items():
        pattern = rf"(?:x?test)\('{re.escape(title)}',[\s\S]*?Binary\('{binary}'\)\.toDecimal\(\)\)\.toEqual\({decimal}\)"
        if not re.search(pattern, source):
            fail(f"case {title!r} does not assert Binary({binary!r}) -> {decimal}")
        observed[title] = {"input": binary, "expected": decimal}
    return {
        "config_file_map": {
            role: str(path.relative_to(exercise.resolve()))
            for role, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_count": len(canonical), "spec_case_count": len(titles),
        "decision_table": observed, "case_names": titles,
    }


def run(root: Path, source: Path, destination: Path) -> dict[str, object]:
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("node_modules"))
    solution, spec, example = (declared(destination, role) for role in ("solution", "test", "example"))
    spec.write_text(spec.read_text().replace("xtest(", "test("))
    shutil.copyfile(example, solution)
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    report = destination / "binary-jest-results.json"
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--", "--watchAll=false", "--runInBand",
               "--json", f"--outputFile={report}"]
    child = subprocess.run(command, cwd=destination, env=env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, check=False)
    if not report.is_file():
        fail("Jest did not create its JSON report\n" + child.stdout[-2500:])
    jest = json.loads(report.read_text())
    counts = {
        "total": int(jest.get("numTotalTests", 0)),
        "passed": int(jest.get("numPassedTests", 0)),
        "failed": int(jest.get("numFailedTests", 0)),
        "pending": int(jest.get("numPendingTests", 0)),
    }
    executed = counts["passed"] + counts["failed"]
    return {"command": command, "returncode": child.returncode, "counts": counts,
            "executed": executed, "output": child.stdout}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    root = parser.parse_args().root.resolve()
    exercise = root / EXERCISE
    details = inspect(exercise)
    learner = declared(exercise, "solution")
    before = sha(learner)
    with tempfile.TemporaryDirectory(prefix="R53-T040-") as temp:
        result = run(root, exercise, Path(temp) / "exercise")
    after = sha(learner)
    if before != after:
        fail("learner stub changed during the reference check")
    executed = result["executed"]
    if executed == 0:
        fail("zero-test run rejected: no test cases executed")
    if result["returncode"] != 0:
        fail("Jest child exited non-zero\n" + str(result["output"])[-2500:])
    if result["counts"]["failed"] != 0 or result["counts"]["pending"] != 0:
        fail(f"expected all {executed} cases to pass, got {result['counts']}")
    evidence = {
        "exercise": str(EXERCISE), "python_version": sys.version,
        "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
        "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
        "metadata_and_decision_table": details, "learner_sha256_before": before,
        "learner_sha256_after": after, "reference_run": result,
    }
    output = root / "work/R53-T040/evidence.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: named binary cases and all {executed} enabled cases pass")
    print(f"Executed Jest cases: {executed}")
    print(f"Evidence: {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
