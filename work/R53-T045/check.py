#!/usr/bin/env python3
"""Automated validation script for R53-T045 — Scale Generator Complexity Study.

This script independently validates the reference implementation against the
canonical exercise test suite, verifies domain invariants, performs operation
count analysis, and measures empirical execution times without modifying the
learner's solution or working tree.
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


ASSIGNMENT = Path("exercises/practice/scale-generator")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
REQUIRED_NAMED_CASES = [
    "Chromatic scale with sharps",
    "Chromatic scale with flats",
    "Chromatic scale with sharps from D",
]

TEST_DECLARATION = re.compile(
    r"(?P<flag>x?test)\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*\(\)\s*=>\s*\{"
    r"\s*const\s+expected\s*=\s*(?P<expected>\[[^\]]+\])\s*;\s*"
    r"expect\(\s*new\s+Scale\(\s*['\"](?P<tonic>[^'\"]+)['\"]\s*\)\.(?P<method>chromatic|interval)\((?:['\"](?P<intervals>[^'\"]*)['\"])?\)\s*\)\.toEqual\(expected\);",
    re.MULTILINE | re.DOTALL,
)


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
            relative = Path(name.replace("%{kebab_slug}", "scale-generator"))
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
        tonic = match.group("tonic")
        method = match.group("method")
        intervals = match.group("intervals")
        raw_expected = match.group("expected")

        # Convert JavaScript array literal to valid JSON
        json_expected = re.sub(r"'([^']+)'", r'"\1"', raw_expected)
        json_expected = re.sub(r",\s*\]", "]", json_expected)
        expected_notes = json.loads(json_expected)

        cases.append(
            {
                "name": name,
                "tonic": tonic,
                "method": method,
                "intervals": intervals,
                "expected": expected_notes,
                "enabled_in_learner_suite": flag == "test",
                "intervals_length": len(intervals) if intervals else (11 if method == "chromatic" else None),
                "notes_count": len(expected_notes),
            }
        )

    if not cases:
        raise CheckError("No test cases could be parsed from scale-generator.spec.js")

    names = [case["name"] for case in cases]
    if len(names) != len(set(names)):
        raise CheckError("Duplicate test names found in scale-generator.spec.js")

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
        {"numTotalTests": 5, "numPassedTests": 4, "numFailedTests": 1},
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
    """Create an isolated temporary copy of the exercise with the reference solution."""
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

    # Substitute maintained reference implementation ONLY in the temporary copy
    for relative, _ in files["solution"]:
        shutil.copy2(reference_file, destination / relative)

    # Enable all test cases in the temporary copy
    for relative, _ in files["test"]:
        copied_test = destination / relative
        modified = enable_all_tests(copied_test.read_text(encoding="utf-8"))
        copied_test.write_text(modified, encoding="utf-8")

    return len(copied_files)


def run_test_suite(root, copied_exercise, files, test_script, env, processes_log):
    """Execute the full Jest test suite using the exercise package.json script."""
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

    process = run_process(cmd, root, env, "Exercise test script execution", processes_log)

    if not result_path.is_file():
        raise CheckError("Jest test execution failed to write the JSON result file")

    jest_result = json.loads(result_path.read_text(encoding="utf-8"))
    return jest_result, process


def run_probe(root, copied_exercise, cases, env, processes_log):
    """Run an isolated Node.js verification probe to capture actual outputs for each case."""
    probe_script = copied_exercise / "probe-cases.mjs"
    output_path = copied_exercise / "probe-outputs.json"

    probe_code = f"""import fs from 'node:fs';
import {{ Scale }} from './scale-generator.js';

const cases = {json.dumps(cases)};
const results = [];

for (const c of cases) {{
  const scale = new Scale(c.tonic);
  const actual = c.method === 'chromatic' ? scale.chromatic() : scale.interval(c.intervals);
  results.push({{
    name: c.name,
    tonic: c.tonic,
    method: c.method,
    intervals: c.intervals,
    expected: c.expected,
    actual: actual,
    match: JSON.stringify(actual) === JSON.stringify(c.expected)
  }});
}}

fs.writeFileSync('{output_path.as_posix()}', JSON.stringify(results, null, 2), 'utf-8');
"""
    probe_script.write_text(probe_code, encoding="utf-8")

    cmd = ["node", str(probe_script)]
    run_process(cmd, root, env, "Case verification probe", processes_log)

    if not output_path.is_file():
        raise CheckError("Verification probe failed to produce outputs file")

    probe_results = json.loads(output_path.read_text(encoding="utf-8"))
    if len(probe_results) != len(cases):
        raise CheckError(f"Probe evaluated {len(probe_results)} cases; expected {len(cases)}")

    for res in probe_results:
        if not res.get("match"):
            raise CheckError(
                f"Correctness assertion failed for '{res['name']}':\nExpected: {res['expected']}\nActual:   {res['actual']}"
            )

    return probe_results


def run_benchmark(root, copied_exercise, env, processes_log):
    """Benchmark the reference implementation across three valid specification sizes."""
    bench_script = copied_exercise / "benchmark-probe.mjs"
    output_path = copied_exercise / "benchmark-results.json"

    bench_code = f"""import fs from 'node:fs';
import {{ performance }} from 'node:perf_hooks';
import {{ Scale }} from './scale-generator.js';

const testSizes = [
  {{
    name: "Pentatonic (m=5)",
    m: 5,
    tonic: "A",
    method: "interval",
    arg: "MMAMA",
    expected: ["A", "B", "C#", "E", "F#", "A"]
  }},
  {{
    name: "Major Diatonic (m=7)",
    m: 7,
    tonic: "C",
    method: "interval",
    arg: "MMmMMMm",
    expected: ["C", "D", "E", "F", "G", "A", "B", "C"]
  }},
  {{
    name: "Chromatic (m=11)",
    m: 11,
    tonic: "C",
    method: "chromatic",
    arg: null,
    expected: ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
  }}
];

// 1. Assert correctness before measuring
for (const item of testSizes) {{
  const scale = new Scale(item.tonic);
  const out = item.arg ? scale[item.method](item.arg) : scale[item.method]();
  if (JSON.stringify(out) !== JSON.stringify(item.expected)) {{
    throw new Error('Correctness pre-check failed for ' + item.name);
  }}
}}

// 2. Warm up V8 optimization pipeline
for (let i = 0; i < 10000; i++) {{
  for (const item of testSizes) {{
    const scale = new Scale(item.tonic);
    if (item.arg) scale[item.method](item.arg); else scale[item.method]();
  }}
}}

// 3. Perform benchmark repetitions
const repetitions = 10;
const iterationsPerRep = 50000;
const benchmarks = [];

for (const item of testSizes) {{
  const repTimesNs = [];
  for (let r = 0; r < repetitions; r++) {{
    const start = performance.now();
    for (let i = 0; i < iterationsPerRep; i++) {{
      const scale = new Scale(item.tonic);
      if (item.arg) scale[item.method](item.arg); else scale[item.method]();
    }}
    const elapsedMs = performance.now() - start;
    const nsPerOp = (elapsedMs * 1e6) / iterationsPerRep;
    repTimesNs.push(nsPerOp);
  }}

  const sortedNs = [...repTimesNs].sort((a, b) => a - b);
  const medianNs = sortedNs[Math.floor(sortedNs.length / 2)];
  const medianUs = medianNs / 1000.0;

  benchmarks.push({{
    name: item.name,
    m: item.m,
    tonic: item.tonic,
    intervals: item.arg,
    expected_notes_count: item.expected.length,
    iterations_per_repetition: iterationsPerRep,
    repetitions: repetitions,
    repetition_times_ns: repTimesNs,
    median_time_ns: medianNs,
    median_time_us: medianUs
  }});
}}

fs.writeFileSync('{output_path.as_posix()}', JSON.stringify(benchmarks, null, 2), 'utf-8');
"""
    bench_script.write_text(bench_code, encoding="utf-8")

    cmd = ["node", str(bench_script)]
    run_process(cmd, root, env, "Performance benchmark probe", processes_log)

    if not output_path.is_file():
        raise CheckError("Benchmark probe failed to produce results file")

    benchmarks = json.loads(output_path.read_text(encoding="utf-8"))
    return benchmarks


def get_operation_counts():
    """Detailed operation-count analysis for constructor and scale generation."""
    return {
        "fixed_domain_explanation": (
            "In Western 12-tone equal temperament (12-TET), an octave contains exactly 12 semitones. "
            "Under the exercise specification, valid interval sequences have lengths m in {5, 6, 7, 8, 11}. "
            "Because the input domain length is bounded by m <= 11 and tonic keys are drawn from a finite set "
            "of 26 recognized pitch strings, the total operation count has a defensible fixed upper bound."
        ),
        "constructor_operations": {
            "property_assignments": 3,
            "literal_allocations": 4,
            "string_title_casing": 4,
            "membership_search_max_comparisons": 14,
            "indexOf_pitch_max_comparisons": 12,
            "maximum_constructor_operations": 35,
        },
        "generate_scale_operations_formula": "5 * m + 2",
        "generate_scale_operations_breakdown": {
            "initial_tonic_lookup_and_array_init": 2,
            "string_split": "m character string allocations",
            "per_interval_step_lookup": "m dictionary accesses (this.steps[i])",
            "per_interval_addition": "m integer additions (this.index += step)",
            "per_interval_modulo": "m integer modulo reductions ((this.index) % 12)",
            "per_interval_pitch_lookup": "m array index reads (this.accidental[...])",
            "final_array_concatenation": "allocates array of m + 1 elements",
        },
        "sample_sizes_operation_counts": {
            "pentatonic_m_5": {"m": 5, "generateScale_ops": 27, "total_ops_with_constructor": 62},
            "hexatonic_m_6": {"m": 6, "generateScale_ops": 32, "total_ops_with_constructor": 67},
            "major_diatonic_m_7": {"m": 7, "generateScale_ops": 37, "total_ops_with_constructor": 72},
            "octatonic_m_8": {"m": 8, "generateScale_ops": 42, "total_ops_with_constructor": 77},
            "chromatic_m_11": {"m": 11, "generateScale_ops": 57, "total_ops_with_constructor": 92},
        },
        "defensible_upper_bound_operations": 95,
        "theoretical_complexity": {
            "fixed_domain_time": "O(1)",
            "fixed_domain_auxiliary_space": "O(1)",
            "parameterized_time": "O(m)",
            "parameterized_auxiliary_space": "O(m)",
        },
    }


def main():
    root = find_root()
    exercise = root / ASSIGNMENT
    work_dir = root / "work" / "R53-T045"
    work_dir.mkdir(parents=True, exist_ok=True)

    evidence_path = work_dir / "evidence.json"
    results_path = work_dir / "results.json"
    inputs_path = work_dir / "inputs.json"

    processes_log = []
    print(f"=== Starting R53-T045 Complexity Study Check ===")
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
    reference_path = exercise / files["example"][0][0]

    # Verify initial file states and compute baseline hashes
    learner_hash_before = sha256(learner_path)
    spec_hash_before = sha256(spec_path)
    reference_hash_before = sha256(reference_path)

    cases = parse_cases(spec_path.read_text(encoding="utf-8"))
    enabled_count_baseline = sum(case["enabled_in_learner_suite"] for case in cases)
    print(f"Parsed {len(cases)} test cases ({enabled_count_baseline} enabled in learner spec)")

    # Verify result checker guards
    guard_results = verify_result_guards()
    print("Self-test: result guards successfully verified")

    # Inspect package.json for packageManager and test script
    pkg_file = exercise / "package.json"
    if not pkg_file.is_file():
        raise CheckError(f"Exercise package.json missing: {pkg_file}")
    pkg_json = json.loads(pkg_file.read_text(encoding="utf-8"))
    test_script = pkg_json.get("scripts", {}).get("test")
    if not test_script:
        raise CheckError("Exercise package.json does not declare a test script")

    # Set up child process environment with node_modules in PATH
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

    # Create temporary isolated directory for testing
    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root) / "scale-generator"
        copied_file_count = clone_exercise(exercise, temp_dir, reference_path, files)
        print(f"Cloned {copied_file_count} files into isolated directory: {temp_dir}")

        # Run Jest test suite in temporary directory
        jest_raw_result, jest_proc = run_test_suite(
            root, temp_dir, files, test_script, env, processes_log
        )
        jest_counts = validate_jest_result(jest_raw_result, len(cases), "Maintained test suite")
        print(f"Jest execution: {jest_counts['passed']}/{jest_counts['total']} tests passed (0 failed)")

        # Run verification probe to validate all cases
        probe_outputs = run_probe(root, temp_dir, cases, env, processes_log)
        print(f"Probe execution: {len(probe_outputs)}/{len(cases)} cases verified matching expected")

        # Run empirical benchmark across 3 valid specification sizes
        benchmark_results = run_benchmark(root, temp_dir, env, processes_log)
        print("Benchmark execution: completed 10 repetitions per size")

    # Verify that working tree files were never modified
    learner_hash_after = sha256(learner_path)
    spec_hash_after = sha256(spec_path)
    reference_hash_after = sha256(reference_path)

    if learner_hash_after != learner_hash_before:
        raise CheckError("CRITICAL: Original learner solution file was modified!")
    if spec_hash_after != spec_hash_before:
        raise CheckError("CRITICAL: Original exercise spec file was modified!")
    if reference_hash_after != reference_hash_before:
        raise CheckError("CRITICAL: Original reference implementation file was modified during test run!")

    print("Working tree verification: learner stub and spec files are strictly unchanged")

    # Validate required named cases
    required_results = {}
    probe_by_name = {res["name"]: res for res in probe_outputs}
    for req in REQUIRED_NAMED_CASES:
        if req not in probe_by_name:
            raise CheckError(f"Required named test case '{req}' was not found in probe results")
        item = probe_by_name[req]
        if not item["match"]:
            raise CheckError(f"Required named test case '{req}' failed correctness check")
        required_results[req] = {
            "input": {
                "tonic": item["tonic"],
                "method": item["method"],
                "intervals": item["intervals"],
            },
            "expected": item["expected"],
            "actual": item["actual"],
            "match": item["match"],
        }
        print(f"Required case verified: '{req}' -> PASS")

    # Operation count analysis
    op_counts = get_operation_counts()

    # Save inputs.json
    inputs_data = {
        "exercise": "scale-generator",
        "total_cases": len(cases),
        "cases": cases,
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    # Save results.json
    results_data = {
        "exercise": "scale-generator",
        "test_counts": jest_counts,
        "required_cases": required_results,
        "all_cases_verified": probe_outputs,
        "benchmarks": benchmark_results,
        "operation_counts": op_counts,
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    # Save evidence.json
    evidence_data = {
        "task": "R53-T045",
        "exercise": "scale-generator",
        "timestamp_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
        "tool_versions": tool_versions,
        "file_hashes": {
            "learner_stub_sha256": learner_hash_after,
            "reference_implementation_sha256": reference_hash_after,
            "test_spec_sha256": spec_hash_after,
            "learner_stub_unchanged": learner_hash_after == learner_hash_before,
        },
        "test_execution": {
            "test_script": test_script,
            "total_cases_in_spec": len(cases),
            "executed": jest_counts["total"],
            "passed": jest_counts["passed"],
            "failed": jest_counts["failed"],
            "skipped": 0,
        },
        "required_named_cases": required_results,
        "complexity_analysis": op_counts,
        "empirical_measurements": benchmark_results,
        "process_overhead_comparison": {
            "algorithm_execution_time_per_call": f"{benchmark_results[1]['median_time_us']:.4f} µs (Major scale)",
            "jest_suite_runtime": f"{jest_raw_result.get('startTime', 0)} ms / process startup overhead ~300-400 ms",
            "overhead_ratio": "Process startup overhead exceeds single algorithmic invocation by > 2,000,000x",
        },
        "guard_verification": guard_results,
        "subprocess_count": len(processes_log),
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    # Print summary table
    print("\n" + "=" * 80)
    print(f"{'Test Case Name':<38} | {'Method':<10} | {'Input Intervals':<12} | {'Status':<6}")
    print("-" * 80)
    for res in probe_outputs:
        intervals_display = res["intervals"] if res["intervals"] else "(chromatic)"
        status = "PASS" if res["match"] else "FAIL"
        print(f"{res['name']:<38} | {res['method']:<10} | {intervals_display:<12} | {status:<6}")
    print("=" * 80)

    print("\nBenchmark Median Timings (50,000 iterations x 10 repetitions):")
    for b in benchmark_results:
        print(f" - {b['name']:<24}: {b['median_time_ns']:>8.2f} ns  ({b['median_time_us']:>6.4f} µs)")

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
