#!/usr/bin/env python3
"""Verify the say exercise using its reference in a temporary copy."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "say"
OUTPUT_DIR = Path(__file__).resolve().parent
TEST_CALL = re.compile(r"\b(x?test)\s*\(\s*(['\"])(.*?)\2", re.DOTALL)
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")


def run_version(command):
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not get version for {command[0]}: {result.stderr.strip()}"
        )
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


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    config_path = EXERCISE / ".meta" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    files = config["files"]
    solution_paths = files["solution"]
    test_paths = files["test"]
    example_paths = files["example"]

    if len(solution_paths) != 1 or len(example_paths) != 1:
        raise ValueError("This verifier expects one solution and one example file.")
    if not test_paths:
        raise ValueError("The exercise config does not list any test files.")

    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    solution_hashes_before = {
        path: hashlib.sha256(contents).hexdigest()
        for path, contents in original_solutions.items()
    }
    before_counts = inclusion_counts(EXERCISE / ".meta" / "tests.toml")

    test_source_by_path = {
        path: (EXERCISE / path).read_text(encoding="utf-8") for path in test_paths
    }
    expected_test_names = []
    skipped_test_count = 0
    for source in test_source_by_path.values():
        expected_test_names.extend(match.group(3) for match in TEST_CALL.finditer(source))
        skipped_test_count += len(SKIPPED_CALL.findall(source))

    versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
    }
    save_json(OUTPUT_DIR / "tool-versions.json", versions)

    inputs = {
        "config": config,
        "solution_paths": solution_paths,
        "test_paths": test_paths,
        "example_paths": example_paths,
        "canonical_cases": {
            "before": before_counts,
        },
        "test_sources": test_source_by_path,
        "expected_test_names": expected_test_names,
        "skipped_tests_enabled_in_temporary_copy": skipped_test_count,
        "original_solution_sha256_before": solution_hashes_before,
    }

    reasons = []
    test_result = None
    actual_counts = None
    return_code = None
    stdout = ""
    stderr = ""

    with tempfile.TemporaryDirectory(prefix="say-reference-") as temp_dir:
        temp_exercise = Path(temp_dir) / "say"
        shutil.copytree(
            EXERCISE,
            temp_exercise,
            ignore=shutil.ignore_patterns("node_modules"),
        )

        dependency_dir = EXERCISE / "node_modules"
        if not dependency_dir.is_dir():
            dependency_dir = ROOT / "node_modules"
        if dependency_dir.is_dir():
            (temp_exercise / "node_modules").symlink_to(
                dependency_dir, target_is_directory=True
            )

        reference_path = temp_exercise / example_paths[0]
        for solution_path in solution_paths:
            shutil.copyfile(reference_path, temp_exercise / solution_path)

        changed_skips = 0
        for test_path in test_paths:
            copied_test = temp_exercise / test_path
            test_source = copied_test.read_text(encoding="utf-8")
            enabled_source, replacements = SKIPPED_CALL.subn("test", test_source)
            changed_skips += replacements
            copied_test.write_text(enabled_source, encoding="utf-8")

        if changed_skips != skipped_test_count:
            reasons.append(
                "The number of enabled skipped tests did not match the source."
            )

        after_counts = inclusion_counts(temp_exercise / ".meta" / "tests.toml")
        inputs["canonical_cases"]["after"] = after_counts

        package = json.loads(
            (temp_exercise / "package.json").read_text(encoding="utf-8")
        )
        if "test" not in package.get("scripts", {}):
            raise ValueError("The exercise package.json has no test script.")

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

        if report_path.exists():
            test_result = json.loads(report_path.read_text(encoding="utf-8"))
            actual_counts = {
                "total": test_result.get("numTotalTests"),
                "passed": test_result.get("numPassedTests"),
                "failed": test_result.get("numFailedTests"),
                "pending": test_result.get("numPendingTests"),
            }
        else:
            reasons.append("Jest did not create its JSON results file.")

    solution_hashes_after = {
        path: sha256(EXERCISE / path) for path in solution_paths
    }
    original_unchanged = solution_hashes_before == solution_hashes_after
    if not original_unchanged:
        reasons.append("The original learner solution changed during verification.")
    if return_code != 0:
        reasons.append(f"The package test script exited with status {return_code}.")
    if test_result is None:
        actual_test_count = None
    else:
        actual_test_count = actual_counts["total"]
        if actual_test_count == 0:
            reasons.append("Jest ran zero tests.")
        if actual_test_count != len(expected_test_names):
            reasons.append(
                f"Expected {len(expected_test_names)} tests, but Jest ran "
                f"{actual_test_count}."
            )
        if actual_counts["failed"] != 0:
            reasons.append(
                f"Jest reported {actual_counts['failed']} failed tests."
            )
        if actual_counts["passed"] != actual_test_count:
            reasons.append("Not every executed test passed.")

    actual_tests = []
    if test_result is not None:
        for test_file in test_result.get("testResults", []):
            for assertion in test_file.get("assertionResults", []):
                actual_tests.append(
                    {
                        "name": assertion.get("fullName"),
                        "status": assertion.get("status"),
                        "failure_messages": assertion.get("failureMessages", []),
                    }
                )

    success = not reasons
    results = {
        "success": success,
        "command": command,
        "return_code": return_code,
        "expected_test_count": len(expected_test_names),
        "actual_test_count": actual_test_count,
        "counts": actual_counts,
        "enabled_skipped_test_count": skipped_test_count,
        "original_solution_unchanged": original_unchanged,
        "original_solution_sha256_after": solution_hashes_after,
        "included_excluded_counts_before_and_after": inputs["canonical_cases"],
        "actual_tests": actual_tests,
        "failure_reasons": reasons,
        "stdout": stdout,
        "stderr": stderr,
    }
    save_json(OUTPUT_DIR / "inputs.json", inputs)
    save_json(OUTPUT_DIR / "results.json", results)

    if not success:
        for reason in reasons:
            print(f"FAIL: {reason}", file=sys.stderr)
        print(f"Details saved in {OUTPUT_DIR}", file=sys.stderr)
        return 1

    print(
        f"PASS: {actual_test_count} tests passed; "
        f"{before_counts['included']} included and "
        f"{before_counts['excluded']} excluded before and after."
    )
    print(f"Results saved in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
