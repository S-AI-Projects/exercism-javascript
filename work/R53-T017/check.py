#!/usr/bin/env python3
"""Verify Word Count tests and JavaScript lowercase examples."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "word-count"
OUTPUT = Path(__file__).resolve().parent
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")
MICRO_EXAMPLES = """\
const ascii = 'HELLO'.toLowerCase();
const unicode = 'İ'.toLowerCase();
console.log(JSON.stringify({
  ascii,
  unicode,
  unicodeEqualsPlainI: unicode === 'i',
  unicodeCodePoints: Array.from(unicode, (char) =>
    char.codePointAt(0).toString(16),
  ),
}));
"""


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def run_micro_examples():
    command = ["node", "-e", MICRO_EXAMPLES]
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    actual = None
    if result.returncode == 0:
        actual = json.loads(result.stdout)

    ascii_example = {
        "input": "'HELLO'.toLowerCase()",
        "expected": "hello",
        "actual": actual.get("ascii") if actual else None,
    }
    ascii_example["passed"] = ascii_example["actual"] == ascii_example["expected"]

    unicode_example = {
        "input": "'İ'.toLowerCase() === 'i'",
        "expected": False,
        "actual": actual.get("unicodeEqualsPlainI") if actual else None,
        "lowercase_value": actual.get("unicode") if actual else None,
        "code_points": actual.get("unicodeCodePoints") if actual else None,
    }
    unicode_example["passed"] = (
        unicode_example["actual"] is unicode_example["expected"]
        and unicode_example["lowercase_value"] == "i\u0307"
        and unicode_example["code_points"] == ["69", "307"]
    )

    return {
        "command": command,
        "return_code": result.returncode,
        "output": result.stdout.strip(),
        "error_output": result.stderr.strip(),
        "examples": {
            "ascii_lowercase": ascii_example,
            "unicode_lowercase": unicode_example,
        },
    }


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
    expected_names = [
        match.group(2)
        for source in test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    expected_count = len(expected_names)
    expected_skips = sum(
        len(SKIPPED_CALL.findall(source)) for source in test_sources.values()
    )
    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    original_tests = {
        path: (EXERCISE / path).read_bytes() for path in test_paths
    }
    versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", versions)

    failures = []
    skipped_enabled = 0
    full_run = None
    with tempfile.TemporaryDirectory(prefix="word-count-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_exercise = temp_root / "word-count"
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
            skipped_enabled += replacements
            copied_test.write_text(enabled, encoding="utf-8")

        if skipped_enabled != expected_skips:
            failures.append("Not all skipped tests were enabled in the temporary copy.")
        package = json.loads(
            (temp_exercise / "package.json").read_text(encoding="utf-8")
        )
        if "test" not in package.get("scripts", {}):
            failures.append("The exercise package.json has no test command.")

        full_run = run_tests(temp_exercise, temp_root / "jest-results.json")

    if full_run["return_code"] != 0:
        failures.append("The exercise test command exited unsuccessfully.")
    counts = full_run["counts"]
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
    if len(full_run["cases"]) != expected_count:
        failures.append("The run did not report every test assertion.")
    for case in full_run["cases"]:
        if case["actual_status"] != case["expected_status"]:
            failures.append(
                f"Test assertion failed: {case['name']} ({case['actual_status']})."
            )

    micro_examples = run_micro_examples()
    if micro_examples["return_code"] != 0:
        failures.append("The JavaScript micro-examples did not run successfully.")
    for name, example in micro_examples["examples"].items():
        if not example["passed"]:
            failures.append(f"The {name} micro-example produced an unexpected result.")

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
        "expected_test_names": expected_names,
        "expected_test_count": expected_count,
        "expected_skipped_tests_enabled": expected_skips,
        "micro_examples": {
            "ascii": "'HELLO'.toLowerCase() should produce 'hello'.",
            "unicode": (
                "'İ'.toLowerCase() === 'i' should be false because the lowercase "
                "string contains an additional combining dot."
            ),
        },
    }
    results = {
        "success": not failures,
        "expected_test_count": expected_count,
        "skipped_tests_enabled": skipped_enabled,
        "exercise_run": full_run,
        "micro_examples": micro_examples,
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
        f"PASS: all {expected_count} exercise tests passed, and both "
        "JavaScript micro-examples matched their expected outputs."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
