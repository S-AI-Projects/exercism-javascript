#!/usr/bin/env python3
"""Automated verification script for R53-T050 — Nucleotide Count Guidance & Checks.

Independently reproduces the selected test cases against the maintained reference
implementation in an isolated temporary directory, executes the full exercise
test suite via the official package manager, verifies guards against zero-test
runs and assertion failures, checks file immutability, and records audit evidence.
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


ASSIGNMENT = Path("exercises/practice/nucleotide-count")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"

SELECTED_TEST_CASES = [
    {
        "name": "empty strand",
        "input": "",
        "expected": "0 0 0 0",
        "description": "Empty DNA sequence contains 0 A, 0 C, 0 G, 0 T",
    },
    {
        "name": "can count one nucleotide in single-character input",
        "input": "G",
        "expected": "0 0 1 0",
        "description": "Single G nucleotide maps to 0 A, 0 C, 1 G, 0 T in strict A-C-G-T order",
    },
    {
        "name": "strand with repeated nucleotide",
        "input": "GGGGGGG",
        "expected": "0 0 7 0",
        "description": "Seven G nucleotides map to 0 A, 0 C, 7 G, 0 T in strict A-C-G-T order",
    },
]

ALL_SPEC_CASES = [
    {
        "name": "empty strand",
        "input": "",
        "expected": "0 0 0 0",
        "expected_error": None,
        "is_error_case": False,
    },
    {
        "name": "can count one nucleotide in single-character input",
        "input": "G",
        "expected": "0 0 1 0",
        "expected_error": None,
        "is_error_case": False,
    },
    {
        "name": "strand with repeated nucleotide",
        "input": "GGGGGGG",
        "expected": "0 0 7 0",
        "expected_error": None,
        "is_error_case": False,
    },
    {
        "name": "strand with multiple nucleotides",
        "input": "AGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGGATTAAAAAAAGAGTGTCTGATAGCAGC",
        "expected": "20 12 17 21",
        "expected_error": None,
        "is_error_case": False,
    },
    {
        "name": "strand with invalid nucleotides",
        "input": "AGXXACT",
        "expected": None,
        "expected_error": "Invalid nucleotide in strand",
        "is_error_case": True,
    },
]


class CheckError(Exception):
    """Raised when any verification assertion fails."""
    pass


def find_root():
    """Locate repository root directory."""
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / CONFIG_PATH).is_file()
        ):
            return candidate
    raise CheckError("Could not locate repository root directory")


def sha256_file(path):
    """Compute SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_package_manager(root):
    """Detect package manager from lockfile and package.json."""
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "package-lock.json").is_file():
        return "npm"
    raise CheckError("No known lockfile found in repository root")


def resolve_files(exercise_dir, config_path):
    """Resolve and validate solution, test, and example file paths from config.json."""
    if not config_path.is_file():
        raise CheckError(f"Exercise config.json not found: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise CheckError(f"Malformed config.json: {err}")

    files_obj = config.get("files")
    if not isinstance(files_obj, dict):
        raise CheckError("Missing or non-object 'files' in config.json")

    resolved = {}
    exercise_root = exercise_dir.resolve()

    for kind in ("solution", "test", "example"):
        declared = files_obj.get(kind)
        if not isinstance(declared, list) or not declared:
            raise CheckError(f"Config category 'files.{kind}' must be a non-empty list")
        resolved[kind] = []
        for entry in declared:
            if not isinstance(entry, str) or not entry.strip():
                raise CheckError(f"Invalid entry in 'files.{kind}'")
            rel_path = Path(entry.replace("%{kebab_slug}", exercise_dir.name))
            abs_path = (exercise_dir / rel_path).resolve()
            if not abs_path.is_relative_to(exercise_root):
                raise CheckError(f"Path '{entry}' escapes exercise root directory")
            if not abs_path.is_file():
                raise CheckError(f"Declared file '{entry}' in 'files.{kind}' does not exist: {abs_path}")
            resolved[kind].append((rel_path, abs_path))

    return resolved


def enable_all_tests(source_text):
    """Promote xtest and xit to test and it, and xdescribe to describe."""
    text = re.sub(r"\bx(test|it)\(", "test(", source_text)
    return re.sub(r"\bxdescribe\(", "describe(", text)


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
        {"numTotalTests": 5, "numPassedTests": 4, "numFailedTests": 1},
        {"numTotalTests": None, "numPassedTests": 0, "numFailedTests": 0},
        {"numTotalTests": 5, "numPassedTests": 0, "numFailedTests": 5},
    ]
    for result in invalid_results:
        try:
            validate_jest_result(result, 5, "checker guard self-test")
        except CheckError:
            continue
        raise CheckError(f"Checker guard failed to reject invalid Jest result: {result}")
    return {
        "zero_tests_rejected": True,
        "assertion_failure_rejected": True,
        "missing_test_count_rejected": True,
    }


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


def run_exercise_probe(copied_exercise, env, processes_log):
    """Run an isolated Node probe to evaluate every test case against the substituted reference."""
    probe_script = copied_exercise / "probe-cases.mjs"
    output_path = copied_exercise / "probe-outputs.json"

    probe_code = f"""import fs from 'node:fs';
import {{ countNucleotides }} from './nucleotide-count.js';

const cases = {json.dumps(ALL_SPEC_CASES)};
const results = [];

for (const c of cases) {{
  let actual = null;
  let error = null;
  let match = false;
  try {{
    actual = countNucleotides(c.input);
    match = actual === c.expected;
  }} catch (err) {{
    error = err.message;
    match = error === c.expected_error;
  }}
  results.push({{
    name: c.name,
    input: c.input,
    expected: c.expected,
    expected_error: c.expected_error,
    is_error_case: c.is_error_case,
    actual,
    error,
    match
  }});
}}

fs.writeFileSync('{output_path.as_posix()}', JSON.stringify(results, null, 2), 'utf-8');
"""
    probe_script.write_text(probe_code, encoding="utf-8")

    cmd = ["node", str(probe_script)]
    run_process(cmd, copied_exercise, env, "Nucleotide Count cases probe execution", processes_log)

    if not output_path.is_file():
        raise CheckError("Nucleotide Count probe failed to produce outputs file")

    probe_results = json.loads(output_path.read_text(encoding="utf-8"))
    if len(probe_results) != len(ALL_SPEC_CASES):
        raise CheckError(f"Probe evaluated {len(probe_results)} cases; expected {len(ALL_SPEC_CASES)}")

    for res in probe_results:
        if not res.get("match"):
            raise CheckError(
                f"Assertion failed for case '{res['name']}':\n"
                f"Input:          {res['input']}\n"
                f"Expected:       {res['expected']}\n"
                f"Expected Error: {res['expected_error']}\n"
                f"Actual:         {res['actual']}\n"
                f"Actual Error:   {res['error']}"
            )

    return probe_results


def clone_and_configure_exercise(source_exercise, destination, reference_file, files):
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

    # Substitute reference implementation ONLY inside temporary copy
    for relative, _ in files["solution"]:
        shutil.copy2(reference_file, destination / relative)

    # Enable all tests in temporary copy
    for relative, _ in files["test"]:
        copied_test = destination / relative
        modified = enable_all_tests(copied_test.read_text(encoding="utf-8"))
        copied_test.write_text(modified, encoding="utf-8")

    return len(copied_files)


def run_jest_suite(root, copied_exercise, files, env, processes_log):
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

    process = run_process(cmd, root, env, "Nucleotide Count Jest execution", processes_log)

    if not result_path.is_file():
        raise CheckError("Jest execution failed to write JSON result file")

    jest_result = json.loads(result_path.read_text(encoding="utf-8"))
    return jest_result, process


def main():
    root = find_root()
    exercise = root / ASSIGNMENT
    work_dir = root / "work" / "R53-T050"
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs_path = work_dir / "inputs.json"
    results_path = work_dir / "results.json"
    evidence_path = work_dir / "evidence.json"
    tools_txt_path = work_dir / "tool-versions.txt"

    processes_log = []
    print("=== Starting R53-T050 Nucleotide Count Automated Checker ===")
    print(f"Repository Root:    {root}")
    print(f"Exercise Directory: {exercise}")

    # 1. Detect package manager from lockfile
    package_manager = detect_package_manager(root)
    print(f"Detected package manager from lockfile: {package_manager}")

    # 2. Read and parse exercise config.json
    config_file = root / CONFIG_PATH
    files = resolve_files(exercise, config_file)

    learner_path = files["solution"][0][1]
    spec_path = files["test"][0][1]
    reference_path = files["example"][0][1]

    print("Resolved files from config.json:")
    print(f"  - Solution (learner stub): {files['solution'][0][0]} -> {learner_path}")
    print(f"  - Test spec:              {files['test'][0][0]} -> {spec_path}")
    print(f"  - Example (reference):    {files['example'][0][0]} -> {reference_path}")

    # Baseline file hashes
    learner_hash_before = sha256_file(learner_path)
    spec_hash_before = sha256_file(spec_path)
    reference_hash_before = sha256_file(reference_path)

    # 3. Verify guard logic self-tests
    guard_results = verify_result_guards()
    print("Self-test: execution guards successfully verified (zero tests, failure detection).")

    # 4. Prepare environment and query tool versions
    env = os.environ.copy()
    node_bin = str(root / "node_modules" / ".bin")
    env["PATH"] = node_bin + ":" + env.get("PATH", "")
    env["NODE_PATH"] = str(root / "node_modules")
    env["CI"] = "1"

    node_version = run_process(["node", "--version"], root, env, "Node version", processes_log).stdout.strip()
    corepack_version = run_process(["corepack", "--version"], root, env, "Corepack version", processes_log).stdout.strip()
    pnpm_version = run_process(["corepack", "pnpm", "--version"], root, env, "pnpm version", processes_log).stdout.strip()
    jest_raw = run_process(["corepack", "pnpm", "jest", "--version"], root, env, "Jest version", processes_log).stdout.strip()
    jest_version = jest_raw.splitlines()[-1] if jest_raw else "unknown"
    python_version = platform.python_version()

    tool_versions = {
        "python": python_version,
        "node": node_version,
        "corepack": corepack_version,
        "pnpm": pnpm_version,
        "package_manager": package_manager,
        "jest": jest_version,
        "platform": platform.platform(),
    }
    print(f"Tool versions: Python {python_version}, Node {node_version}, pnpm {pnpm_version}, Jest {jest_version}")

    tools_txt_path.write_text(
        f"Python: {python_version}\n"
        f"Node.js: {node_version}\n"
        f"Package Manager: pnpm {pnpm_version} (via Corepack {corepack_version})\n"
        f"Test Runner: Jest {jest_version}\n"
        f"Platform: {platform.platform()}\n",
        encoding="utf-8",
    )

    # 5. Clone exercise to temporary directory and run Jest
    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root) / "nucleotide-count"
        cloned_count = clone_and_configure_exercise(exercise, temp_dir, reference_path, files)
        print(f"Cloned {cloned_count} files into isolated directory: {temp_dir}")

        jest_raw_res, _ = run_jest_suite(root, temp_dir, files, env, processes_log)
        counts = validate_jest_result(jest_raw_res, len(ALL_SPEC_CASES), "Nucleotide Count test suite")
        print(f"Jest test execution: {counts['passed']}/{counts['total']} tests passed (0 failed)")

        probe_outputs = run_exercise_probe(temp_dir, env, processes_log)
        print(f"Direct probe execution: {len(probe_outputs)}/{len(ALL_SPEC_CASES)} cases evaluated and verified")

    # 6. Verify working tree files remain strictly unmodified
    learner_hash_after = sha256_file(learner_path)
    spec_hash_after = sha256_file(spec_path)
    reference_hash_after = sha256_file(reference_path)

    if learner_hash_after != learner_hash_before:
        raise CheckError("CRITICAL: Original learner solution file was modified in working tree!")
    if spec_hash_after != spec_hash_before:
        raise CheckError("CRITICAL: Original exercise test spec file was modified in working tree!")
    if reference_hash_after != reference_hash_before:
        raise CheckError("CRITICAL: Original reference implementation file was modified in working tree!")

    print("Working tree verification: learner stub, spec, and reference files are strictly unchanged")

    # 7. Verify selected required test cases
    probe_by_name = {res["name"]: res for res in probe_outputs}
    selected_verification_records = {}
    for sel in SELECTED_TEST_CASES:
        name = sel["name"]
        if name not in probe_by_name:
            raise CheckError(f"Required selected case '{name}' missing from probe results")
        item = probe_by_name[name]
        if not item["match"]:
            raise CheckError(f"Required selected case '{name}' failed correctness check")
        selected_verification_records[name] = {
            "name": name,
            "input": sel["input"],
            "expected": sel["expected"],
            "actual": item["actual"],
            "description": sel["description"],
            "match": item["match"],
        }
        print(f"[PASS] Selected case verified: '{name}' -> input: '{sel['input']}', output: '{item['actual']}'")

    # 8. Save inputs.json
    inputs_data = {
        "exercise": "nucleotide-count",
        "selected_test_cases": SELECTED_TEST_CASES,
        "all_spec_test_cases": ALL_SPEC_CASES,
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    # 9. Save results.json
    results_data = {
        "exercise": "nucleotide-count",
        "tool_versions": tool_versions,
        "test_counts": counts,
        "selected_test_cases": selected_verification_records,
        "all_cases": probe_outputs,
        "working_tree_immutability": {
            "learner_stub_sha256": learner_hash_after,
            "learner_stub_unchanged": learner_hash_after == learner_hash_before,
            "spec_sha256": spec_hash_after,
            "spec_unchanged": spec_hash_after == spec_hash_before,
            "reference_sha256": reference_hash_after,
            "reference_unchanged": reference_hash_after == reference_hash_before,
        },
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    # 10. Save evidence.json
    evidence_data = {
        "task": "R53-T050",
        "exercise": "nucleotide-count",
        "timestamp_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
        "tool_versions": tool_versions,
        "test_execution": {
            "test_script": "corepack pnpm jest",
            "total_cases_in_spec": len(ALL_SPEC_CASES),
            "executed": counts["total"],
            "passed": counts["passed"],
            "failed": counts["failed"],
        },
        "selected_test_cases": selected_verification_records,
        "guard_verification": guard_results,
        "file_hashes": {
            "learner_stub_sha256": learner_hash_after,
            "reference_implementation_sha256": reference_hash_after,
            "test_spec_sha256": spec_hash_after,
            "learner_stub_unchanged": learner_hash_after == learner_hash_before,
            "reference_unchanged": reference_hash_after == reference_hash_before,
        },
        "subprocess_count": len(processes_log),
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    # 11. Print Summary
    print("\n" + "=" * 80)
    print("SUMMARY OF VERIFICATION — R53-T050")
    print("=" * 80)
    print("Nucleotide Count Test Suite Execution:")
    print(f"  - Executed Tests:        {counts['total']}")
    print(f"  - Passed:                {counts['passed']}")
    print(f"  - Failed:                {counts['failed']}")
    print("  - Test Status:           ALL PASS")
    print("\nSelected Key Cases:")
    for name, rec in selected_verification_records.items():
        print(f"  - '{name}':")
        print(f"      Input:    '{rec['input']}'")
        print(f"      Expected: '{rec['expected']}'")
        print(f"      Actual:   '{rec['actual']}'")
        print(f"      Status:   PASS")
    print("\nWorking Tree Immutability:")
    print(f"  - Learner stub unchanged:       {learner_hash_after == learner_hash_before}")
    print(f"  - Spec file unchanged:          {spec_hash_after == spec_hash_before}")
    print(f"  - Reference impl unchanged:     {reference_hash_after == reference_hash_before}")
    print("=" * 80)

    print(f"\nArtifacts successfully written to {work_dir}:")
    print(f" - {inputs_path.relative_to(root)}")
    print(f" - {results_path.relative_to(root)}")
    print(f" - {evidence_path.relative_to(root)}")
    print(f" - {tools_txt_path.relative_to(root)}")
    print("=== Verification completed successfully ===")


if __name__ == "__main__":
    try:
        main()
    except CheckError as err:
        print(f"\nVALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(1)

