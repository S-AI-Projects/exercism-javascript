#!/usr/bin/env python3
"""Run the Accumulate tests against the reference in a temporary copy."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "accumulate"
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")


def save_report(report_path, report):
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def run_tests(arguments):
    exercise = arguments.exercise_dir.resolve()
    config = json.loads(
        (exercise / ".meta" / "config.json").read_text(encoding="utf-8")
    )
    files = config["files"]
    solution_paths = files["solution"]
    test_paths = files["test"]
    reference_paths = files["example"]
    if not solution_paths or len(solution_paths) != len(reference_paths):
        raise ValueError("The solution and reference paths do not match.")
    if not test_paths:
        raise ValueError("The config does not list any test files.")

    package = json.loads((exercise / "package.json").read_text(encoding="utf-8"))
    if "test" not in package.get("scripts", {}):
        raise ValueError("The exercise package.json has no test script.")

    test_sources = {
        path: (exercise / path).read_text(encoding="utf-8") for path in test_paths
    }
    test_names = [
        match.group(2)
        for source in test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    expected_count = len(test_names)
    expected_skips = sum(
        len(SKIPPED_CALL.findall(source)) for source in test_sources.values()
    )
    failures = []
    counts = None
    cases = []
    test_output = ""
    command = []

    with tempfile.TemporaryDirectory(prefix="accumulate-course-check-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_exercise = temp_root / "accumulate"
        shutil.copytree(
            exercise,
            temp_exercise,
            ignore=shutil.ignore_patterns("node_modules"),
        )

        dependencies = ROOT / "node_modules"
        if not dependencies.is_dir():
            raise FileNotFoundError("Repository node_modules are missing.")
        (temp_exercise / "node_modules").symlink_to(
            dependencies, target_is_directory=True
        )

        for solution_path, reference_path in zip(solution_paths, reference_paths):
            shutil.copyfile(
                temp_exercise / reference_path,
                temp_exercise / solution_path,
            )

        enabled_skips = 0
        for test_path in test_paths:
            copied_test = temp_exercise / test_path
            source = copied_test.read_text(encoding="utf-8")
            enabled, replacements = SKIPPED_CALL.subn("test", source)
            enabled_skips += replacements
            copied_test.write_text(enabled, encoding="utf-8")
        if enabled_skips != expected_skips:
            failures.append("Not all skipped tests were enabled in the temporary copy.")

        report_path = temp_root / "jest-results.json"
        command = [
            "npm",
            "run",
            "test",
            "--",
            "--watch=false",
            "--runInBand",
            "--json",
            f"--outputFile={report_path}",
        ]
        process = subprocess.run(
            command,
            cwd=temp_exercise,
            capture_output=True,
            text=True,
            check=False,
        )
        test_output = (process.stdout + process.stderr)[-2000:]

        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            counts = {
                "total": report.get("numTotalTests", 0),
                "passed": report.get("numPassedTests", 0),
                "failed": report.get("numFailedTests", 0),
                "pending": report.get("numPendingTests", 0),
            }
            for test_file in report.get("testResults", []):
                for assertion in test_file.get("assertionResults", []):
                    cases.append(
                        {
                            "name": assertion.get("fullName"),
                            "status": assertion.get("status"),
                            "failure_messages": assertion.get("failureMessages", []),
                        }
                    )

    if process.returncode != 0:
        failures.append(f"The test process exited with status {process.returncode}.")
    if counts is None or counts["total"] == 0:
        failures.append("No tests were executed.")
    elif counts["total"] != expected_count:
        failures.append(
            f"Executed {counts['total']} tests; expected {expected_count}."
        )
    elif counts["failed"] > 0 or counts["pending"] > 0:
        failures.append("One or more tests failed or remained skipped.")
    if len(cases) != expected_count:
        failures.append("The test run did not report every test case.")
    for case in cases:
        if case["status"] != "passed":
            failures.append(f"Test assertion failed: {case['name']} ({case['status']}).")

    result = {
        "success": not failures,
        "command": command,
        "return_code": process.returncode,
        "counts": counts,
        "expected_test_count": expected_count,
        "enabled_skipped_tests": enabled_skips,
        "test_names": test_names,
        "cases": cases,
        "failures": failures,
        "output_excerpt": test_output,
    }
    save_report(arguments.report_file, result)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        if counts is not None:
            print(f"Executed {counts['total']} tests.", file=sys.stderr)
        return 1

    print(
        f"PASS: executed {counts['total']} tests; "
        f"{counts['passed']} passed and none failed."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exercise-dir",
        type=Path,
        default=EXERCISE,
        help="Exercise directory to copy (defaults to Accumulate).",
    )
    parser.add_argument("--report-file", type=Path, help="Optional JSON result path.")
    arguments = parser.parse_args()

    try:
        return run_tests(arguments)
    except KeyboardInterrupt:
        print("Interrupted; the temporary exercise copy was cleaned up.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
