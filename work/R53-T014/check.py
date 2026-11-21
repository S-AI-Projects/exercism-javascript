#!/usr/bin/env python3
"""Compare secret-handshake tests before and after the reference refactor."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "secret-handshake"
OUTPUT = Path(__file__).resolve().parent
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
                        "status": assertion.get("status"),
                    }
                )
    return {
        "command": command,
        "return_code": result.returncode,
        "counts": counts,
        "cases": cases,
        "output_excerpt": (result.stdout + result.stderr)[-1000:],
    }


def prepare_copy(destination, solution_paths, test_paths, reference_source):
    shutil.copytree(
        EXERCISE,
        destination,
        ignore=shutil.ignore_patterns("node_modules"),
    )
    dependencies = ROOT / "node_modules"
    if dependencies.is_dir():
        (destination / "node_modules").symlink_to(
            dependencies, target_is_directory=True
        )

    for solution_path in solution_paths:
        (destination / solution_path).write_text(
            reference_source, encoding="utf-8"
        )

    enabled_sources = {}
    skipped_count = 0
    for test_path in test_paths:
        copied_test = destination / test_path
        source = copied_test.read_text(encoding="utf-8")
        enabled, replacements = SKIPPED_CALL.subn("test", source)
        skipped_count += replacements
        copied_test.write_text(enabled, encoding="utf-8")
        enabled_sources[test_path] = enabled
    return enabled_sources, skipped_count


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(
        (EXERCISE / ".meta" / "config.json").read_text(encoding="utf-8")
    )
    files = config["files"]
    solution_paths = files["solution"]
    test_paths = files["test"]
    example_paths = files["example"]
    if not solution_paths or len(example_paths) != 1:
        raise ValueError("The exercise config must list solution and example files.")
    if not test_paths:
        raise ValueError("The exercise config does not list test files.")

    example_path = example_paths[0]
    repo_example_path = (
        EXERCISE.relative_to(ROOT) / example_path
    ).as_posix()
    before_process = subprocess.run(
        ["git", "show", f"HEAD:{repo_example_path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if before_process.returncode != 0:
        raise RuntimeError("Could not read the original reference from HEAD.")
    before_reference = before_process.stdout
    after_reference = (EXERCISE / example_path).read_text(encoding="utf-8")

    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    original_tests = {
        path: (EXERCISE / path).read_bytes() for path in test_paths
    }
    original_test_sources = {
        path: contents.decode("utf-8") for path, contents in original_tests.items()
    }
    expected_names = [
        match.group(2)
        for source in original_test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    expected_test_count = len(expected_names)
    expected_skipped_count = sum(
        len(SKIPPED_CALL.findall(source))
        for source in original_test_sources.values()
    )
    tool_versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", tool_versions)

    failures = []
    before_run = None
    after_run = None
    enabled_test_sources = {}
    skipped_counts = {}
    with tempfile.TemporaryDirectory(prefix="secret-handshake-") as temp_dir:
        temp_root = Path(temp_dir)
        copies = {}
        for name, reference in (
            ("before", before_reference),
            ("after", after_reference),
        ):
            copy = temp_root / name / "secret-handshake"
            copy.parent.mkdir()
            enabled_test_sources[name], skipped_counts[name] = prepare_copy(
                copy, solution_paths, test_paths, reference
            )
            copies[name] = copy
            if not (ROOT / "node_modules").is_dir():
                failures.append("Repository node_modules are missing.")

        if enabled_test_sources["before"] != enabled_test_sources["after"]:
            failures.append("Before and after runs do not use identical tests.")
        if any(count != expected_skipped_count for count in skipped_counts.values()):
            failures.append("Not all skipped tests were enabled in both copies.")

        before_run = run_tests(copies["before"], temp_root / "before-results.json")
        after_run = run_tests(copies["after"], temp_root / "after-results.json")

    for name, result in (("before", before_run), ("after", after_run)):
        if result["return_code"] != 0:
            failures.append(f"The {name} test command exited unsuccessfully.")
        if result["counts"] is None:
            failures.append(f"The {name} run did not produce Jest results.")
        elif result["counts"]["total"] == 0:
            failures.append(f"The {name} run executed zero tests.")
        elif result["counts"]["total"] != expected_test_count:
            failures.append(
                f"The {name} run executed {result['counts']['total']} tests; "
                f"expected {expected_test_count}."
            )
        elif (
            result["counts"]["failed"] != 0
            or result["counts"]["passed"] != expected_test_count
        ):
            failures.append(f"Not all tests passed in the {name} run.")

    same_results = before_run["cases"] == after_run["cases"]
    if not same_results:
        failures.append("Test outputs differ before and after the refactor.")

    learner_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_solutions.items()
    )
    tests_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_tests.items()
    )
    if not learner_unchanged:
        failures.append("The learner solution changed.")
    if not tests_unchanged:
        failures.append("The maintained test source changed.")

    inputs = {
        "config": config,
        "before_reference": before_reference,
        "after_reference": after_reference,
        "test_sources": original_test_sources,
        "expected_test_names": expected_names,
        "skipped_tests_enabled_per_run": skipped_counts,
    }
    results = {
        "success": not failures,
        "expected_test_count": expected_test_count,
        "before": before_run,
        "after": after_run,
        "same_test_results": same_results,
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
        f"PASS: before and after results match; "
        f"all {expected_test_count} tests passed."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
