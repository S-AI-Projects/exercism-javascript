#!/usr/bin/env python3
"""Validate Forth test-runner success, failure, empty selection, and file safety."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "forth"
OUTPUT = Path(__file__).resolve().parent
RUNNER = ROOT / "tools" / "course_checks" / "r53-t019.py"
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
FAILING_REFERENCE = """\
export class Forth {
  constructor() {
    this.stack = [];
  }

  evaluate() {
    throw new Error('Deliberately failing reference');
  }
}
"""


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_version(command):
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not get version for {command[0]}.")
    return result.stdout.strip()


def hash_solution_files(solution_paths):
    hashes = {}
    for path in solution_paths:
        contents = (EXERCISE / path).read_bytes()
        hashes[path] = hashlib.sha256(contents).hexdigest()
    return hashes


def run_case(name, options, report_path, solution_paths, expected, expected_count):
    before_hashes = hash_solution_files(solution_paths)
    command = [
        sys.executable,
        str(RUNNER),
        "--report-file",
        str(report_path),
        *options,
    ]
    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return_code = process.returncode
        output = (process.stdout + process.stderr).strip()
    except OSError as error:
        return_code = None
        output = str(error)
    finally:
        after_hashes = hash_solution_files(solution_paths)

    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else None
    )
    unchanged = before_hashes == after_hashes
    actual_counts = report.get("counts") if report else None

    if not unchanged:
        passed = False
    elif expected == "pass":
        passed = (
            return_code == 0
            and report is not None
            and report["success"]
            and actual_counts is not None
            and actual_counts["total"] == expected_count
            and actual_counts["failed"] == 0
            and actual_counts["pending"] == 0
        )
    elif expected == "failed reference":
        passed = (
            return_code != 0
            and report is not None
            and not report["success"]
            and actual_counts is not None
            and actual_counts["total"] == expected_count
            and actual_counts["failed"] > 0
        )
    else:
        passed = (
            return_code != 0
            and report is not None
            and not report["success"]
            and actual_counts is not None
            and actual_counts["total"] == 0
            and any("No tests were executed." in reason for reason in report["failures"])
        )

    return {
        "name": name,
        "expected": expected,
        "return_code": return_code,
        "actual_counts": actual_counts,
        "runner_result": report,
        "output": output,
        "learner_sha256_before": before_hashes,
        "learner_sha256_after": after_hashes,
        "learner_unchanged": unchanged,
        "passed": passed,
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(
        (EXERCISE / ".meta" / "config.json").read_text(encoding="utf-8")
    )
    files = config["files"]
    solution_paths = files["solution"]
    test_paths = files["test"]
    reference_paths = files["example"]
    if not solution_paths or len(solution_paths) != len(reference_paths):
        raise ValueError("The solution and reference paths do not match.")
    if not test_paths:
        raise ValueError("The config does not list any test files.")
    test_sources = {
        path: (EXERCISE / path).read_text(encoding="utf-8") for path in test_paths
    }
    test_names = [
        match.group(2)
        for source in test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]

    versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", versions)

    cases = []
    cases.append(
        run_case(
            "real reference",
            [],
            OUTPUT / "reference-results.json",
            solution_paths,
            "pass",
            len(test_names),
        )
    )

    with tempfile.TemporaryDirectory(prefix="forth-bad-reference-") as temp_dir:
        failing_reference = Path(temp_dir) / "failing-reference.js"
        failing_reference.write_text(FAILING_REFERENCE, encoding="utf-8")
        cases.append(
            run_case(
                "deliberately failing reference",
                ["--reference-override", str(failing_reference)],
                OUTPUT / "failing-reference-results.json",
                solution_paths,
                "failed reference",
                len(test_names),
            )
        )

    cases.append(
        run_case(
            "empty test selection",
            ["--empty-selection"],
            OUTPUT / "empty-selection-results.json",
            solution_paths,
            "empty selection",
            0,
        )
    )

    test_inputs = {
        "config": config,
        "test_sources": test_sources,
        "test_names": test_names,
        "expected_enabled_test_count": len(test_names),
        "failing_reference_source": FAILING_REFERENCE,
        "empty_selection_method": (
            "The temporary copy's spec files are emptied and Jest is told to "
            "ignore all test paths."
        ),
    }
    failures = [case["name"] for case in cases if not case["passed"]]
    inputs = {
        "test_inputs": test_inputs,
        "expected_results": {
            "real reference": "all tests pass and at least one test executes",
            "deliberately failing reference": "non-zero result and failed assertions",
            "empty test selection": "non-zero result and zero executed tests",
            "learner solution": "same SHA256 before and after every run",
        },
    }
    results = {
        "success": not failures,
        "cases": cases,
        "failed_checks": failures,
        "final_learner_sha256": hash_solution_files(solution_paths),
    }
    save_json(OUTPUT / "inputs.json", inputs)
    save_json(OUTPUT / "results.json", results)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"Details saved in {OUTPUT}", file=sys.stderr)
        return 1

    real_counts = cases[0]["actual_counts"]
    print(
        f"PASS: reference passed {real_counts['total']} tests; the failing "
        "reference and empty selection were rejected; learner hashes stayed the same."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
