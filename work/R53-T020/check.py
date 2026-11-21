#!/usr/bin/env python3
"""Run Accumulate's reference tests and verify the learner file is unchanged."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "accumulate"
OUTPUT = Path(__file__).resolve().parent
RUNNER = ROOT / "tools" / "course_checks" / "r53-t020.py"
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
REQUIRED_CASES = [
    "accumulation empty",
    "accumulate squares",
    "accumulate upcases",
]


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
    return {
        path: hashlib.sha256((EXERCISE / path).read_bytes()).hexdigest()
        for path in solution_paths
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
    expected_count = len(test_names)
    tool_versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", tool_versions)

    before_hashes = hash_solution_files(solution_paths)
    report_path = OUTPUT / "reference-results.json"
    command = [
        sys.executable,
        str(RUNNER),
        "--report-file",
        str(report_path),
    ]
    process_error = None
    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        process = None
        process_error = str(error)
    finally:
        after_hashes = hash_solution_files(solution_paths)

    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else None
    )
    failures = []
    if process is None:
        failures.append(f"Could not run the course checker: {process_error}")
        return_code = None
        output = process_error
    else:
        return_code = process.returncode
        output = (process.stdout + process.stderr).strip()
        if process.returncode != 0:
            failures.append(f"The course checker exited with {process.returncode}.")

    if report is None:
        failures.append("The course checker did not save its result report.")
        counts = None
        cases = []
    else:
        counts = report["counts"]
        cases = report["cases"]
        if not report["success"]:
            failures.append("The reference test run reported a failure.")
        if counts["total"] == 0:
            failures.append("The course checker executed zero tests.")
        elif counts["total"] != expected_count:
            failures.append(
                f"Executed {counts['total']} tests; expected {expected_count}."
            )
        if counts["failed"] != 0 or counts["pending"] != 0:
            failures.append("Some tests failed or remained skipped.")
        if len(cases) != expected_count:
            failures.append("The report does not include every test case.")

    for required in REQUIRED_CASES:
        if not any(
            required in case["name"] and case["status"] == "passed"
            for case in cases
        ):
            failures.append(f"Required contract case did not pass: {required}.")
    for case in cases:
        if case["status"] != "passed":
            failures.append(f"Test assertion failed: {case['name']} ({case['status']}).")

    learner_unchanged = before_hashes == after_hashes
    if not learner_unchanged:
        failures.append("Learner solution SHA256 hashes changed during testing.")

    inputs = {
        "config": config,
        "test_sources": test_sources,
        "expected_test_names": test_names,
        "expected_test_count": expected_count,
        "required_contract_cases": REQUIRED_CASES,
        "learner_sha256_before": before_hashes,
    }
    results = {
        "success": not failures,
        "command": command,
        "return_code": return_code,
        "expected_test_count": expected_count,
        "actual_counts": counts,
        "expected_case_status": "passed",
        "actual_cases": cases,
        "runner_report": report,
        "output": output,
        "learner_sha256_before": before_hashes,
        "learner_sha256_after": after_hashes,
        "learner_unchanged": learner_unchanged,
        "failure_reasons": failures,
    }
    save_json(OUTPUT / "inputs.json", inputs)
    save_json(OUTPUT / "results.json", results)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"Details saved in {OUTPUT}", file=sys.stderr)
        return 1

    print(
        f"PASS: reference passed {counts['total']} tests; "
        "all required contract cases passed and learner SHA256 hashes matched."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
