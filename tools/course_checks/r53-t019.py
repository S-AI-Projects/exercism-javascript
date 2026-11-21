#!/usr/bin/env python3
"""Run the Forth exercise tests against its reference implementation safely."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "forth"
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")


def save_report(report_path, report):
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def run_checker(arguments):
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
    expected_names = [
        match.group(2)
        for source in test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    expected_count = len(expected_names)
    expected_skips = sum(
        len(SKIPPED_CALL.findall(source)) for source in test_sources.values()
    )

    failures = []
    child = None
    counts = None
    cases = []
    test_output = ""
    command = []

    with tempfile.TemporaryDirectory(prefix="forth-course-check-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_exercise = temp_root / "forth"
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

        reference_source = arguments.reference_override
        if reference_source is None:
            reference_source = temp_exercise / reference_paths[0]
        elif not reference_source.is_file():
            raise FileNotFoundError(
                f"Reference override does not exist: {reference_source}"
            )

        for solution_path in solution_paths:
            shutil.copyfile(reference_source, temp_exercise / solution_path)

        enabled_skips = 0
        for test_path in test_paths:
            copied_test = temp_exercise / test_path
            source = copied_test.read_text(encoding="utf-8")
            enabled, replacements = SKIPPED_CALL.subn("test", source)
            enabled_skips += replacements
            copied_test.write_text(enabled, encoding="utf-8")
        if enabled_skips != expected_skips:
            failures.append("Not all skipped tests were enabled in the temporary copy.")

        if arguments.empty_selection:
            for test_path in test_paths:
                (temp_exercise / test_path).write_text("", encoding="utf-8")

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
        if arguments.empty_selection:
            command.append("--testPathIgnorePatterns=.+")

        child = subprocess.run(
            command,
            cwd=temp_exercise,
            capture_output=True,
            text=True,
            check=False,
        )
        test_output = (child.stdout + child.stderr)[-2000:]

        report = None
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        if report is not None:
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
        elif arguments.empty_selection:
            counts = {"total": 0, "passed": 0, "failed": 0, "pending": 0}
        else:
            failures.append("The test command did not produce a Jest results file.")

    if child.returncode != 0:
        failures.append(f"The test process exited with status {child.returncode}.")
    if counts is None or counts["total"] == 0:
        failures.append("No tests were executed.")
    elif counts["total"] != expected_count:
        failures.append(
            f"Executed {counts['total']} tests; expected {expected_count}."
        )
    elif counts["failed"] > 0 or any(case["status"] != "passed" for case in cases):
        failures.append("One or more test assertions failed.")
    if counts is not None and counts["pending"] > 0:
        failures.append("Some tests were still skipped.")

    result = {
        "success": not failures,
        "command": command,
        "return_code": child.returncode,
        "counts": counts,
        "expected_test_count": expected_count,
        "enabled_skipped_tests": enabled_skips,
        "cases": cases,
        "failures": failures,
        "output_excerpt": test_output,
    }
    save_report(arguments.report_file, result)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        if counts is not None:
            print(
                f"Executed {counts['total']} tests: {counts['passed']} passed, "
                f"{counts['failed']} failed, {counts['pending']} pending.",
                file=sys.stderr,
            )
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
        help="Exercise folder to copy (defaults to the Forth exercise).",
    )
    parser.add_argument(
        "--reference-override",
        type=Path,
        help="Optional alternate reference file, used to test failure handling.",
    )
    parser.add_argument(
        "--empty-selection",
        action="store_true",
        help="Run with all copied test files ignored to verify zero-test handling.",
    )
    parser.add_argument("--report-file", type=Path, help="Optional JSON result path.")
    arguments = parser.parse_args()

    try:
        return run_checker(arguments)
    except KeyboardInterrupt:
        print("Interrupted; the temporary exercise copy was cleaned up.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
