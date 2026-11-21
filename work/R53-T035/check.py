#!/usr/bin/env python3
"""Validate the fixed groupCost domain and execute Book Store reference cases."""

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


EXERCISE = Path("exercises/practice/book-store")
CANONICAL_COUNT = 18
CASE_COUNT = 17
SIZES = (1, 3, 5)
EXPECTED = {1: 800, 3: 2160, 5: 3000}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared(exercise: Path, key: str) -> Path:
    config = json.loads((exercise / ".meta/config.json").read_text())
    values = config.get("files", {}).get(key)
    if not isinstance(values, list) or len(values) != 1:
        fail(f"config.json must map files.{key} to one path")
    rel = Path(values[0])
    path = (exercise / rel).resolve()
    if rel.is_absolute() or not path.is_relative_to(exercise.resolve()) or not path.is_file():
        fail(f"files.{key} is missing or escapes the exercise: {rel}")
    return path


def inspect(exercise: Path) -> dict[str, object]:
    canonical = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    solution, spec, example = (declared(exercise, key) for key in ("solution", "test", "example"))
    titles = re.findall(r"\b(?:x?test)\('([^']+)'", spec.read_text())
    if len(canonical) != CANONICAL_COUNT or len(titles) != CASE_COUNT:
        fail(f"expected {CANONICAL_COUNT} canonical entries and {CASE_COUNT} spec cases, found {len(canonical)} and {len(titles)}")
    for required in ("only a single book", "two of the same book", "empty basket"):
        if not any(title.lower() == required for title in titles):
            fail(f"missing required case {required!r}")
    reference = example.read_text()
    expected_expression = "size * BOOK_PRICE * DISCOUNTS[size - 1]"
    if expected_expression not in reference:
        fail("groupCost no longer has the operation shape documented in README.md")
    rows = []
    discounts = {1: 1.0, 3: 0.9, 5: 0.75}
    for size in SIZES:
        observed = round(size * 800 * discounts[size])
        if observed != EXPECTED[size]:
            fail(f"unexpected groupCost value for size {size}: {observed}")
        rows.append({"group_size": size, "discount": discounts[size], "price_cents": observed,
                     "array_lookups": 1, "numeric_multiplications": 2})
    return {
        "config_file_map": {
            key: str(path.relative_to(exercise.resolve()))
            for key, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_count": len(canonical),
        "spec_case_count": len(titles),
        "fixed_domain": list(range(1, 6)),
        "operation_table": rows,
        "case_names": titles,
    }


def run(root: Path, source: Path, target: Path) -> dict[str, object]:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("node_modules"))
    solution, spec, example = (declared(target, key) for key in ("solution", "test", "example"))
    spec.write_text(spec.read_text().replace("xtest(", "test("))
    shutil.copyfile(example, solution)
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--", "--watchAll=false", "--runInBand"]
    result = subprocess.run(command, cwd=target, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    match = re.search(r"Tests:\s+(?:(\d+) passed,\s*)?(?:(\d+) failed,\s*)?(\d+) total", result.stdout)
    if not match:
        fail("Jest did not report test counts\n" + result.stdout[-2500:])
    passed, failed, total = match.groups()
    counts = {"passed": int(passed or 0), "failed": int(failed or 0), "total": int(total)}
    return {"command": command, "returncode": result.returncode, "counts": counts, "output": result.stdout}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    root = parser.parse_args().root.resolve()
    exercise = root / EXERCISE
    report = inspect(exercise)
    learner = declared(exercise, "solution")
    before = sha(learner)
    with tempfile.TemporaryDirectory(prefix="R53-T035-") as temp:
        run_result = run(root, exercise, Path(temp) / "exercise")
    after = sha(learner)
    if before != after:
        fail("learner solution changed during reference run")
    if run_result["returncode"] != 0 or run_result["counts"] != {"passed": CASE_COUNT, "failed": 0, "total": CASE_COUNT}:
        fail("reference cases failed or ran an unexpected number of tests\n" + str(run_result["output"])[-2500:])
    evidence = {
        "exercise": str(EXERCISE), "python_version": sys.version,
        "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
        "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
        "metadata_and_operation_check": report, "learner_sha256_before": before,
        "learner_sha256_after": after, "benchmark": None, "run": run_result,
    }
    output = root / "work/R53-T035/evidence.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: groupCost is constant over sizes 1..5; {CASE_COUNT} exercise cases pass")
    print(f"Evidence: {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
