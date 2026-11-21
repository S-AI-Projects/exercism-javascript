#!/usr/bin/env python3
"""Check Luhn metadata validation and run all exercise tests on the reference."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "luhn"
OUTPUT = Path(__file__).resolve().parent
METADATA_CHECKER = ROOT / "tools" / "course_checks" / "r53-t018.py"
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_version(command):
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not get version for {command[0]}.")
    return result.stdout.strip()


def run_metadata_checker(exercise_dir):
    return subprocess.run(
        [
            sys.executable,
            str(METADATA_CHECKER),
            "--exercise-dir",
            str(exercise_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def create_fixture(exercise_dir, files):
    meta_dir = exercise_dir / ".meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "config.json").write_text(
        json.dumps({"files": files}, indent=2) + "\n",
        encoding="utf-8",
    )


def check_invalid_fixtures(temp_root):
    results = []

    missing_reference = temp_root / "missing-reference"
    missing_reference.mkdir()
    create_fixture(
        missing_reference,
        {
            "solution": ["luhn.js"],
            "test": ["luhn.spec.js"],
            "example": [".meta/proof.ci.js"],
        },
    )
    (missing_reference / "luhn.js").write_text("", encoding="utf-8")
    (missing_reference / "luhn.spec.js").write_text("", encoding="utf-8")
    result = run_metadata_checker(missing_reference)
    results.append(
        {
            "name": "missing reference file",
            "expected_failure_reason": "Declared example file does not exist",
            "return_code": result.returncode,
            "output": (result.stdout + result.stderr).strip(),
            "passed": (
                result.returncode != 0
                and "Declared example file does not exist" in result.stderr
            ),
        }
    )

    missing_test = temp_root / "missing-test"
    missing_test.mkdir()
    create_fixture(
        missing_test,
        {
            "solution": ["luhn.js"],
            "test": ["missing.spec.js"],
            "example": [".meta/proof.ci.js"],
        },
    )
    (missing_test / "luhn.js").write_text("", encoding="utf-8")
    (missing_test / ".meta" / "proof.ci.js").write_text("", encoding="utf-8")
    result = run_metadata_checker(missing_test)
    results.append(
        {
            "name": "missing test file",
            "expected_failure_reason": "Declared test file does not exist",
            "return_code": result.returncode,
            "output": (result.stdout + result.stderr).strip(),
            "passed": (
                result.returncode != 0
                and "Declared test file does not exist" in result.stderr
            ),
        }
    )

    outside_exercise = temp_root / "outside-exercise"
    outside_exercise.mkdir()
    (temp_root / "outside.spec.js").write_text("", encoding="utf-8")
    create_fixture(
        outside_exercise,
        {
            "solution": ["luhn.js"],
            "test": ["../outside.spec.js"],
            "example": [".meta/proof.ci.js"],
        },
    )
    (outside_exercise / "luhn.js").write_text("", encoding="utf-8")
    (outside_exercise / ".meta" / "proof.ci.js").write_text("", encoding="utf-8")
    result = run_metadata_checker(outside_exercise)
    results.append(
        {
            "name": "path outside exercise directory",
            "expected_failure_reason": "escapes the exercise directory",
            "return_code": result.returncode,
            "output": (result.stdout + result.stderr).strip(),
            "passed": (
                result.returncode != 0
                and "escapes the exercise directory" in result.stderr
            ),
        }
    )

    return results


def run_exercise_tests(expected_count, test_paths, solution_paths, example_paths):
    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    original_tests = {
        path: (EXERCISE / path).read_bytes() for path in test_paths
    }
    failures = []
    enabled_skips = 0
    run = None

    with tempfile.TemporaryDirectory(prefix="luhn-reference-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_exercise = temp_root / "luhn"
        shutil.copytree(
            EXERCISE,
            temp_exercise,
            ignore=shutil.ignore_patterns("node_modules"),
        )

        dependencies = ROOT / "node_modules"
        if dependencies.is_dir():
            (temp_exercise / "node_modules").symlink_to(
                dependencies, target_is_directory=True
            )
        else:
            failures.append("Repository node_modules are missing.")

        for solution_path, example_path in zip(solution_paths, example_paths):
            shutil.copyfile(
                temp_exercise / example_path,
                temp_exercise / solution_path,
            )

        for test_path in test_paths:
            copied_test = temp_exercise / test_path
            source = copied_test.read_text(encoding="utf-8")
            enabled, replacements = SKIPPED_CALL.subn("test", source)
            enabled_skips += replacements
            copied_test.write_text(enabled, encoding="utf-8")

        package = json.loads(
            (temp_exercise / "package.json").read_text(encoding="utf-8")
        )
        if "test" not in package.get("scripts", {}):
            failures.append("The exercise package.json has no test command.")

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
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        report = (
            json.loads(report_path.read_text(encoding="utf-8"))
            if report_path.is_file()
            else None
        )

    counts = None
    cases = []
    if report is not None:
        counts = {
            "total": report.get("numTotalTests"),
            "passed": report.get("numPassedTests"),
            "failed": report.get("numFailedTests"),
            "pending": report.get("numPendingTests"),
        }
        for test_file in report.get("testResults", []):
            for assertion in test_file.get("assertionResults", []):
                cases.append(
                    {
                        "name": assertion.get("fullName"),
                        "expected_status": "passed",
                        "actual_status": assertion.get("status"),
                        "failure_messages": assertion.get("failureMessages", []),
                    }
                )

    run = {
        "command": command,
        "return_code": process.returncode,
        "counts": counts,
        "cases": cases,
        "output_excerpt": (process.stdout + process.stderr)[-1500:],
    }

    if process.returncode != 0:
        failures.append("The exercise test command exited unsuccessfully.")
    if counts is None:
        failures.append("The test run did not produce Jest results.")
    elif counts["total"] == 0:
        failures.append("The test run executed zero tests.")
    elif counts["total"] != expected_count:
        failures.append(
            f"The test run executed {counts['total']} tests; expected {expected_count}."
        )
    elif counts["failed"] != 0 or counts["passed"] != expected_count:
        failures.append("Not all exercise tests passed.")
    if len(cases) != expected_count:
        failures.append("The test run did not report every test assertion.")
    for case in cases:
        if case["actual_status"] != case["expected_status"]:
            failures.append(
                f"Test assertion failed: {case['name']} ({case['actual_status']})."
            )

    learner_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_solutions.items()
    )
    tests_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_tests.items()
    )
    if not learner_unchanged:
        failures.append("The original learner solution changed.")
    if not tests_unchanged:
        failures.append("The original exercise tests changed.")

    return run, enabled_skips, learner_unchanged, tests_unchanged, failures


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config_path = EXERCISE / ".meta" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    files = config["files"]
    solution_paths = files["solution"]
    test_paths = files["test"]
    example_paths = files["example"]
    if not solution_paths or len(solution_paths) != len(example_paths):
        raise ValueError("The solution and example paths do not match.")
    if not test_paths:
        raise ValueError("The exercise config does not list test files.")

    test_sources = {
        path: (EXERCISE / path).read_text(encoding="utf-8") for path in test_paths
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
    versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", versions)

    failures = []
    real_metadata = run_metadata_checker(EXERCISE)
    real_metadata_result = {
        "expected": "pass",
        "return_code": real_metadata.returncode,
        "output": (real_metadata.stdout + real_metadata.stderr).strip(),
        "passed": real_metadata.returncode == 0,
    }
    if not real_metadata_result["passed"]:
        failures.append("The real Luhn metadata did not pass validation.")

    with tempfile.TemporaryDirectory(prefix="luhn-metadata-fixtures-") as temp_dir:
        fixture_results = check_invalid_fixtures(Path(temp_dir))
    for fixture in fixture_results:
        if not fixture["passed"]:
            failures.append(
                f"Metadata checker fixture did not fail as expected: {fixture['name']}."
            )

    (
        exercise_run,
        skipped_enabled,
        learner_unchanged,
        tests_unchanged,
        exercise_failures,
    ) = run_exercise_tests(
        expected_count, test_paths, solution_paths, example_paths
    )
    failures.extend(exercise_failures)
    if skipped_enabled != expected_skips:
        failures.append("Not all skipped tests were enabled in the temporary copy.")

    required_cases = [
        "single digit strings can not be valid",
        "a single zero is invalid",
        "a simple valid SIN that remains valid if reversed",
    ]
    for required in required_cases:
        if not any(
            required in case["name"] and case["actual_status"] == "passed"
            for case in exercise_run["cases"]
        ):
            failures.append(f"Required Luhn test did not pass: {required}.")

    inputs = {
        "config": config,
        "test_sources": test_sources,
        "expected_test_names": expected_names,
        "expected_test_count": expected_count,
        "expected_skipped_tests_enabled": expected_skips,
        "metadata_fixtures": [
            "missing reference file",
            "missing test file",
            "path outside exercise directory",
        ],
    }
    results = {
        "success": not failures,
        "real_metadata_validation": real_metadata_result,
        "invalid_metadata_fixtures": fixture_results,
        "enabled_skipped_tests": skipped_enabled,
        "exercise_run": exercise_run,
        "learner_solution_unchanged": learner_unchanged,
        "tests_unchanged": tests_unchanged,
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
        f"PASS: real metadata passed; all 3 invalid metadata fixtures were "
        f"rejected; all {expected_count} Luhn tests passed."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
