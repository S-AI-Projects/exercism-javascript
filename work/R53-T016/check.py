#!/usr/bin/env python3
"""Run the Space Age tests against the reference and switch alternatives."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "space-age"
OUTPUT = Path(__file__).resolve().parent
ALTERNATIVE = OUTPUT / "alternative.js"
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


def run_tests(exercise, report_path):
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
    result = subprocess.run(
        command,
        cwd=exercise,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
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

    return {
        "command": command,
        "return_code": result.returncode,
        "counts": counts,
        "cases": cases,
        "output_excerpt": (result.stdout + result.stderr)[-1000:],
    }


def prepare_and_test(approach, implementation_path, test_paths, expected_count):
    failures = []
    enabled_skips = 0

    with tempfile.TemporaryDirectory(prefix=f"space-age-{approach}-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_exercise = temp_root / "space-age"
        shutil.copytree(
            EXERCISE,
            temp_exercise,
            ignore=shutil.ignore_patterns("node_modules"),
        )

        dependencies = ROOT / "node_modules"
        if not dependencies.is_dir():
            return None, 0, ["Repository node_modules are missing."]
        (temp_exercise / "node_modules").symlink_to(
            dependencies, target_is_directory=True
        )

        config = json.loads(
            (EXERCISE / ".meta" / "config.json").read_text(encoding="utf-8")
        )
        for solution_path in config["files"]["solution"]:
            shutil.copyfile(implementation_path, temp_exercise / solution_path)

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

        run = run_tests(temp_exercise, temp_root / f"{approach}-jest-results.json")

    if run["return_code"] != 0:
        failures.append(f"The {approach} test command exited unsuccessfully.")
    counts = run["counts"]
    if counts is None:
        failures.append(f"The {approach} run did not produce Jest results.")
    elif counts["total"] == 0:
        failures.append(f"The {approach} run executed zero tests.")
    elif counts["total"] != expected_count:
        failures.append(
            f"The {approach} run executed {counts['total']} tests; "
            f"expected {expected_count}."
        )
    elif counts["failed"] != 0 or counts["passed"] != expected_count:
        failures.append(f"Not all {approach} tests passed.")

    if len(run["cases"]) != expected_count:
        failures.append(f"The {approach} run did not report every test assertion.")
    for case in run["cases"]:
        if case["actual_status"] != case["expected_status"]:
            failures.append(
                f"{approach} assertion failed: {case['name']} "
                f"({case['actual_status']})."
            )

    return run, enabled_skips, failures


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(
        (EXERCISE / ".meta" / "config.json").read_text(encoding="utf-8")
    )
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
    test_names = [
        match.group(2)
        for source in test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    expected_count = len(test_names)
    expected_skips = sum(
        len(SKIPPED_CALL.findall(source)) for source in test_sources.values()
    )

    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    original_tests = {
        path: (EXERCISE / path).read_bytes() for path in test_paths
    }
    implementations = {
        "reference": EXERCISE / example_paths[0],
        "alternative": ALTERNATIVE,
    }
    for name, path in implementations.items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing {name} implementation: {path}")

    versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", versions)

    runs = {}
    failures = []
    enabled_skips = {}
    for approach, implementation_path in implementations.items():
        run, skipped, approach_failures = prepare_and_test(
            approach, implementation_path, test_paths, expected_count
        )
        runs[approach] = run
        enabled_skips[approach] = skipped
        failures.extend(approach_failures)
        if skipped != expected_skips:
            failures.append(f"Not all skipped tests were enabled for {approach}.")

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

    inputs = {
        "config": config,
        "test_sources": test_sources,
        "expected_test_names": test_names,
        "expected_test_count": expected_count,
        "expected_skipped_tests_enabled_per_copy": expected_skips,
        "approaches": {
            "reference": str(implementations["reference"].relative_to(ROOT)),
            "alternative": str(ALTERNATIVE.relative_to(ROOT)),
        },
    }
    results = {
        "success": not failures,
        "expected_test_count": expected_count,
        "enabled_skipped_tests": enabled_skips,
        "runs": runs,
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
        f"PASS: reference and switch alternative each passed all "
        f"{expected_count} exercise tests."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
