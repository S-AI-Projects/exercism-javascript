#!/usr/bin/env python3
"""Check perfect-numbers tests against the reference and a temporary mutant."""

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
EXERCISE = ROOT / "exercises" / "practice" / "perfect-numbers"
OUTPUT = Path(__file__).resolve().parent
MUTATION_FROM = "i <= number / 2"
MUTATION_TO = "i < number / 2"
DETECTING_UUID = "163e8e86-7bfd-4ee2-bd68-d083dc3381a3"
DETECTING_TEST = "Smallest perfect number is classified correctly"
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")
DIAGNOSTIC_INPUTS = list(range(1, 7))
EXPECTED_CLASSIFICATIONS = ["deficient"] * 5 + ["perfect"]
PROBE_SOURCE = """\
import { writeFileSync } from 'node:fs';
import { classify } from './perfect-numbers';

test('records classifications for inputs 1 through 6', () => {
  const results = [];
  for (let input = 1; input <= 6; input += 1) {
    results.push({ input, classification: classify(input) });
  }
  writeFileSync(process.env.MUTATION_PROBE_OUTPUT, JSON.stringify(results));
});
"""


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def get_version(command):
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not get version for {command[0]}.")
    return result.stdout.strip()


def run_tests(exercise, extra_args, report_path, extra_env=None):
    command = [
        "npm",
        "run",
        "test",
        "--",
        "--watch=false",
        "--runInBand",
        *extra_args,
        "--json",
        f"--outputFile={report_path}",
    ]
    environment = os.environ.copy()
    if extra_env:
        environment.update(extra_env)
    child = subprocess.run(
        command,
        cwd=exercise,
        env=environment,
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
    assertions = []
    if report is not None:
        counts = {
            "total": report.get("numTotalTests"),
            "passed": report.get("numPassedTests"),
            "failed": report.get("numFailedTests"),
            "pending": report.get("numPendingTests"),
        }
        for test_file in report.get("testResults", []):
            for assertion in test_file.get("assertionResults", []):
                assertions.append(
                    {
                        "name": assertion.get("fullName"),
                        "status": assertion.get("status"),
                    }
                )
    return {
        "command": command,
        "return_code": child.returncode,
        "counts": counts,
        "assertions": assertions,
        "output_excerpt": (child.stdout + child.stderr)[-1200:],
    }


def copy_exercise(destination, solution_paths, test_paths, example_paths):
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

    for solution, example in zip(solution_paths, example_paths):
        shutil.copyfile(destination / example, destination / solution)

    changed_skips = 0
    enabled_sources = {}
    for test_path in test_paths:
        copied_test = destination / test_path
        source = copied_test.read_text(encoding="utf-8")
        enabled, replacements = SKIPPED_CALL.subn("test", source)
        changed_skips += replacements
        copied_test.write_text(enabled, encoding="utf-8")
        enabled_sources[test_path] = enabled
    return enabled_sources, changed_skips


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
        raise ValueError("The exercise config lists no test files.")

    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    original_examples = {
        path: (EXERCISE / path).read_bytes() for path in example_paths
    }
    original_tests = {
        path: (EXERCISE / path).read_bytes() for path in test_paths
    }
    test_sources = {
        path: contents.decode("utf-8") for path, contents in original_tests.items()
    }
    expected_test_names = [
        match.group(2)
        for source in test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    skipped_count = sum(
        len(SKIPPED_CALL.findall(source)) for source in test_sources.values()
    )

    with (EXERCISE / ".meta" / "tests.toml").open("rb") as tests_file:
        canonical_cases = tomllib.load(tests_file)
    detecting_case = canonical_cases.get(DETECTING_UUID)
    failures = []
    if detecting_case is None:
        failures.append(f"Detecting UUID {DETECTING_UUID} is missing.")
    elif DETECTING_TEST not in detecting_case.get("description", ""):
        failures.append("The detecting UUID does not match the test name.")
    if DETECTING_TEST not in expected_test_names:
        failures.append("The detecting test is missing from the test source.")

    versions = {
        "python": sys.version.split()[0],
        "node": get_version(["node", "--version"]),
        "npm": get_version(["npm", "--version"]),
        "pnpm": get_version(["corepack", "pnpm", "--version"]),
        "jest": get_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", versions)

    original_run = None
    mutant_run = None
    original_probe = None
    mutant_probe = None
    original_values = None
    mutant_values = None
    mutation_count = 0
    differences = []

    with tempfile.TemporaryDirectory(prefix="perfect-numbers-mutation-") as work:
        temp_root = Path(work)
        copies = {}
        enabled_sources = {}
        changed_skips = {}

        for name in ("original", "mutated"):
            exercise = temp_root / name / "perfect-numbers"
            exercise.parent.mkdir()
            enabled_sources[name], changed_skips[name] = copy_exercise(
                exercise, solution_paths, test_paths, example_paths
            )
            copies[name] = exercise
            if not (ROOT / "node_modules").is_dir():
                failures.append("Repository node_modules are missing.")

        if enabled_sources["original"] != enabled_sources["mutated"]:
            failures.append("The original and mutant do not have identical tests.")
        if any(count != skipped_count for count in changed_skips.values()):
            failures.append("Not all skipped tests were enabled in both copies.")

        mutant_solution = copies["mutated"] / solution_paths[0]
        reference_source = mutant_solution.read_text(encoding="utf-8")
        mutation_count = reference_source.count(MUTATION_FROM)
        if mutation_count == 1:
            mutant_solution.write_text(
                reference_source.replace(MUTATION_FROM, MUTATION_TO, 1),
                encoding="utf-8",
            )
        else:
            failures.append(f"Expected one mutation target, found {mutation_count}.")

        for name, exercise in copies.items():
            package = json.loads(
                (exercise / "package.json").read_text(encoding="utf-8")
            )
            if "test" not in package.get("scripts", {}):
                failures.append("The exercise package.json has no test script.")

        original_run = run_tests(
            copies["original"], [], temp_root / "original-tests.json"
        )
        mutant_run = run_tests(
            copies["mutated"], [], temp_root / "mutated-tests.json"
        )

        for name, run in (("original", original_run), ("mutated", mutant_run)):
            if run["counts"] is None:
                failures.append(f"The {name} run did not produce Jest results.")
            elif run["counts"]["total"] == 0:
                failures.append(f"The {name} run executed zero tests.")
            elif run["counts"]["total"] != len(expected_test_names):
                failures.append(
                    f"The {name} run executed {run['counts']['total']} tests; "
                    f"expected {len(expected_test_names)}."
                )

        if original_run["return_code"] != 0:
            failures.append("The original reference did not pass.")
        if original_run["counts"] is not None and (
            original_run["counts"]["passed"] != len(expected_test_names)
            or original_run["counts"]["failed"] != 0
        ):
            failures.append("The original reference has unexpected test results.")

        if mutant_run["return_code"] == 0:
            failures.append("The mutated reference unexpectedly passed.")
        failed_mutant_tests = [
            item["name"]
            for item in mutant_run["assertions"]
            if item["status"] == "failed"
        ]
        if DETECTING_TEST not in " ".join(failed_mutant_tests):
            failures.append("The mutation did not fail the detecting test.")

        probe_path = "mutation-boundary-probe.spec.js"
        for exercise in copies.values():
            (exercise / probe_path).write_text(PROBE_SOURCE, encoding="utf-8")

        original_probe_path = temp_root / "original-probe-values.json"
        mutant_probe_path = temp_root / "mutant-probe-values.json"
        original_probe = run_tests(
            copies["original"],
            ["--runTestsByPath", probe_path],
            temp_root / "original-probe-tests.json",
            {"MUTATION_PROBE_OUTPUT": str(original_probe_path)},
        )
        mutant_probe = run_tests(
            copies["mutated"],
            ["--runTestsByPath", probe_path],
            temp_root / "mutant-probe-tests.json",
            {"MUTATION_PROBE_OUTPUT": str(mutant_probe_path)},
        )

        for name, probe in (("original", original_probe), ("mutated", mutant_probe)):
            if probe["return_code"] != 0:
                failures.append(f"The {name} diagnostic run failed.")
            if probe["counts"] is None or probe["counts"]["total"] != 1:
                failures.append(f"The {name} diagnostic run did not execute one test.")

        if original_probe_path.is_file() and mutant_probe_path.is_file():
            original_values = json.loads(
                original_probe_path.read_text(encoding="utf-8")
            )
            mutant_values = json.loads(mutant_probe_path.read_text(encoding="utf-8"))
            if [item["input"] for item in original_values] != DIAGNOSTIC_INPUTS:
                failures.append("The original diagnostic inputs were not 1 through 6.")
            if [item["input"] for item in mutant_values] != DIAGNOSTIC_INPUTS:
                failures.append("The mutant did not receive inputs 1 through 6.")
            if [item["classification"] for item in original_values] != (
                EXPECTED_CLASSIFICATIONS
            ):
                failures.append("The original diagnostic results were unexpected.")
            differences = [
                {
                    "input": original["input"],
                    "expected": original["classification"],
                    "actual": mutant["classification"],
                }
                for original, mutant in zip(original_values, mutant_values)
                if original["classification"] != mutant["classification"]
            ]
            if not differences or differences[0]["input"] != 6:
                failures.append("The smallest differing input was not 6.")
        else:
            failures.append("The diagnostic runs did not save both result files.")

    learner_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_solutions.items()
    )
    reference_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_examples.items()
    )
    tests_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_tests.items()
    )
    if not learner_unchanged:
        failures.append("The learner solution changed.")
    if not reference_unchanged:
        failures.append("The original reference changed.")
    if not tests_unchanged:
        failures.append("The original test file changed.")

    inputs = {
        "config": config,
        "test_sources": test_sources,
        "expected_test_names": expected_test_names,
        "enabled_skipped_test_count": skipped_count,
        "mutation": {"from": MUTATION_FROM, "to": MUTATION_TO, "matches": mutation_count},
        "detecting_test": {"uuid": DETECTING_UUID, "name": DETECTING_TEST},
        "diagnostic_inputs": DIAGNOSTIC_INPUTS,
        "expected_diagnostic_classifications": EXPECTED_CLASSIFICATIONS,
    }
    results = {
        "success": not failures,
        "expected_test_count": len(expected_test_names),
        "original": original_run,
        "mutated": mutant_run,
        "failed_mutant_tests": failed_mutant_tests,
        "original_diagnostic_results": original_values,
        "mutated_diagnostic_results": mutant_values,
        "classification_differences": differences,
        "smallest_differing_input": differences[0]["input"] if differences else None,
        "learner_solution_unchanged": learner_unchanged,
        "reference_unchanged": reference_unchanged,
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
        f"PASS: original passed {original_run['counts']['total']} tests; "
        f"mutant failed the detecting test; input 6 is the first difference."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
