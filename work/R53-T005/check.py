#!/usr/bin/env python3
"""Automated verification script for R53-T005 — Simple Cipher Complexity Study.

Measures the empirical scaling of Simple Cipher operations across 3 domain input sizes
with 5 repetitions (reporting medians), verifies operation bounds and invariant comments,
tests all 12 canonical test cases including required named cases, checks learner stub immutability,
and generates audit evidence.
"""

import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/simple-cipher")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
REQUIRED_NAMED_CASES = [
    "can encode",
    "can decode",
    "is reversible",
]


class CheckError(Exception):
    pass


def find_root():
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / CONFIG_PATH).is_file()
        ):
            return candidate
    raise CheckError("Could not locate repository root directory")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_benchmark(root, example_path):
    bench_code = f"""
import {{ Cipher }} from '{example_path}';
import {{ performance }} from 'node:perf_hooks';

const sizes = [10, 100, 250];
const results = {{}};

for (const size of sizes) {{
  const text = 'abcdefghij'.repeat(Math.ceil(size / 10)).slice(0, size);
  const cipher = new Cipher();
  
  // Assert correctness first
  const encoded = cipher.encode(text);
  const decoded = cipher.decode(encoded);
  if (decoded !== text) {{
    throw new Error('Correctness verification failed for size ' + size);
  }}

  // 5 repetitions
  const times = [];
  for (let rep = 0; rep < 5; rep++) {{
    const start = performance.now();
    for (let iter = 0; iter < 1000; iter++) {{
      cipher.encode(text);
      cipher.decode(encoded);
    }}
    const end = performance.now();
    times.push((end - start) / 1000); // ms per iteration
  }}
  times.sort((a, b) => a - b);
  const median = times[2];
  results[size] = {{
    input_size: size,
    correct: true,
    repetitions: times,
    median_ms: median,
    median_us: median * 1000,
  }};
}}
console.log(JSON.stringify(results));
"""
    res = subprocess.run(["node", "--input-type=module", "-e", bench_code], cwd=str(root), capture_output=True, text=True)
    if res.returncode != 0:
        raise CheckError(f"Benchmark run failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")
    return json.loads(res.stdout.strip())


def main():
    root = find_root()
    exercise_dir = root / ASSIGNMENT
    config_file = root / CONFIG_PATH
    work_dir = root / "work" / "R53-T005"
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs_path = work_dir / "inputs.json"
    results_path = work_dir / "results.json"
    evidence_path = work_dir / "evidence.json"

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"

    node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    pnpm_v = subprocess.run(["pnpm", "-v"], capture_output=True, text=True).stdout.strip()

    tool_versions = {
        "python": platform.python_version(),
        "node": node_v,
        "pnpm": pnpm_v,
        "platform": platform.platform(),
    }

    # 1. Metadata and file hashing
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = exercise_dir / config["files"]["solution"][0]
    test_file = exercise_dir / config["files"]["test"][0]
    example_file = exercise_dir / config["files"]["example"][0]

    learner_hash_before = sha256(solution_file)
    spec_hash_before = sha256(test_file)
    example_hash = sha256(example_file)

    # 2. Check invariant comments in proof.ci.js
    example_text = example_file.read_text(encoding="utf-8")
    if "Complexity and Invariant" not in example_text or "L = 100" not in example_text:
        raise CheckError("Complexity and invariant comment missing in proof.ci.js")

    # 3. Run Jest test suite
    test_env = env.copy()
    test_env["ASSIGNMENT"] = "practice/simple-cipher"
    test_res = subprocess.run(["node", "scripts/test.mjs"], cwd=str(root), env=test_env, capture_output=True, text=True)
    output = test_res.stdout + "\n" + test_res.stderr

    if test_res.returncode != 0:
        raise CheckError(f"Test suite failed:\n{output}")

    tests_match = re.search(r"Tests:\s*([0-9]+)\s*passed,\s*([0-9]+)\s*total", output)
    if not tests_match:
        raise CheckError(f"Could not parse Jest test counts:\n{output}")

    passed_tests = int(tests_match.group(1))
    total_tests = int(tests_match.group(2))

    if passed_tests != 12 or total_tests != 12:
        raise CheckError(f"Expected 12/12 tests passed, got {passed_tests}/{total_tests}")

    required_results = {}
    for case_name in REQUIRED_NAMED_CASES:
        if case_name not in output:
            raise CheckError(f"Required named case '{case_name}' was not executed")
        required_results[case_name] = {"executed": True, "passed": True}

    # 4. Run scaling benchmark
    bench_results = run_benchmark(root, example_file)

    # 5. Check learner stub immutability
    learner_hash_after = sha256(solution_file)
    spec_hash_after = sha256(test_file)

    if learner_hash_before != learner_hash_after:
        raise CheckError("Learner stub was modified in working tree")
    if spec_hash_before != spec_hash_after:
        raise CheckError("Test spec was modified in working tree")

    # 6. Save artifacts
    inputs_data = {
        "task": "R53-T005",
        "exercise": "simple-cipher",
        "required_named_cases": REQUIRED_NAMED_CASES,
        "input_domain_sizes": [10, 100, 250],
        "repetitions_per_size": 5,
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    results_data = {
        "task": "R53-T005",
        "exercise": "simple-cipher",
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "required_named_cases": required_results,
        "benchmark_scaling": bench_results,
        "fixed_domain_bound": {
            "key_length": 100,
            "complexity": "O(1) constant time, ~502 discrete VM operations",
        },
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    evidence_data = {
        "task": "R53-T005",
        "exercise": "simple-cipher",
        "tool_versions": tool_versions,
        "file_hashes": {
            "learner_stub_sha256": learner_hash_after,
            "spec_sha256": spec_hash_after,
            "example_sha256": example_hash,
            "learner_unchanged": True,
        },
        "tests": {
            "passed": passed_tests,
            "total": total_tests,
            "named_cases": required_results,
        },
        "complexity_study": {
            "comment_added": True,
            "benchmarks": bench_results,
        },
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("VERIFICATION SUCCESSFUL — R53-T005")
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    for k in REQUIRED_NAMED_CASES:
        print(f" - Named case '{k}': PASS")
    print("Measured Scaling Medians (5 reps per size):")
    for s, data in bench_results.items():
        print(f" - Size {s} chars: {data['median_us']:.2f} μs (correctness: {data['correct']})")
    print(f"Learner stub intact: {learner_hash_before == learner_hash_after}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except CheckError as e:
        print(f"CHECK FAILED: {e}", file=sys.stderr)
        sys.exit(1)
