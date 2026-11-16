#!/usr/bin/env python3
"""Automated verification script for R53-T047 — Flower Field Language-Specific Hints.

This script independently validates the Flower Field reference implementation
against the canonical test suite in an isolated temporary directory, runs and
asserts the standalone JavaScript micro-example and contrasting pitfall example,
and records comprehensive audit evidence without modifying the working tree.
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


ASSIGNMENT = Path("exercises/practice/flower-field")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
REQUIRED_NAMED_CASES = [
    "handles no rows",
    "handles no columns",
    "handles no flowers",
]

CONSTRUCT_NAME = (
    "Property accessor (bracket notation array indexing) and out-of-bounds falsy evaluation"
)

MICRO_PROBE_CODE = """
const grid = [
  ['A', 'B'],
  ['C', 'D'],
];

// In-bounds row access returns row array (truthy):
const validRow = Boolean(grid[0]);

// Out-of-bounds row access returns undefined (falsy) without throwing:
const outOfBoundsRow = Boolean(grid[-1]);

let contrastingResult;
let errorMessage = null;
try {
  contrastingResult = grid[-1][0];
} catch (err) {
  contrastingResult = err.name;
  errorMessage = err.message;
}

const payload = {
  construct: "Property accessor (bracket notation) & out-of-bounds falsy evaluation",
  micro_example: {
    input_grid: grid,
    in_bounds_access: {
      expression: "Boolean(grid[0])",
      expected: true,
      actual: validRow,
      match: validRow === true
    },
    out_of_bounds_access: {
      expression: "Boolean(grid[-1])",
      expected: false,
      actual: outOfBoundsRow,
      match: outOfBoundsRow === false
    }
  },
  contrasting_example: {
    expression: "grid[-1][0]",
    expected: "TypeError",
    actual: contrastingResult,
    error_message: errorMessage,
    match: contrastingResult === "TypeError"
  }
};

console.log(JSON.stringify(payload, null, 2));
"""


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
            relative = Path(name.replace("%{kebab_slug}", "flower-field"))
            source = (exercise / relative).resolve()
            if not source.is_relative_to(exercise.resolve()):
                raise CheckError(f"Configured path escapes the exercise directory: {name}")
            if not source.is_file():
                raise CheckError(f"Configured {kind} file is missing: {source}")
            resolved[kind].append((relative, source))
    return resolved


def clean_json_array(raw_text):
    """Convert JavaScript array literal to valid JSON."""
    s = re.sub(r"'([^']*)'", r'"\1"', raw_text)
    s = re.sub(r",\s*\]", "]", s)
    return json.loads(s)


def parse_cases(spec_source):
    """Extract structured test cases from flower-field.spec.js."""
    cases = []

    # Pattern 1: expect(annotate(input)).toEqual(expected);
    p1 = re.compile(
        r"(?P<flag>x?test)\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*\(\)\s*=>\s*\{"
        r"\s*expect\(\s*annotate\((?P<input>\[.*?\])\)\s*\)\.toEqual\((?P<expected>\[.*?\])\);\s*\}\);",
        re.DOTALL,
    )
    for m in p1.finditer(spec_source):
        inp = clean_json_array(m.group("input"))
        exp = clean_json_array(m.group("expected"))
        cases.append(
            {
                "name": m.group("name"),
                "input": inp,
                "expected": exp,
                "enabled_in_learner_suite": m.group("flag") == "test",
            }
        )

    # Pattern 2: const input = [...]; const expected = [...]; expect(annotate(input)).toEqual(expected);
    p2 = re.compile(
        r"(?P<flag>x?test)\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*\(\)\s*=>\s*\{"
        r"\s*const\s+input\s*=\s*(?P<input>\[.*?\]);\s*"
        r"const\s+expected\s*=\s*(?P<expected>\[.*?\]);\s*"
        r"expect\(\s*annotate\(input\)\s*\)\.toEqual\(expected\);\s*\}\);",
        re.DOTALL,
    )
    for m in p2.finditer(spec_source):
        inp = clean_json_array(m.group("input"))
        exp = clean_json_array(m.group("expected"))
        cases.append(
            {
                "name": m.group("name"),
                "input": inp,
                "expected": exp,
                "enabled_in_learner_suite": m.group("flag") == "test",
            }
        )

    if not cases:
        raise CheckError("No test cases could be parsed from flower-field.spec.js")

    names = [c["name"] for c in cases]
    if len(names) != len(set(names)):
        raise CheckError("Duplicate test names found in flower-field.spec.js")

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
        {"numTotalTests": 13, "numPassedTests": 12, "numFailedTests": 1},
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

    process = run_process(cmd, root, env, "Flower Field Jest execution", processes_log)

    if not result_path.is_file():
        raise CheckError("Jest execution failed to write JSON result file")

    jest_result = json.loads(result_path.read_text(encoding="utf-8"))
    return jest_result, process


def run_exercise_probe(root, copied_exercise, cases, env, processes_log):
    """Run an isolated Node probe to verify actual outputs for all cases."""
    probe_script = copied_exercise / "probe-cases.mjs"
    output_path = copied_exercise / "probe-outputs.json"

    probe_code = f"""import fs from 'node:fs';
import {{ annotate }} from './flower-field.js';

const cases = {json.dumps(cases)};
const results = [];

for (const c of cases) {{
  const actual = annotate(c.input);
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
    run_process(cmd, root, env, "Exercise cases probe execution", processes_log)

    if not output_path.is_file():
        raise CheckError("Exercise cases probe failed to produce outputs file")

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


def run_micro_example(root, env, processes_log):
    """Run the standalone JavaScript micro-example and contrasting example."""
    with tempfile.TemporaryDirectory() as temp_dir:
        probe_file = Path(temp_dir) / "micro-probe.mjs"
        probe_file.write_text(MICRO_PROBE_CODE, encoding="utf-8")

        proc = run_process(["node", str(probe_file)], root, env, "Micro-example execution", processes_log)
        payload = json.loads(proc.stdout)

        micro = payload["micro_example"]
        contrast = payload["contrasting_example"]

        # Assert micro-example: in_bounds_access
        if not micro["in_bounds_access"]["match"]:
            raise CheckError(
                f"Micro-example in-bounds assertion failed: expected {micro['in_bounds_access']['expected']}, "
                f"got {micro['in_bounds_access']['actual']}"
            )

        # Assert micro-example: out_of_bounds_access
        if not micro["out_of_bounds_access"]["match"]:
            raise CheckError(
                f"Micro-example out-of-bounds assertion failed: expected {micro['out_of_bounds_access']['expected']}, "
                f"got {micro['out_of_bounds_access']['actual']}"
            )

        # Assert contrasting pitfall example
        if not contrast["match"]:
            raise CheckError(
                f"Contrasting example assertion failed: expected {contrast['expected']}, "
                f"got {contrast['actual']}"
            )

        return payload


def main():
    root = find_root()
    exercise = root / ASSIGNMENT
    work_dir = root / "work" / "R53-T047"
    work_dir.mkdir(parents=True, exist_ok=True)

    evidence_path = work_dir / "evidence.json"
    results_path = work_dir / "results.json"
    inputs_path = work_dir / "inputs.json"

    processes_log = []
    print(f"=== Starting R53-T047 Flower Field Checker ===")
    print(f"Repository root: {root}")
    print(f"Exercise path:   {exercise}")

    # 1. Detect package manager from lockfile
    package_manager = detect_package_manager(root)
    print(f"Detected package manager from lockfile: {package_manager}")

    # 2. Read and parse exercise config.json
    config_file = root / CONFIG_PATH
    if not config_file.is_file():
        raise CheckError(f"Configuration file missing: {config_file}")
    config = json.loads(config_file.read_text(encoding="utf-8"))

    files = resolve_files(exercise, config)
    learner_path = exercise / files["solution"][0][0]
    spec_path = exercise / files["test"][0][0]
    reference_path = exercise / files["example"][0][0]

    # Baseline file hashes
    learner_hash_before = sha256(learner_path)
    spec_hash_before = sha256(spec_path)
    reference_hash_before = sha256(reference_path)

    cases = parse_cases(spec_path.read_text(encoding="utf-8"))
    enabled_count_baseline = sum(c["enabled_in_learner_suite"] for c in cases)
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

    # Setup child process environment
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
        "package_manager": package_manager,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    print(f"Tools: Node {tool_versions['node']}, {package_manager} {tool_versions['pnpm']}, Python {tool_versions['python']}")

    # 3. Run Standalone JavaScript Micro-Example and Contrasting Example
    micro_results = run_micro_example(root, env, processes_log)
    print("Micro-example & contrasting pitfall: successfully executed and verified")

    # 4. Clone exercise to temporary directory and run Jest
    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root) / "flower-field"
        cloned_count = clone_exercise(exercise, temp_dir, reference_path, files)
        print(f"Cloned {cloned_count} files into isolated directory: {temp_dir}")

        jest_raw, _ = run_test_suite(root, temp_dir, files, test_script, env, processes_log)
        counts = validate_jest_result(jest_raw, len(cases), "Flower Field test suite")
        print(f"Jest execution: {counts['passed']}/{counts['total']} tests passed (0 failed)")

        probe_outputs = run_exercise_probe(root, temp_dir, cases, env, processes_log)
        print(f"Probe execution: {len(probe_outputs)}/{len(cases)} cases verified")

    # 5. Verify working tree was never modified
    learner_hash_after = sha256(learner_path)
    spec_hash_after = sha256(spec_path)
    reference_hash_after = sha256(reference_path)

    if learner_hash_after != learner_hash_before:
        raise CheckError("CRITICAL: Original learner solution file was modified!")
    if spec_hash_after != spec_hash_before:
        raise CheckError("CRITICAL: Original exercise spec file was modified!")
    if reference_hash_after != reference_hash_before:
        raise CheckError("CRITICAL: Original reference implementation file was modified!")

    print("Working tree verification: learner stub and spec files are strictly unchanged")

    # 6. Verify required named cases
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

    # 7. Save inputs.json
    inputs_data = {
        "exercise": "flower-field",
        "demonstrated_construct": CONSTRUCT_NAME,
        "micro_example_inputs": micro_results["micro_example"]["input_grid"],
        "total_exercise_cases": len(cases),
        "exercise_cases": cases,
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    # 8. Save results.json
    results_data = {
        "exercise": "flower-field",
        "demonstrated_construct": CONSTRUCT_NAME,
        "micro_example_results": micro_results["micro_example"],
        "contrasting_example_results": micro_results["contrasting_example"],
        "test_counts": counts,
        "required_named_cases": required_results,
        "all_cases": probe_outputs,
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    # 9. Save evidence.json
    evidence_data = {
        "task": "R53-T047",
        "exercise": "flower-field",
        "timestamp_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
        "tool_versions": tool_versions,
        "file_hashes": {
            "learner_stub_sha256": learner_hash_after,
            "reference_implementation_sha256": reference_hash_after,
            "test_spec_sha256": spec_hash_after,
            "learner_stub_unchanged": learner_hash_after == learner_hash_before,
            "reference_unchanged": reference_hash_after == reference_hash_before,
        },
        "demonstrated_construct": {
            "name": CONSTRUCT_NAME,
            "used_by": "adjacentSquareIsOnBoard(board, x, d) => board[x + d[0]]",
            "micro_example": micro_results["micro_example"],
            "contrasting_example": micro_results["contrasting_example"],
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

    # 10. Print Readable Summary (Requirement 12)
    print("\n" + "=" * 80)
    print("SUMMARY OF VERIFICATION")
    print("=" * 80)
    print(f"JavaScript Construct Demonstrated:\n  {CONSTRUCT_NAME}")
    print("\nMicro-Example Results:")
    print(f"  - In-bounds  ({micro_results['micro_example']['in_bounds_access']['expression']}):")
    print(f"      Expected: {micro_results['micro_example']['in_bounds_access']['expected']}")
    print(f"      Actual:   {micro_results['micro_example']['in_bounds_access']['actual']} (MATCH: PASS)")
    print(f"  - Out-bounds ({micro_results['micro_example']['out_of_bounds_access']['expression']}):")
    print(f"      Expected: {micro_results['micro_example']['out_of_bounds_access']['expected']}")
    print(f"      Actual:   {micro_results['micro_example']['out_of_bounds_access']['actual']} (MATCH: PASS)")
    print("\nContrasting Pitfall Example Results:")
    print(f"  - Expression: {micro_results['contrasting_example']['expression']}")
    print(f"      Expected: {micro_results['contrasting_example']['expected']}")
    print(f"      Actual:   {micro_results['contrasting_example']['actual']} ({micro_results['contrasting_example']['error_message']}) (MATCH: PASS)")
    print(f"\nExercise Test Suite Execution:")
    print(f"  - Executed Tests: {counts['total']}")
    print(f"  - Passed:         {counts['passed']}")
    print(f"  - Failed:         {counts['failed']}")
    print(f"  - Test Result:    ALL PASS")
    print("\nTool Versions:")
    print(f"  - Python:          {tool_versions['python']}")
    print(f"  - Node.js:         {tool_versions['node']}")
    print(f"  - Package Manager: {tool_versions['package_manager']} ({tool_versions['pnpm']})")
    print("=" * 80)

    print(f"\nArtifacts successfully written to {work_dir}:")
    print(f" - {inputs_path.relative_to(root)}")
    print(f" - {results_path.relative_to(root)}")
    print(f" - {evidence_path.relative_to(root)}")
    print("=== Check completed successfully ===")


if __name__ == "__main__":
    try:
        main()
    except CheckError as err:
        print(f"\nVALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(1)

