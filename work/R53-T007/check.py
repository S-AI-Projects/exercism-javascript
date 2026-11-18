#!/usr/bin/env python3
"""Automated verification script for R53-T007 — Difference of Squares JavaScript Guidance.

Verifies JavaScript-specific coercion examples, executes canonical Jest tests in an
isolated temporary environment, verifies all 3 required named cases, checks micro-example
agreement, asserts learner stub immutability, and generates audit evidence.
"""

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/difference-of-squares")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
HINTS_PATH = ASSIGNMENT / ".docs" / "hints.md"
REQUIRED_NAMED_CASES = [
    "square of sum 1",
    "square of sum 5",
    "square of sum 100",
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


def verify_micro_examples(root):
    """Executes the micro-example and the pitfall to assert their exact outputs."""
    code = """
let numericSum = 0;
for (let x = 1; x <= 5; x += 1) {
  numericSum += x;
}
const squareOfSum = numericSum * numericSum;

let stringSum = "";
for (let x = 1; x <= 5; x += 1) {
  stringSum += x;
}

console.log(JSON.stringify({
  numeric_square: squareOfSum,
  string_concatenation: stringSum,
}));
"""
    res = subprocess.run(["node", "-e", code], cwd=str(root), capture_output=True, text=True)
    if res.returncode != 0:
        raise CheckError(f"Micro-example execution failed: {res.stderr}")
    data = json.loads(res.stdout.strip())
    if data["numeric_square"] != 225 or data["string_concatenation"] != "12345":
        raise CheckError(f"Micro-example outputs do not match expectation: {data}")
    return data


def main():
    root = find_root()
    exercise_dir = root / ASSIGNMENT
    config_file = root / CONFIG_PATH
    hints_file = root / HINTS_PATH
    work_dir = root / "work" / "R53-T007"
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs_path = work_dir / "inputs.json"
    results_path = work_dir / "results.json"
    evidence_path = work_dir / "evidence.json"

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"

    tool_versions = {
        "python": platform.python_version(),
        "node": subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip(),
        "pnpm": subprocess.run(["pnpm", "-v"], capture_output=True, text=True).stdout.strip(),
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

    # 2. Check hints.md
    if not hints_file.is_file():
        raise CheckError("hints.md is missing")
    hints_text = hints_file.read_text(encoding="utf-8")
    if "coercion" not in hints_text.lower() or "developer.mozilla.org" not in hints_text:
        raise CheckError("hints.md is missing coercion explanation or MDN documentation link")

    # 3. Run Jest test suite
    test_env = env.copy()
    test_env["ASSIGNMENT"] = "practice/difference-of-squares"
    test_res = subprocess.run(["node", "scripts/test.mjs"], cwd=str(root), env=test_env, capture_output=True, text=True)
    output = test_res.stdout + "\n" + test_res.stderr

    if test_res.returncode != 0:
        raise CheckError(f"Test suite failed:\n{output}")

    tests_match = re.search(r"Tests:\s*([0-9]+)\s*passed,\s*([0-9]+)\s*total", output)
    if not tests_match:
        raise CheckError(f"Could not parse Jest test counts:\n{output}")

    passed_tests = int(tests_match.group(1))
    total_tests = int(tests_match.group(2))

    required_results = {}
    for case_name in REQUIRED_NAMED_CASES:
        if case_name not in output:
            raise CheckError(f"Required named case '{case_name}' was not executed")
        required_results[case_name] = {"executed": True, "passed": True}

    # 4. Verify micro-examples
    micro_results = verify_micro_examples(root)

    # 5. Check learner stub immutability
    learner_hash_after = sha256(solution_file)
    spec_hash_after = sha256(test_file)

    if learner_hash_before != learner_hash_after:
        raise CheckError("Learner stub was modified in working tree")
    if spec_hash_before != spec_hash_after:
        raise CheckError("Test spec was modified in working tree")

    # 6. Save artifacts
    inputs_data = {
        "task": "R53-T007",
        "exercise": "difference-of-squares",
        "required_named_cases": REQUIRED_NAMED_CASES,
        "language_construct": "Type coercion in numeric accumulation vs string concatenation",
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    results_data = {
        "task": "R53-T007",
        "exercise": "difference-of-squares",
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "required_named_cases": required_results,
        "micro_examples_outputs": micro_results,
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    evidence_data = {
        "task": "R53-T007",
        "exercise": "difference-of-squares",
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
        "language_guidance": {
            "construct_analyzed": "coercion",
            "micro_examples_verified": True,
        },
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("VERIFICATION SUCCESSFUL — R53-T007")
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    for k in REQUIRED_NAMED_CASES:
        print(f" - Named case '{k}': PASS")
    print(f"Micro-examples verified: numeric = {micro_results['numeric_square']}, string = '{micro_results['string_concatenation']}'")
    print(f"Learner stub intact: {learner_hash_before == learner_hash_after}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except CheckError as e:
        print(f"CHECK FAILED: {e}", file=sys.stderr)
        sys.exit(1)
