#!/usr/bin/env python3
"""Run zebra-puzzle tests against the reference in a temporary copy."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "zebra-puzzle"
PREPARATION_CHECK = ROOT / "tools" / "course_checks" / "r53-t012.py"
OUTPUT_DIR = Path(__file__).resolve().parent
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1", re.DOTALL)
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")
EXPECTED_CASES = {
    "16efb4e4-8ad7-4d5e-ba96-e5537b66fd42": {
        "description": "resident who drinks water",
        "test_name": "resident who drinks water",
        "method": "waterDrinker",
        "expected": "Norwegian",
    },
    "084d5b8b-24e2-40e6-b008-c800da8cd257": {
        "description": "resident who owns zebra",
        "test_name": "resident who owns zebra",
        "method": "zebraOwner",
        "expected": "Japanese",
    },
}


def sha256(contents):
    return hashlib.sha256(contents).hexdigest()


def run_version(command):
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not get version for {command[0]}.")
    return result.stdout.strip()


def inclusion_counts(path):
    with path.open("rb") as tests_file:
        cases = tomllib.load(tests_file)
    entries = [case for case in cases.values() if isinstance(case, dict)]
    included = sum(case.get("include", True) is not False for case in entries)
    return {
        "total": len(entries),
        "included": included,
        "excluded": len(entries) - included,
    }


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = json.loads(
        (EXERCISE / ".meta" / "config.json").read_text(encoding="utf-8")
    )
    files = config["files"]
    solution_paths = files["solution"]
    test_paths = files["test"]
    example_paths = files["example"]
    if not solution_paths or len(solution_paths) != len(example_paths):
        raise ValueError("The solution and example file paths do not match.")
    if not test_paths:
        raise ValueError("The exercise config does not list test files.")

    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    original_tests = {
        path: (EXERCISE / path).read_bytes() for path in test_paths
    }
    original_solution_hashes = {
        path: sha256(contents) for path, contents in original_solutions.items()
    }
    original_test_hashes = {
        path: sha256(contents) for path, contents in original_tests.items()
    }
    original_test_sources = {
        path: contents.decode("utf-8") for path, contents in original_tests.items()
    }
    expected_test_names = [
        match.group(2)
        for source in original_test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    skipped_test_count = sum(
        len(SKIPPED_CALL.findall(source)) for source in original_test_sources.values()
    )
    canonical_counts = inclusion_counts(EXERCISE / ".meta" / "tests.toml")

    tool_versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT_DIR / "tool-versions.json", tool_versions)

    preparation = subprocess.run(
        [sys.executable, str(PREPARATION_CHECK)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    preparation_report_path = OUTPUT_DIR / "preparation-results.json"
    preparation_report = (
        json.loads(preparation_report_path.read_text(encoding="utf-8"))
        if preparation_report_path.is_file()
        else None
    )

    inputs = {
        "config": config,
        "solution_paths": solution_paths,
        "test_paths": test_paths,
        "example_paths": example_paths,
        "original_test_sources": original_test_sources,
        "canonical_cases": EXPECTED_CASES,
        "included_excluded_counts": canonical_counts,
        "expected_test_names": expected_test_names,
        "skipped_tests_to_enable": skipped_test_count,
        "original_solution_sha256": original_solution_hashes,
        "original_test_sha256": original_test_hashes,
    }

    failures = []
    if preparation.returncode != 0:
        failures.append("The preparation reproducibility check failed.")
    if preparation_report is None:
        failures.append("The preparation check did not save its results.")
    elif not preparation_report.get("success"):
        failures.append("The preparation report did not pass.")

    actual_counts = None
    actual_tests = []
    return_code = None
    stdout = ""
    stderr = ""
    command = None

    with tempfile.TemporaryDirectory(prefix="zebra-reference-") as temp_dir:
        temp_exercise = Path(temp_dir) / "zebra-puzzle"
        shutil.copytree(
            EXERCISE,
            temp_exercise,
            ignore=shutil.ignore_patterns("node_modules"),
        )

        reference_paths = [temp_exercise / path for path in example_paths]
        for solution_path, reference_path in zip(solution_paths, reference_paths):
            shutil.copyfile(reference_path, temp_exercise / solution_path)

        changed_skips = 0
        for test_path in test_paths:
            copied_test = temp_exercise / test_path
            source = copied_test.read_text(encoding="utf-8")
            enabled_source, replacements = SKIPPED_CALL.subn("test", source)
            changed_skips += replacements
            copied_test.write_text(enabled_source, encoding="utf-8")

        if changed_skips != skipped_test_count:
            failures.append("Not all skipped tests were enabled in the temporary copy.")

        dependency_dir = ROOT / "node_modules"
        if dependency_dir.is_dir():
            (temp_exercise / "node_modules").symlink_to(
                dependency_dir, target_is_directory=True
            )
        else:
            failures.append("Repository node_modules are missing; install dependencies.")

        package = json.loads(
            (temp_exercise / "package.json").read_text(encoding="utf-8")
        )
        if "test" not in package.get("scripts", {}):
            failures.append("The exercise package.json has no test script.")

        report_path = Path(temp_dir) / "jest-results.json"
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
        completed = subprocess.run(
            command,
            cwd=temp_exercise,
            capture_output=True,
            text=True,
            check=False,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr

        test_result = None
        if report_path.is_file():
            test_result = json.loads(report_path.read_text(encoding="utf-8"))
            actual_counts = {
                "total": test_result.get("numTotalTests"),
                "passed": test_result.get("numPassedTests"),
                "failed": test_result.get("numFailedTests"),
                "pending": test_result.get("numPendingTests"),
            }
            for test_file in test_result.get("testResults", []):
                for assertion in test_file.get("assertionResults", []):
                    actual_tests.append(
                        {
                            "name": assertion.get("fullName"),
                            "status": assertion.get("status"),
                            "failure_messages": assertion.get("failureMessages", []),
                        }
                    )
        else:
            failures.append("Jest did not create its JSON results file.")

    if return_code != 0:
        failures.append(f"The package test script exited with status {return_code}.")
    if actual_counts is not None:
        if actual_counts["total"] == 0:
            failures.append("Jest ran zero tests.")
        if actual_counts["total"] != len(expected_test_names):
            failures.append(
                f"Expected {len(expected_test_names)} tests, but Jest ran "
                f"{actual_counts['total']}."
            )
        if actual_counts["failed"] != 0:
            failures.append(f"Jest reported {actual_counts['failed']} failed tests.")
        if actual_counts["passed"] != actual_counts["total"]:
            failures.append("Not every executed test passed.")

    solution_hashes_after = {
        path: sha256((EXERCISE / path).read_bytes()) for path in solution_paths
    }
    test_hashes_after = {
        path: sha256((EXERCISE / path).read_bytes()) for path in test_paths
    }
    originals_unchanged = (
        original_solution_hashes == solution_hashes_after
        and original_test_hashes == test_hashes_after
    )
    if not originals_unchanged:
        failures.append("The original learner solution or test source changed.")

    results = {
        "success": not failures,
        "command": command,
        "return_code": return_code,
        "preparation_check_return_code": preparation.returncode,
        "preparation_check_stdout": preparation.stdout,
        "preparation_check_stderr": preparation.stderr,
        "expected_test_count": len(expected_test_names),
        "actual_test_count": (
            actual_counts["total"] if actual_counts is not None else None
        ),
        "counts": actual_counts,
        "enabled_skipped_test_count": skipped_test_count,
        "expected_case_results": EXPECTED_CASES,
        "actual_tests": actual_tests,
        "original_solution_sha256_after": solution_hashes_after,
        "original_test_sha256_after": test_hashes_after,
        "original_solution_and_tests_unchanged": originals_unchanged,
        "preparation_results": preparation_report,
        "failure_reasons": failures,
        "stdout": stdout,
        "stderr": stderr,
    }
    save_json(OUTPUT_DIR / "inputs.json", inputs)
    save_json(OUTPUT_DIR / "results.json", results)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"Details saved in {OUTPUT_DIR}", file=sys.stderr)
        return 1

    print(
        f"PASS: {actual_counts['total']} tests passed against the reference; "
        f"{canonical_counts['included']} canonical cases included and "
        f"{canonical_counts['excluded']} excluded."
    )
    print(f"Results saved in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
