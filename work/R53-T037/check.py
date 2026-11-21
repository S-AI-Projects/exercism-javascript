#!/usr/bin/env python3
"""Check the Unicode micro-example and execute Micro-blog reference cases."""

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


EXERCISE = Path("exercises/practice/micro-blog")


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
    if len(canonical) != 12 or len(titles) != 12:
        fail(f"expected 12 canonical cases and tests, found {len(canonical)} and {len(titles)}")
    for required in ("English language short", "English language long", "German language short (broth)"):
        if required not in titles:
            fail(f"missing required case {required!r}")
    reference = example.read_text()
    if "Intl.Segmenter" not in reference or "String(input)" not in reference:
        fail("reference no longer uses the documented Segmenter and string coercion")
    return {
        "config_file_map": {
            key: str(path.relative_to(exercise.resolve()))
            for key, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_count": len(canonical), "spec_case_count": len(titles), "case_names": titles,
    }


def run_example(root: Path) -> dict[str, object]:
    example = root / "work/R53-T037/micro-example.mjs"
    result = subprocess.run(["node", str(example)], cwd=root, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        fail("Unicode micro-example assertions failed\n" + result.stdout)
    try:
        actual = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail("micro-example did not emit its result JSON")
    expected = {"input": "e\u0301bcdef", "byGrapheme": "e\u0301bcde", "byCodePoint": "e\u0301bcd"}
    if actual != expected:
        fail(f"unexpected micro-example outputs: {actual!r}")
    return {"command": ["node", str(example)], "returncode": result.returncode, "actual": actual, "expected": expected}


def run_tests(root: Path, source: Path, target: Path) -> dict[str, object]:
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
    metadata = inspect(exercise)
    learner = declared(exercise, "solution")
    before = sha(learner)
    example = run_example(root)
    with tempfile.TemporaryDirectory(prefix="R53-T037-") as tmp:
        tests = run_tests(root, exercise, Path(tmp) / "exercise")
    after = sha(learner)
    if before != after:
        fail("learner stub changed during the check")
    count = metadata["spec_case_count"]
    if tests["returncode"] != 0 or tests["counts"] != {"passed": count, "failed": 0, "total": count}:
        fail("reference tests failed or test count was unexpected\n" + str(tests["output"])[-2500:])
    evidence = {
        "exercise": str(EXERCISE), "python_version": sys.version,
        "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
        "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
        "metadata": metadata, "micro_example": example, "learner_sha256_before": before,
        "learner_sha256_after": after, "reference_run": tests,
    }
    output = root / "work/R53-T037/evidence.json"
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(f"PASS: both Unicode outputs asserted; {count} reference cases pass")
    print(f"Evidence: {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
