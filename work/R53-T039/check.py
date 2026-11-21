#!/usr/bin/env python3
"""Safely exercise the Satellite reference runner in isolated copies."""

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


EXERCISE = Path("exercises/practice/satellite")
NAMED_CASES = ("Empty tree", "Tree with one item", "Tree with many items")


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
    titles = [title for _quote, title in re.findall(r"\b(?:x?test)\(([\"'])(.*?)\1", spec.read_text())]
    if len(canonical) != 9 or len(titles) != 9:
        fail(f"expected 9 canonical cases and test cases, found {len(canonical)} and {len(titles)}")
    if any(name not in titles for name in NAMED_CASES):
        fail("one of the named satellite cases is missing")
    return {
        "config_file_map": {
            role: str(path.relative_to(exercise.resolve()))
            for role, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_count": len(canonical), "spec_case_count": len(titles), "case_names": titles,
    }


def run_mode(root: Path, source: Path, dest: Path, mode: str, reference: Path) -> dict[str, object]:
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("node_modules"))
    solution, spec = declared(dest, "solution"), declared(dest, "test")
    spec_text = spec.read_text()
    if mode == "empty":
        spec_text = re.sub(r"\btest\(", "xtest(", spec_text)
    else:
        spec_text = spec_text.replace("xtest(", "test(")
    spec.write_text(spec_text)
    shutil.copyfile(reference, solution)

    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    report = dest / "satellite-jest-results.json"
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--", "--watchAll=false", "--runInBand",
               "--json", f"--outputFile={report}"]
    child = subprocess.run(command, cwd=dest, env=env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, check=False)
    if not report.is_file():
        fail(f"Jest did not write its JSON report in {mode} mode\n" + child.stdout[-2000:])
    jest = json.loads(report.read_text())
    counts = {
        "total": int(jest.get("numTotalTests", 0)),
        "passed": int(jest.get("numPassedTests", 0)),
        "failed": int(jest.get("numFailedTests", 0)),
        "pending": int(jest.get("numPendingTests", 0)),
    }
    executed = counts["passed"] + counts["failed"]
    accepted = child.returncode == 0 and executed > 0 and counts["failed"] == 0
    return {
        "mode": mode, "command": command, "returncode": child.returncode,
        "counts": counts, "executed": executed, "accepted_as_success": accepted,
        "output": child.stdout,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    root = parser.parse_args().root.resolve()
    exercise = root / EXERCISE
    metadata = inspect(exercise)
    learner = declared(exercise, "solution")
    reference = declared(exercise, "example")
    suite_results: dict[str, object] = {}

    with tempfile.TemporaryDirectory(prefix="R53-T039-") as tmp:
        tmp_path = Path(tmp)
        for mode in ("reference", "failing", "empty"):
            before = sha(learner)
            if mode == "reference":
                mode_reference = reference
                copy = tmp_path / "reference"
            elif mode == "failing":
                mode_reference = tmp_path / "failing-proof.ci.js"
                mode_reference.write_text("export const treeFromTraversals = () => { throw new Error('deliberate failure'); };\n")
                copy = tmp_path / "failing"
            else:
                mode_reference = reference
                copy = tmp_path / "empty"
            result = run_mode(root, exercise, copy, "empty" if mode == "empty" else "all", mode_reference)
            after = sha(learner)
            result["learner_sha256_before"] = before
            result["learner_sha256_after"] = after
            result["learner_unchanged"] = before == after
            if before != after:
                fail(f"learner solution changed during {mode} mode")
            suite_results[mode] = result
            if mode == "reference":
                count = metadata["spec_case_count"]
                if not result["accepted_as_success"] or result["counts"] != {"total": count, "passed": count, "failed": 0, "pending": 0}:
                    fail("real reference did not pass every case\n" + str(result["output"])[-2000:])
            elif mode == "failing":
                if result["returncode"] == 0 or result["counts"]["failed"] == 0 or result["accepted_as_success"]:
                    fail("deliberately failing reference was not rejected\n" + str(result["output"])[-2000:])
            else:
                if result["executed"] != 0 or result["accepted_as_success"]:
                    fail("empty test selection was incorrectly accepted")

    for result in suite_results.values():
        result["temporary_directory_removed"] = not tmp_path.exists()
    if not all(item["learner_unchanged"] and item["temporary_directory_removed"] for item in suite_results.values()):
        fail("learner preservation or temporary cleanup check failed")
    evidence = {
        "exercise": str(EXERCISE), "python_version": sys.version,
        "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
        "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
        "metadata": metadata, "modes": suite_results,
    }
    output = root / "work/R53-T039/evidence.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print("PASS: real reference passes; failing and empty selections are rejected; learner file hashes are unchanged")
    for mode, item in suite_results.items():
        print(f"{mode}: executed={item['executed']} returncode={item['returncode']}")
    print(f"Evidence: {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
