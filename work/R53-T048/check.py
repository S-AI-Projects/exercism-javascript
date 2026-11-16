#!/usr/bin/env python3
"""Automated verification script for R53-T048 — Poker Exercise Metadata Validation.

This script independently validates the Poker exercise metadata and its declared
solution, test, and example paths, runs the reference implementation against
the canonical test suite in an isolated temporary directory, verifies all 37 test
cases and the 3 required named cases, validates the 3 invalid metadata fixtures,
and records comprehensive audit evidence without modifying the working tree.
"""

import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/poker")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
REQUIRED_NAMED_CASES = [
    "single hand always wins",
    "highest card out of all hands wins",
    "a tie has multiple winners",
]


class CheckError(Exception):
    """Raised when any assertion or validation check fails."""
    pass


def find_root():
    """Locate the repository root directory."""
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / CONFIG_PATH).is_file()
        ):
            return candidate
    raise CheckError("Could not locate repository root directory")


def sha256(path):
    """Compute the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_process(command, cwd, env, label, processes_log):
    """Run an external process with return-code verification and log recording."""
    result = subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd),
        env=env,
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
    processes_log.append(record)
    if result.returncode != 0:
        raise CheckError(
            f"{label} exited with status {result.returncode}\n"
            f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}"
        )
    return result


def detect_package_manager(root):
    """Detect package manager from lockfile and package.json."""
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "package-lock.json").is_file():
        return "npm"
    raise CheckError("No known lockfile found in repository root")


def resolve_files(exercise, config):
    """Resolve and validate solution, test, and example file paths from config.json."""
    file_config = config.get("files")
    if not isinstance(file_config, dict):
        raise CheckError("Exercise config is missing its 'files' object")

    resolved = {}
    for kind in ("solution", "test", "example"):
        names = file_config.get(kind)
        if not isinstance(names, list) or not names:
            raise CheckError(f"Config files.{kind} must be a non-empty list")
        resolved[kind] = []
        for name in names:
            if not isinstance(name, str) or not name:
                raise CheckError(f"Invalid configured {kind} path")
            relative = Path(name.replace("%{kebab_slug}", "poker"))
            source = (exercise / relative).resolve()
            if not source.is_relative_to(exercise.resolve()):
                raise CheckError(f"Configured path escapes the exercise directory: {name}")
            if not source.is_file():
                raise CheckError(f"Configured {kind} file is missing: {source}")
            resolved[kind].append((relative, source))
    return resolved


def clean_json_array(raw_text):
    """Convert JavaScript single-quoted array literal to valid JSON."""
    s = re.sub(r"'([^']*)'", r'"\1"', raw_text)
    s = re.sub(r",\s*\]", "]", s)
    return json.loads(s)


def parse_cases(spec_source):
    """Extract structured test cases from poker.spec.js."""
    cases = []
    pattern = re.compile(
        r"(?P<flag>x?test)\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*\(\)\s*=>\s*\{"
        r"\s*const\s+hands\s*=\s*(?P<hands>\[.*?\]);\s*"
        r"const\s+expected\s*=\s*(?P<expected>\[.*?\]);\s*"
        r"expect\(bestHands\(hands\)\)\.toEqual\(expected\);\s*\}\);",
        re.DOTALL,
    )

    for m in pattern.finditer(spec_source):
        hands = clean_json_array(m.group("hands"))
        expected = clean_json_array(m.group("expected"))
        cases.append(
            {
                "name": m.group("name"),
                "input": hands,
                "expected": expected,
                "enabled_in_learner_suite": m.group("flag") == "test",
            }
        )

    if not cases:
        raise CheckError("No test cases could be parsed from poker.spec.js")

    names = [c["name"] for c in cases]
    if len(names) != len(set(names)):
        raise CheckError("Duplicate test names found in poker.spec.js")

    return cases


def enable_all_tests(source):
    """Enable all skipped tests by replacing xtest and xdescribe with test and describe."""
    source = re.sub(r"\bx(test|it)\(", "test(", source)
    return re.sub(r"\bxdescribe\(", "describe(", source)


def validate_jest_result(result, expected_count, label):
    """Verify Jest test execution counts and assertion results."""
    if not isinstance(result, dict):
        raise CheckError(f"{label} produced no parseable Jest JSON result")

    counts = [result.get(k) for k in ("numTotalTests", "numPassedTests", "numFailedTests")]
    if not all(isinstance(v, int) for v in counts):
        raise CheckError(f"{label} Jest JSON omitted valid integer test counts")

    total, passed, failed = counts
    if total == 0:
        raise CheckError(f"{label} executed zero tests (guard triggered)")
    if total != expected_count:
        raise CheckError(f"{label} executed {total} tests; expected exactly {expected_count}")
    if failed != 0 or passed != total:
        raise CheckError(f"{label} had {failed} failed assertions ({passed} passed)")

    return {"total": total, "passed": passed, "failed": failed}


def verify_result_guards():
    """Verify that validate_jest_result properly rejects invalid execution results."""
    invalid_results = [
        {"numTotalTests": 0, "numPassedTests": 0, "numFailedTests": 0},
        {"numTotalTests": 1, "numPassedTests": 0, "numFailedTests": 1},
        {"numTotalTests": None, "numPassedTests": 0, "numFailedTests": 0},
        {"numTotalTests": 37, "numPassedTests": 36, "numFailedTests": 1},
    ]
    for result in invalid_results:
        try:
            validate_jest_result(result, 1, "checker guard self-test")
        except CheckError:
            continue
        raise CheckError(f"Checker guard failed to reject invalid Jest result: {result}")
    return {
        "zero_tests_rejected": True,
        "assertion_failure_rejected": True,
        "missing_test_count_rejected": True,
    }


def clone_exercise(source_exercise, destination, reference_file, files):
    """Create an isolated temporary copy of the exercise with reference solution."""
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
        raise CheckError("Temporary exercise copy failed to include all files")

    # Substitute reference implementation ONLY in temporary copy
    for relative, _ in files["solution"]:
        shutil.copy2(reference_file, destination / relative)

    # Enable all tests in temporary copy
    for relative, _ in files["test"]:
        copied_test = destination / relative
        modified = enable_all_tests(copied_test.read_text(encoding="utf-8"))
        copied_test.write_text(modified, encoding="utf-8")

    return len(copied_files)


def run_test_suite(root, copied_exercise, files, test_script, env, processes_log):
    """Execute the Jest test suite using the exercise package.json script."""
    result_path = copied_exercise / "jest-test-result.json"
    test_paths = [relative.as_posix() for relative, _ in files["test"]]

    cmd = [
        "corepack",
        "pnpm",
        "--dir",
        str(copied_exercise),
        "run",
        "test",
        "--runInBand",
        "--watch=false",
        "--runTestsByPath",
        *test_paths,
        "--json",
        "--outputFile",
        str(result_path),
    ]

    process = run_process(cmd, root, env, "Poker Jest execution", processes_log)

    if not result_path.is_file():
        raise CheckError("Jest execution failed to write JSON result file")

    jest_result = json.loads(result_path.read_text(encoding="utf-8"))
    return jest_result, process


def run_exercise_probe(root, copied_exercise, cases, env, processes_log):
    """Run an isolated Node probe to verify actual outputs for all cases."""
    probe_script = copied_exercise / "probe-cases.mjs"
    output_path = copied_exercise / "probe-outputs.json"

    probe_code = f"""import fs from 'node:fs';
import {{ bestHands }} from './poker.js';

const cases = {json.dumps(cases)};
const results = [];

for (const c of cases) {{
  const actual = bestHands(c.input);
  results.push({{
    name: c.name,
    input: c.input,
    expected: c.expected,
    actual: actual,
    match: JSON.stringify(actual) === JSON.stringify(c.expected)
  }});
}}

fs.writeFileSync('{output_path.as_posix()}', JSON.stringify(results, null, 2), 'utf-8');
"""
    probe_script.write_text(probe_code, encoding="utf-8")

    cmd = ["node", str(probe_script)]
    run_process(cmd, copied_exercise, env, "Poker cases probe execution", processes_log)

    if not output_path.is_file():
        raise CheckError("Poker cases probe failed to produce outputs file")

    probe_results = json.loads(output_path.read_text(encoding="utf-8"))
    if len(probe_results) != len(cases):
        raise CheckError(f"Probe evaluated {len(probe_results)} cases; expected {len(cases)}")

    for res in probe_results:
        if not res.get("match"):
            raise CheckError(
                f"Assertion failed for case '{res['name']}':\n"
                f"Input:    {res['input']}\n"
                f"Expected: {res['expected']}\n"
                f"Actual:   {res['actual']}"
            )

    return probe_results


def load_checker_module(checker_path):
    """Dynamically load tools/course_checks/r53-t048.py module."""
    if not checker_path.is_file():
        raise CheckError(f"Course checker script missing at {checker_path}")
    spec = importlib.util.spec_from_file_location("course_check_r53_t048", checker_path)
    if spec is None or spec.loader is None:
        raise CheckError(f"Cannot load module spec for {checker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    root = find_root()
    exercise = root / ASSIGNMENT
    work_dir = root / "work" / "R53-T048"
    work_dir.mkdir(parents=True, exist_ok=True)

    evidence_path = work_dir / "evidence.json"
    results_path = work_dir / "results.json"
    inputs_path = work_dir / "inputs.json"

    processes_log = []
    print("=== Starting R53-T048 Poker Metadata Checker & Test Runner ===")
    print(f"Repository root:    {root}")
    print(f"Exercise directory: {exercise}")

    # 1. Detect package manager from lockfile
    package_manager = detect_package_manager(root)
    print(f"Detected package manager: {package_manager}")

    # 2. Read and parse exercise config.json
    config_file = root / CONFIG_PATH
    if not config_file.is_file():
        raise CheckError(f"Configuration file missing: {config_file}")
    config = json.loads(config_file.read_text(encoding="utf-8"))

    # Resolve and validate metadata files
    files = resolve_files(exercise, config)
    learner_path = exercise / files["solution"][0][0]
    spec_path = exercise / files["test"][0][0]
    reference_path = exercise / files["example"][0][0]

    print("Resolved metadata files:")
    print(f"  - Solution (learner stub): {files['solution'][0][0]} -> {learner_path}")
    print(f"  - Test spec:              {files['test'][0][0]} -> {spec_path}")
    print(f"  - Example (reference):    {files['example'][0][0]} -> {reference_path}")

    # Baseline file hashes for working tree immutability verification
    learner_hash_before = sha256(learner_path)
    spec_hash_before = sha256(spec_path)
    reference_hash_before = sha256(reference_path)

    # 3. Validate metadata and test invalid fixtures via tools/course_checks/r53-t048.py
    checker_script = root / "tools" / "course_checks" / "r53-t048.py"
    checker_module = load_checker_module(checker_script)

    raw_validation_result = checker_module.validate_file(config_file, exercise)
    # Format resolved files nicely for JSON serialization
    real_validation_result = {
        cat: [{"relative": str(rel), "absolute": str(abs_path)} for rel, abs_path in items]
        for cat, items in raw_validation_result.items()
    }
    print("[PASS] Real config.json validated successfully via r53-t048 checker module")

    fixture_results_list = checker_module.run_fixtures(exercise)
    print(f"[PASS] All {len(fixture_results_list)} invalid metadata fixtures verified and rejected as expected:")
    fixture_results_dict = {}
    for fix in fixture_results_list:
        if not fix["passed"]:
            raise CheckError(f"Fixture check failed for {fix['fixture']}: {fix['actual_error']}")
        print(f"  - {fix['fixture']}: rejected as expected")
        print(f"    Observed Error: {fix['actual_error']}")
        fixture_results_dict[fix["fixture"]] = fix

    # Also verify course checker as standalone executable process
    run_process(
        [sys.executable, str(checker_script)],
        root,
        os.environ.copy(),
        "Standalone r53-t048.py execution",
        processes_log,
    )
    print("[PASS] Standalone tools/course_checks/r53-t048.py process executed cleanly")

    # 4. Parse test cases from poker.spec.js
    cases = parse_cases(spec_path.read_text(encoding="utf-8"))
    enabled_count_baseline = sum(c["enabled_in_learner_suite"] for c in cases)
    print(f"Parsed {len(cases)} test cases from poker.spec.js ({enabled_count_baseline} enabled in learner spec)")

    # Verify result checker guards
    guard_results = verify_result_guards()
    print("Self-test: Jest result guards successfully verified")

    # Inspect package.json
    pkg_file = exercise / "package.json"
    if not pkg_file.is_file():
        raise CheckError(f"Exercise package.json missing: {pkg_file}")
    pkg_json = json.loads(pkg_file.read_text(encoding="utf-8"))
    test_script = pkg_json.get("scripts", {}).get("test")
    if not test_script:
        raise CheckError("Exercise package.json does not declare a test script")

    # Setup child process environment
    env = os.environ.copy()
    node_bin = str(root / "node_modules" / ".bin")
    env["PATH"] = node_bin + ":" + env.get("PATH", "")
    env["NODE_PATH"] = str(root / "node_modules")
    env["CI"] = "1"

    # Query tool versions
    tool_versions = {
        "node": run_process(["node", "--version"], root, env, "Node version", processes_log).stdout.strip(),
        "corepack": run_process(["corepack", "--version"], root, env, "Corepack version", processes_log).stdout.strip(),
        "pnpm": run_process(["corepack", "pnpm", "--version"], root, env, "pnpm version", processes_log).stdout.strip(),
        "package_manager": package_manager,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    print(f"Environment: Node {tool_versions['node']}, {package_manager} {tool_versions['pnpm']}, Python {tool_versions['python']}")

    # 5. Clone exercise to isolated temporary directory and run Jest
    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root) / "poker"
        cloned_count = clone_exercise(exercise, temp_dir, reference_path, files)
        print(f"Cloned {cloned_count} files into isolated directory: {temp_dir}")

        jest_raw, _ = run_test_suite(root, temp_dir, files, test_script, env, processes_log)
        counts = validate_jest_result(jest_raw, len(cases), "Poker test suite")
        print(f"Jest test execution: {counts['passed']}/{counts['total']} tests passed (0 failed)")

        probe_outputs = run_exercise_probe(root, temp_dir, cases, env, processes_log)
        print(f"Direct probe execution: {len(probe_outputs)}/{len(cases)} cases evaluated and verified")

    # 6. Verify working tree was never modified
    learner_hash_after = sha256(learner_path)
    spec_hash_after = sha256(spec_path)
    reference_hash_after = sha256(reference_path)

    if learner_hash_after != learner_hash_before:
        raise CheckError("CRITICAL: Original learner solution file was modified!")
    if spec_hash_after != spec_hash_before:
        raise CheckError("CRITICAL: Original exercise spec file was modified!")
    if reference_hash_after != reference_hash_before:
        raise CheckError("CRITICAL: Original reference implementation file was modified!")

    print("Working tree verification: learner stub, spec, and reference files are strictly unchanged")

    # 7. Verify required named cases
    required_results = {}
    probe_by_name = {res["name"]: res for res in probe_outputs}
    for req in REQUIRED_NAMED_CASES:
        if req not in probe_by_name:
            raise CheckError(f"Required named test case '{req}' missing from probe results")
        item = probe_by_name[req]
        if not item["match"]:
            raise CheckError(f"Required named test case '{req}' failed correctness check")
        required_results[req] = {
            "input": item["input"],
            "expected": item["expected"],
            "actual": item["actual"],
            "match": item["match"],
        }
        print(f"Required case verified: '{req}' -> PASS")

    # 8. Save inputs.json
    inputs_data = {
        "exercise": "poker",
        "metadata_configuration": {
            "files": config["files"],
            "blurb": config.get("blurb"),
            "source": config.get("source"),
            "source_url": config.get("source_url"),
        },
        "invalid_fixtures": {
            fix["fixture"]: {
                "description": fix["description"],
                "expected_error_substring": fix["expected_error_substring"],
            }
            for fix in fixture_results_list
        },
        "total_exercise_cases": len(cases),
        "exercise_cases": cases,
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    # 9. Save results.json
    results_data = {
        "exercise": "poker",
        "metadata_validation": {
            "real_config": {
                "valid": True,
                "resolved_files": real_validation_result,
            },
            "invalid_fixtures": fixture_results_dict,
        },
        "test_counts": counts,
        "required_named_cases": required_results,
        "all_cases": probe_outputs,
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    # 10. Save evidence.json
    evidence_data = {
        "task": "R53-T048",
        "exercise": "poker",
        "timestamp_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
        "tool_versions": tool_versions,
        "metadata_validation": {
            "config_path": str(CONFIG_PATH),
            "files_declared": config["files"],
            "real_config_passed": True,
            "resolved_files": real_validation_result,
            "invalid_fixtures_tested": {
                fix["fixture"]: {
                    "passed_rejection_check": fix["passed"],
                    "observed_error": fix["actual_error"],
                }
                for fix in fixture_results_list
            },
        },
        "file_hashes": {
            "learner_stub_sha256": learner_hash_after,
            "reference_implementation_sha256": reference_hash_after,
            "test_spec_sha256": spec_hash_after,
            "learner_stub_unchanged": learner_hash_after == learner_hash_before,
            "reference_unchanged": reference_hash_after == reference_hash_before,
        },
        "test_execution": {
            "test_script": test_script,
            "total_cases_in_spec": len(cases),
            "executed": counts["total"],
            "passed": counts["passed"],
            "failed": counts["failed"],
        },
        "required_named_cases": required_results,
        "guard_verification": guard_results,
        "subprocess_count": len(processes_log),
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    # 11. Print summary
    print("\n" + "=" * 80)
    print("SUMMARY OF VERIFICATION — R53-T048")
    print("=" * 80)
    print("Metadata Configuration Validation:")
    print("  - Real config.json:      VALID")
    print("  - files.solution:        poker.js -> EXISTS")
    print("  - files.test:            poker.spec.js -> EXISTS")
    print("  - files.example:         .meta/proof.ci.js -> EXISTS")
    print("\nInvalid Metadata Fixture Rejections:")
    for fix in fixture_results_list:
        print(f"  - {fix['fixture']}: REJECTED AS EXPECTED")
        print(f"    Error: {fix['actual_error']}")
    print("\nPoker Test Suite Execution:")
    print(f"  - Executed Tests:        {counts['total']}")
    print(f"  - Passed:                {counts['passed']}")
    print(f"  - Failed:                {counts['failed']}")
    print("  - Test Status:           ALL PASS")
    print("\nRequired Named Test Cases:")
    for req in REQUIRED_NAMED_CASES:
        res = required_results[req]
        print(f"  - '{req}': PASS")
        print(f"      Input:    {res['input']}")
        print(f"      Expected: {res['expected']}")
        print(f"      Actual:   {res['actual']}")
    print("\nWorking Tree Immutability:")
    print(f"  - Learner stub unchanged:       {learner_hash_after == learner_hash_before}")
    print(f"  - Spec file unchanged:          {spec_hash_after == spec_hash_before}")
    print(f"  - Reference impl unchanged:     {reference_hash_after == reference_hash_before}")
    print("=" * 80)

    print(f"\nArtifacts successfully written to {work_dir}:")
    print(f" - {inputs_path.relative_to(root)}")
    print(f" - {results_path.relative_to(root)}")
    print(f" - {evidence_path.relative_to(root)}")
    print("=== Validation completed successfully ===")


if __name__ == "__main__":
    try:
        main()
    except CheckError as err:
        print(f"\nVALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(1)
