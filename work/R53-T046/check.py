#!/usr/bin/env python3
"""Automated validation script for R53-T046 — Eliud's Eggs Approach Comparison.

This script independently validates both the maintained reference implementation
and an alternative numeric bitwise implementation against the canonical exercise
test suite in isolated temporary directories without modifying the learner's
solution or the working tree.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/eliuds-eggs")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
REQUIRED_NAMED_CASES = ["0 eggs", "1 egg", "4 eggs"]

TEST_DECLARATION = re.compile(
    r"(?P<flag>x?test)\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*\(\)\s*=>\s*\{"
    r"\s*const\s+expected\s*=\s*(?P<expected>\d+)\s*;\s*"
    r"const\s+actual\s*=\s*eggCount\((?P<input>\d+)\)\s*;\s*"
    r"expect\(actual\)\.toEqual\(expected\);\s*\}\);",
    re.MULTILINE,
)


class CheckError(Exception):
    """Raised when any assertion or verification check fails."""
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
    raise CheckError("Could not locate repository root")


def sha256(path):
    """Compute the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_process(command, cwd, env, label, processes_log):
    """Run an external process with error checking and log recording."""
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
            f"{label} exited with {result.returncode}\nStdout:\n{result.stdout}\nStderr:\n{result.stderr}"
        )
    return result


def resolve_files(exercise, config):
    """Resolve and validate solution, test, and example file paths from config.json."""
    file_config = config.get("files")
    if not isinstance(file_config, dict):
        raise CheckError("Exercise config is missing its files object")

    resolved = {}
    for kind in ("solution", "test", "example"):
        names = file_config.get(kind)
        if not isinstance(names, list) or not names:
            raise CheckError(f"Config files.{kind} must be a non-empty list")
        resolved[kind] = []
        for name in names:
            if not isinstance(name, str) or not name:
                raise CheckError(f"Invalid configured {kind} path")
            relative = Path(name.replace("%{kebab_slug}", "eliuds-eggs"))
            source = (exercise / relative).resolve()
            if not source.is_relative_to(exercise.resolve()):
                raise CheckError(f"Configured path escapes the exercise directory: {name}")
            if not source.is_file():
                raise CheckError(f"Configured {kind} file is missing: {source}")
            resolved[kind].append((relative, source))
    return resolved


def parse_cases(spec_source):
    """Extract structured test cases from the exercise specification file."""
    cases = []
    for match in TEST_DECLARATION.finditer(spec_source):
        name = match.group("name")
        flag = match.group("flag")
        input_val = int(match.group("input"))
        expected_val = int(match.group("expected"))

        cases.append(
            {
                "name": name,
                "input": input_val,
                "expected": expected_val,
                "binary_representation": bin(input_val)[2:],
                "bit_length": len(bin(input_val)[2:]) if input_val > 0 else 1,
                "enabled_in_learner_suite": flag == "test",
            }
        )

    if not cases:
        raise CheckError("No test cases could be parsed from eliuds-eggs.spec.js")

    names = [case["name"] for case in cases]
    if len(names) != len(set(names)):
        raise CheckError("Duplicate test names found in eliuds-eggs.spec.js")

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
        {"numTotalTests": 4, "numPassedTests": 3, "numFailedTests": 1},
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


def clone_exercise(source_exercise, destination, implementation_file, files):
    """Create an isolated temporary copy of the exercise with a specific implementation."""
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

    # Substitute implementation ONLY in the temporary copy
    for relative, _ in files["solution"]:
        shutil.copy2(implementation_file, destination / relative)

    # Enable all test cases in the temporary copy
    for relative, _ in files["test"]:
        copied_test = destination / relative
        modified = enable_all_tests(copied_test.read_text(encoding="utf-8"))
        copied_test.write_text(modified, encoding="utf-8")

    return len(copied_files)


def run_test_suite(root, copied_exercise, files, test_script, env, label, processes_log):
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

    process = run_process(cmd, root, env, f"{label} test execution", processes_log)

    if not result_path.is_file():
        raise CheckError(f"{label} failed to write the Jest JSON result file")

    jest_result = json.loads(result_path.read_text(encoding="utf-8"))
    return jest_result, process


def run_probe(root, copied_exercise, cases, env, label, processes_log):
    """Run an isolated Node.js probe to capture actual outputs for each case."""
    probe_script = copied_exercise / "probe-cases.mjs"
    output_path = copied_exercise / "probe-outputs.json"

    probe_code = f"""import fs from 'node:fs';
import {{ eggCount }} from './eliuds-eggs.js';

const cases = {json.dumps(cases)};
const results = [];

for (const c of cases) {{
  const actual = eggCount(c.input);
  results.push({{
    name: c.name,
    input: c.input,
    binary: c.binary_representation,
    expected: c.expected,
    actual: actual,
    match: actual === c.expected
  }});
}}

fs.writeFileSync('{output_path.as_posix()}', JSON.stringify(results, null, 2), 'utf-8');
"""
    probe_script.write_text(probe_code, encoding="utf-8")

    cmd = ["node", str(probe_script)]
    run_process(cmd, root, env, f"{label} probe execution", processes_log)

    if not output_path.is_file():
        raise CheckError(f"{label} probe failed to produce outputs file")

    probe_results = json.loads(output_path.read_text(encoding="utf-8"))
    if len(probe_results) != len(cases):
        raise CheckError(f"{label} probe evaluated {len(probe_results)} cases; expected {len(cases)}")

    for res in probe_results:
        if not res.get("match"):
            raise CheckError(
                f"{label} correctness check failed for '{res['name']}':\n"
                f"Input: {res['input']} (0b{res['binary']})\n"
                f"Expected: {res['expected']}\n"
                f"Actual:   {res['actual']}"
            )

    return probe_results


def main():
    root = find_root()
    exercise = root / ASSIGNMENT
    work_dir = root / "work" / "R53-T046"
    work_dir.mkdir(parents=True, exist_ok=True)

    reference_source = exercise / ".meta" / "proof.ci.js"
    alternative_source = work_dir / "alternative.js"

    evidence_path = work_dir / "evidence.json"
    results_path = work_dir / "results.json"
    inputs_path = work_dir / "inputs.json"

    processes_log = []
    print(f"=== Starting R53-T046 Eliud's Eggs Approach Check ===")
    print(f"Repository root: {root}")
    print(f"Exercise path:   {exercise}")

    # Read and parse exercise config.json
    config_file = root / CONFIG_PATH
    if not config_file.is_file():
        raise CheckError(f"Configuration file missing: {config_file}")
    config = json.loads(config_file.read_text(encoding="utf-8"))

    files = resolve_files(exercise, config)
    learner_path = exercise / files["solution"][0][0]
    spec_path = exercise / files["test"][0][0]

    if not alternative_source.is_file():
        raise CheckError(f"Alternative implementation missing: {alternative_source}")

    # Baseline file hashes
    learner_hash_before = sha256(learner_path)
    spec_hash_before = sha256(spec_path)
    reference_hash_before = sha256(reference_source)

    cases = parse_cases(spec_path.read_text(encoding="utf-8"))
    enabled_count_baseline = sum(case["enabled_in_learner_suite"] for case in cases)
    print(f"Parsed {len(cases)} test cases ({enabled_count_baseline} enabled in learner spec)")

    # Verify result checker guards
    guard_results = verify_result_guards()
    print("Self-test: result guards successfully verified")

    # Inspect package.json
    pkg_file = exercise / "package.json"
    if not pkg_file.is_file():
        raise CheckError(f"Exercise package.json missing: {pkg_file}")
    pkg_json = json.loads(pkg_file.read_text(encoding="utf-8"))
    test_script = pkg_json.get("scripts", {}).get("test")
    if not test_script:
        raise CheckError("Exercise package.json does not declare a test script")

    # Set up child process environment
    env = os.environ.copy()
    node_bin = root / "node_modules" / ".bin"
    env["PATH"] = f"{node_bin}:{env.get('PATH', '')}"
    env["NODE_PATH"] = str(root / "node_modules")
    env["CI"] = "1"

    # Query tool versions
    tool_versions = {
        "node": run_process(["node", "--version"], root, env, "Node version", processes_log).stdout.strip(),
        "corepack": run_process(["corepack", "--version"], root, env, "Corepack version", processes_log).stdout.strip(),
        "pnpm": run_process(["corepack", "pnpm", "--version"], root, env, "pnpm version", processes_log).stdout.strip(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    print(f"Tools: Node {tool_versions['node']}, pnpm {tool_versions['pnpm']}, Python {tool_versions['python']}")

    # 1. Test Reference Implementation in isolated temp dir
    with tempfile.TemporaryDirectory() as temp_root_ref:
        temp_dir_ref = Path(temp_root_ref) / "eliuds-eggs"
        clone_exercise(exercise, temp_dir_ref, reference_source, files)
        jest_raw_ref, _ = run_test_suite(
            root, temp_dir_ref, files, test_script, env, "Reference", processes_log
        )
        counts_ref = validate_jest_result(jest_raw_ref, len(cases), "Reference test suite")
        probe_ref = run_probe(root, temp_dir_ref, cases, env, "Reference", processes_log)
        print(f"Reference implementation: {counts_ref['passed']}/{counts_ref['total']} tests passed")

    # 2. Test Alternative Implementation in isolated temp dir
    with tempfile.TemporaryDirectory() as temp_root_alt:
        temp_dir_alt = Path(temp_root_alt) / "eliuds-eggs"
        clone_exercise(exercise, temp_dir_alt, alternative_source, files)
        jest_raw_alt, _ = run_test_suite(
            root, temp_dir_alt, files, test_script, env, "Alternative", processes_log
        )
        counts_alt = validate_jest_result(jest_raw_alt, len(cases), "Alternative test suite")
        probe_alt = run_probe(root, temp_dir_alt, cases, env, "Alternative", processes_log)
        print(f"Alternative implementation: {counts_alt['passed']}/{counts_alt['total']} tests passed")

    # Verify working tree was never modified
    learner_hash_after = sha256(learner_path)
    spec_hash_after = sha256(spec_path)
    reference_hash_after = sha256(reference_source)

    if learner_hash_after != learner_hash_before:
        raise CheckError("CRITICAL: Original learner solution file was modified!")
    if spec_hash_after != spec_hash_before:
        raise CheckError("CRITICAL: Original exercise spec file was modified!")
    if reference_hash_after != reference_hash_before:
        raise CheckError("CRITICAL: Original reference implementation file was modified!")

    print("Working tree verification: learner stub and spec files are strictly unchanged")

    # Verify required named cases on both implementations
    required_results = {}
    probe_ref_by_name = {res["name"]: res for res in probe_ref}
    probe_alt_by_name = {res["name"]: res for res in probe_alt}

    for req in REQUIRED_NAMED_CASES:
        if req not in probe_ref_by_name or req not in probe_alt_by_name:
            raise CheckError(f"Required named test case '{req}' missing from probe results")

        item_ref = probe_ref_by_name[req]
        item_alt = probe_alt_by_name[req]

        if not item_ref["match"] or not item_alt["match"]:
            raise CheckError(f"Required named test case '{req}' failed correctness check")

        required_results[req] = {
            "input": item_ref["input"],
            "binary": item_ref["binary"],
            "expected": item_ref["expected"],
            "reference_actual": item_ref["actual"],
            "alternative_actual": item_alt["actual"],
            "match": True,
        }
        print(f"Required case verified: '{req}' (input: {item_ref['input']}) -> PASS (ref: {item_ref['actual']}, alt: {item_alt['actual']})")

    # Save inputs.json
    inputs_data = {
        "exercise": "eliuds-eggs",
        "total_cases": len(cases),
        "cases": cases,
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    # Save results.json
    results_data = {
        "exercise": "eliuds-eggs",
        "reference": {
            "name": "Binary String & Array Reduce",
            "test_counts": counts_ref,
            "cases": probe_ref,
        },
        "alternative": {
            "name": "32-bit Numeric Bitwise Masking & Shift",
            "test_counts": counts_alt,
            "cases": probe_alt,
        },
        "required_named_cases": required_results,
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    # Save evidence.json
    evidence_data = {
        "task": "R53-T046",
        "exercise": "eliuds-eggs",
        "timestamp_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
        "tool_versions": tool_versions,
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
            "reference_executed": counts_ref["total"],
            "reference_passed": counts_ref["passed"],
            "reference_failed": counts_ref["failed"],
            "alternative_executed": counts_alt["total"],
            "alternative_passed": counts_alt["passed"],
            "alternative_failed": counts_alt["failed"],
        },
        "required_named_cases": required_results,
        "guard_verification": guard_results,
        "subprocess_count": len(processes_log),
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    # Summary table
    print("\n" + "=" * 80)
    print(f"{'Case Name':<15} | {'Input':<12} | {'Binary':<35} | {'Exp':<4} | {'Ref':<4} | {'Alt':<4} | Status")
    print("-" * 80)
    for c in cases:
        name = c["name"]
        ref_act = probe_ref_by_name[name]["actual"]
        alt_act = probe_alt_by_name[name]["actual"]
        print(f"{name:<15} | {c['input']:<12} | 0b{c['binary_representation']:<33} | {c['expected']:<4} | {ref_act:<4} | {alt_act:<4} | PASS")
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

