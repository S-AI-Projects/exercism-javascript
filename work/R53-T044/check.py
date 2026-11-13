#!/usr/bin/env python3
"""Compare Armstrong reference behavior before and after a readability refactor."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/armstrong-numbers")
BEFORE_REFERENCE = Path("work/R53-T044/proof.ci.before.js")
TEST_DECLARATION = re.compile(
    r"\b(x?test|test)\s*\(\s*(['\"])(.*?)\2\s*,\s*\(\)\s*=>\s*\{(?P<body>.*?)^\s*\}\);",
    re.S | re.M,
)
ASSERTION = re.compile(
    r"expect\s*\(\s*isArmstrongNumber\((?P<input>[^)]*)\)\s*\)\s*"
    r"\.toEqual\((?P<expected>true|false)\)",
    re.S,
)
PROBE_SOURCE = """import fs from 'node:fs';
import { expect, test } from '@jest/globals';
import { isArmstrongNumber } from './armstrong-numbers';

const cases = JSON.parse(process.env.ARMSTRONG_CASES);
const actual = cases.map(({ name, input, expected }) => {
  const value = input.endsWith('n') ? BigInt(input.slice(0, -1)) : Number(input);
  return { name, input, expected, actual: isArmstrongNumber(value) };
});

test('capture actual Armstrong outputs', () => {
  fs.writeFileSync(process.env.ARMSTRONG_OUTPUT, JSON.stringify(actual, null, 2));
  expect(actual.map(({ actual: result }) => result)).toEqual(
    cases.map(({ expected }) => expected),
  );
});
"""


class CheckError(Exception):
    pass


def find_root():
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / "scripts" / "helpers.mjs").is_file()
            and (candidate / ASSIGNMENT / ".meta" / "config.json").is_file()
        ):
            return candidate
    raise CheckError("Could not locate repository root")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_process(command, cwd, environment, label, processes):
    result = subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    record = {
        "label": label,
        "command": [str(part) for part in command],
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    processes.append(record)
    if result.returncode != 0:
        raise CheckError(
            "%s exited with %d\n%s\n%s"
            % (label, result.returncode, result.stdout, result.stderr)
        )
    return result


def resolve_files(exercise, config):
    file_config = config.get("files")
    if not isinstance(file_config, dict):
        raise CheckError("Exercise config is missing its files object")
    resolved = {}
    for kind in ("solution", "test", "example"):
        names = file_config.get(kind)
        if not isinstance(names, list) or not names:
            raise CheckError("Config files.%s must be a non-empty list" % kind)
        resolved[kind] = []
        for name in names:
            if not isinstance(name, str) or not name:
                raise CheckError("Invalid configured %s path" % kind)
            relative = Path(name.replace("%{kebab_slug}", "armstrong-numbers"))
            source = (exercise / relative).resolve()
            if not source.is_relative_to(exercise.resolve()):
                raise CheckError("Configured path escapes the exercise: %s" % name)
            if not source.is_file():
                raise CheckError("Configured %s file is missing: %s" % (kind, source))
            resolved[kind].append((relative, source))
    return resolved


def parse_cases(spec_source):
    cases = []
    for match in TEST_DECLARATION.finditer(spec_source):
        assertion = ASSERTION.search(match.group("body"))
        if not assertion:
            raise CheckError("Could not extract assertion from test %r" % match.group(3))
        input_expression = assertion.group("input").strip()
        if input_expression == "bigInput":
            big_input = re.search(r"const\s+bigInput\s*=\s*(\d+)n\s*;", match.group("body"))
            if not big_input:
                raise CheckError("Could not resolve bigInput in test %r" % match.group(3))
            input_value = big_input.group(1) + "n"
        elif re.fullmatch(r"\d+", input_expression):
            input_value = input_expression
        else:
            raise CheckError("Unsupported test input in %r: %s" % (match.group(3), input_expression))
        cases.append(
            {
                "name": match.group(3),
                "input": input_value,
                "expected": assertion.group("expected") == "true",
                "enabled_in_learner_suite": match.group(1) == "test",
            }
        )
    if not cases:
        raise CheckError("No Armstrong test cases were parsed")
    names = [case["name"] for case in cases]
    if len(names) != len(set(names)):
        raise CheckError("Duplicate test names in exercise spec")
    return cases


def enable_optional_tests(source):
    source = re.sub(r"\bx(test|it)\(", "test(", source)
    return re.sub(r"\bxdescribe\(", "describe(", source)


def validate_jest_result(result, expected_count, label):
    if not isinstance(result, dict):
        raise CheckError("%s produced no parseable Jest JSON result" % label)
    counts = [result.get(key) for key in ("numTotalTests", "numPassedTests", "numFailedTests")]
    if not all(isinstance(value, int) for value in counts):
        raise CheckError("%s Jest JSON omitted test counts" % label)
    total, passed, failed = counts
    if total == 0:
        raise CheckError("%s executed zero tests" % label)
    if total != expected_count:
        raise CheckError("%s executed %d tests; expected %d" % (label, total, expected_count))
    if failed != 0 or passed != total:
        raise CheckError("%s had %d failed assertions (%d passed)" % (label, failed, passed))
    return {"executed": total, "passed": passed, "failed": failed}


def verify_result_guards():
    invalid_results = [
        {"numTotalTests": 0, "numPassedTests": 0, "numFailedTests": 0},
        {"numTotalTests": 1, "numPassedTests": 0, "numFailedTests": 1},
        {"numTotalTests": None, "numPassedTests": 0, "numFailedTests": 0},
    ]
    for result in invalid_results:
        try:
            validate_jest_result(result, 1, "checker guard self-test")
        except CheckError:
            continue
        raise CheckError("Checker guard accepted invalid Jest counts: %r" % result)
    return {
        "zero_tests_rejected": True,
        "assertion_failure_rejected": True,
        "missing_test_count_rejected": True,
    }


def clone_variant(source_exercise, files, reference_path, destination):
    shutil.copytree(source_exercise, destination)
    original_files = {
        path.relative_to(source_exercise).as_posix()
        for path in source_exercise.rglob("*")
        if path.is_file()
    }
    copied_files = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    }
    if copied_files != original_files:
        raise CheckError("Temporary exercise copy omitted one or more files")
    for relative, _ in files["solution"]:
        shutil.copy2(reference_path, destination / relative)
    for relative, _ in files["test"]:
        copied_test = destination / relative
        copied_test.write_text(
            enable_optional_tests(copied_test.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
    return len(copied_files)


def jest_command(root, copied_exercise, test_script, test_paths, result_path):
    if not isinstance(test_script, str) or not test_script.strip():
        raise CheckError("Armstrong exercise package.json has no test script")
    return [
        "corepack",
        "pnpm",
        "--dir",
        str(copied_exercise),
        "run",
        "test",
        "--runInBand",
        "--watch=false",
        "--runTestsByPath",
        *[path.as_posix() for path in test_paths],
        "--json",
        "--outputFile",
        str(result_path),
    ]


def run_variant(root, source_exercise, files, package, cases, reference_path, label, temp_root, env, report):
    copied_exercise = temp_root / label
    copied_count = clone_variant(source_exercise, files, reference_path, copied_exercise)
    test_script = package.get("scripts", {}).get("test")
    test_paths = [relative for relative, _ in files["test"]]
    report_path = temp_root / (label + "-jest.json")
    command = jest_command(root, copied_exercise, test_script, test_paths, report_path)
    process = run_process(command, root, env, label + " exercise test script", report["processes"])
    if not report_path.is_file():
        raise CheckError("%s did not write the Jest JSON result" % label)
    jest_result = json.loads(report_path.read_text(encoding="utf-8"))
    counts = validate_jest_result(jest_result, len(cases), label)

    statuses = {}
    for suite in jest_result.get("testResults", []):
        for assertion in suite.get("assertionResults", []):
            statuses[assertion.get("title")] = assertion.get("status")
    if set(statuses) != {case["name"] for case in cases}:
        raise CheckError("%s executed a different set of cases than the maintained spec" % label)
    if any(status != "passed" for status in statuses.values()):
        raise CheckError("%s contains a failed assertion" % label)

    probe_path = copied_exercise / "armstrong-reference-probe.spec.js"
    probe_path.write_text(PROBE_SOURCE, encoding="utf-8")
    actual_path = temp_root / (label + "-outputs.json")
    probe_env = env.copy()
    probe_env["ARMSTRONG_CASES"] = json.dumps(cases)
    probe_env["ARMSTRONG_OUTPUT"] = str(actual_path)
    probe_result_path = temp_root / (label + "-probe-jest.json")
    probe_command = jest_command(
        root,
        copied_exercise,
        test_script,
        [Path(probe_path.name)],
        probe_result_path,
    )
    probe_process = run_process(
        probe_command, root, probe_env, label + " output probe", report["processes"]
    )
    if not probe_result_path.is_file() or not actual_path.is_file():
        raise CheckError("%s probe did not create its result files" % label)
    probe_jest_result = json.loads(probe_result_path.read_text(encoding="utf-8"))
    probe_counts = validate_jest_result(probe_jest_result, 1, label + " output probe")
    actual_outputs = json.loads(actual_path.read_text(encoding="utf-8"))
    if len(actual_outputs) != len(cases):
        raise CheckError("%s probe returned an incomplete output list" % label)
    for expected, actual in zip(cases, actual_outputs):
        if actual["name"] != expected["name"] or actual["input"] != expected["input"]:
            raise CheckError("%s probe output order/input differs from the spec" % label)
        if actual["expected"] != expected["expected"] or actual["actual"] != expected["expected"]:
            raise CheckError("%s output disagrees with the canonical assertion for %s" % (label, expected["name"]))

    return {
        "label": label,
        "test_command": command,
        "test_return_code": process.returncode,
        "test_counts": counts,
        "test_statuses": statuses,
        "exercise_file_count_copied": copied_count,
        "probe_command": probe_command,
        "probe_return_code": probe_process.returncode,
        "probe_counts": probe_counts,
        "outputs": actual_outputs,
    }


def arithmetic_trace(input_text):
    number = int(input_text[:-1] if input_text.endswith("n") else input_text)
    digits = [int(digit) for digit in str(number)]
    powers = [digit ** len(digits) for digit in digits]
    return {
        "input": input_text,
        "digits": digits,
        "digit_count_exponent": len(digits),
        "powered_digits": powers,
        "sum": sum(powers),
        "is_armstrong": sum(powers) == number,
    }


def main():
    root = None
    report = {
        "task": "R53-T044",
        "success": False,
        "inputs": {},
        "before": {},
        "after": {},
        "comparison": {},
        "processes": [],
        "tool_versions": {},
        "guard_self_tests": {},
    }
    error = None
    evidence_directory = Path(__file__).resolve().parent
    try:
        root = find_root()
        exercise = root / ASSIGNMENT
        config_path = exercise / ".meta" / "config.json"
        package_path = exercise / "package.json"
        spec_path = exercise / "armstrong-numbers.spec.js"
        learner_path = exercise / "armstrong-numbers.js"
        before_reference = root / BEFORE_REFERENCE
        after_reference = exercise / ".meta" / "proof.ci.js"
        for required in (config_path, package_path, spec_path, learner_path, before_reference, after_reference):
            if not required.is_file():
                raise CheckError("Required Armstrong file is missing: %s" % required)

        config = json.loads(config_path.read_text(encoding="utf-8"))
        package = json.loads(package_path.read_text(encoding="utf-8"))
        root_package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        package_manager = root_package.get("packageManager", "")
        if not package_manager.startswith("pnpm@") or not (root / "pnpm-lock.yaml").is_file():
            raise CheckError("Root packageManager/pnpm-lock.yaml does not select pnpm")
        if package.get("packageManager") != package_manager:
            raise CheckError("Exercise packageManager differs from root packageManager")
        files = resolve_files(exercise, config)
        if len(files["solution"]) != len(files["example"]):
            raise CheckError("Configured solution and example counts differ")
        cases = parse_cases(spec_path.read_text(encoding="utf-8"))
        enabled_count = sum(case["enabled_in_learner_suite"] for case in cases)
        learner_hash_before = sha256(learner_path)
        spec_hash_before = sha256(spec_path)
        reference_hash_after_before_check = sha256(after_reference)
        before_hash = sha256(before_reference)
        guard_results = verify_result_guards()

        env = os.environ.copy()
        env["PATH"] = str(root / "node_modules" / ".bin") + os.pathsep + env.get("PATH", "")
        env["NODE_PATH"] = str(root / "node_modules")
        env["CI"] = "1"
        versions = {}
        for name, command in (
            ("node", ["node", "--version"]),
            ("pnpm", ["corepack", "pnpm", "--version"]),
        ):
            version_process = run_process(command, root, env, name + " version", report["processes"])
            versions[name] = version_process.stdout.strip()
        versions["python"] = sys.version.split()[0]
        if versions["pnpm"] != package_manager.split("@", 1)[1]:
            raise CheckError("Installed pnpm does not match root packageManager %s" % package_manager)

        with tempfile.TemporaryDirectory(prefix="armstrong-r53-t044-") as temporary:
            temporary_root = Path(temporary)
            before = run_variant(
                root, exercise, files, package, cases, before_reference, "before", temporary_root, env, report
            )
            after = run_variant(
                root, exercise, files, package, cases, after_reference, "after", temporary_root, env, report
            )

        before_outputs = before["outputs"]
        after_outputs = after["outputs"]
        if before_outputs != after_outputs:
            raise CheckError("Before/after actual outputs differ")
        if before["test_statuses"] != after["test_statuses"]:
            raise CheckError("Before/after test results differ")

        traces_by_name = {
            "Zero is an Armstrong number",
            "Single-digit numbers are Armstrong numbers",
            "There are no two-digit Armstrong numbers",
        }
        trace_inputs = [case for case in cases if case["name"] in traces_by_name]
        traces = [arithmetic_trace(case["input"]) for case in trace_inputs]
        if len(traces) != 3:
            raise CheckError("Could not prepare all three requested arithmetic traces")
        for trace in traces:
            output = next(item["actual"] for item in after_outputs if item["input"] == trace["input"])
            if output != trace["is_armstrong"]:
                raise CheckError("Arithmetic trace disagrees with actual output for %s" % trace["input"])

        learner_hash_after = sha256(learner_path)
        spec_hash_after = sha256(spec_path)
        reference_hash_after = sha256(after_reference)
        if learner_hash_after != learner_hash_before:
            raise CheckError("Learner solution changed during reference verification")
        if spec_hash_after != spec_hash_before:
            raise CheckError("Canonical exercise tests changed during verification")
        if reference_hash_after != reference_hash_after_before_check:
            raise CheckError("Working-tree reference changed during verification")

        report["inputs"] = {
            "exercise_config": str(config_path.relative_to(root)),
            "configured_paths": {
                kind: [relative.as_posix() for relative, _ in values]
                for kind, values in files.items()
            },
            "test_script": package.get("scripts", {}).get("test"),
            "canonical_case_count": len(cases),
            "enabled_before_track_promotion": enabled_count,
            "cases": cases,
            "requested_traces": traces,
            "reference_snapshot": {
                "path": BEFORE_REFERENCE.as_posix(),
                "sha256": before_hash,
            },
        }
        report["before"] = before
        report["after"] = after
        report["comparison"] = {
            "actual_outputs_match_for_every_case": before_outputs == after_outputs,
            "test_statuses_match_for_every_case": before["test_statuses"] == after["test_statuses"],
            "test_count_before": before["test_counts"]["executed"],
            "test_count_after": after["test_counts"]["executed"],
            "learner_hash_unchanged": learner_hash_after == learner_hash_before,
            "spec_hash_unchanged": spec_hash_after == spec_hash_before,
            "reference_hash_unchanged_during_check": reference_hash_after == reference_hash_after_before_check,
            "check_guard_self_tests": guard_results,
        }
        report["processes"] = report["processes"]
        report["tool_versions"] = versions
        report["working_tree_hashes"] = {
            "learner_before": learner_hash_before,
            "learner_after": learner_hash_after,
            "spec_before": spec_hash_before,
            "spec_after": spec_hash_after,
            "reference_before_check": reference_hash_after_before_check,
            "reference_after_check": reference_hash_after,
        }
        report["success"] = True

        (evidence_directory / "inputs.json").write_text(
            json.dumps(report["inputs"], indent=2) + "\n", encoding="utf-8"
        )
        (evidence_directory / "before-results.json").write_text(
            json.dumps(before, indent=2) + "\n", encoding="utf-8"
        )
        (evidence_directory / "after-results.json").write_text(
            json.dumps(after, indent=2) + "\n", encoding="utf-8"
        )
    except Exception as exception:
        error = "%s: %s" % (type(exception).__name__, exception)
        report["error"] = error
    finally:
        try:
            evidence_directory.mkdir(parents=True, exist_ok=True)
            (evidence_directory / "results.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as write_error:
            report["success"] = False
            error = "Could not save evidence: %s" % write_error
        before_counts = report.get("before", {}).get("test_counts", {})
        after_counts = report.get("after", {}).get("test_counts", {})
        print("Armstrong Numbers reference comparison")
        print(
            "Before: %s tests executed, %s passed, %s failed"
            % (before_counts.get("executed", 0), before_counts.get("passed", 0), before_counts.get("failed", 0))
        )
        print(
            "After: %s tests executed, %s passed, %s failed"
            % (after_counts.get("executed", 0), after_counts.get("passed", 0), after_counts.get("failed", 0))
        )
        for trace in report.get("inputs", {}).get("requested_traces", []):
            print("%s: input %s -> %s" % (trace["input"], trace["digits"], trace["sum"]))
        print("Before/after outputs match: %s" % report.get("comparison", {}).get("actual_outputs_match_for_every_case", False))
        print("Evidence: work/R53-T044/results.json")
        if report["success"]:
            print("Result: PASS")
        else:
            print("Result: FAIL" + (" (%s)" % error if error else ""), file=sys.stderr)
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())