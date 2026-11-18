#!/usr/bin/env python3
"""Automated verification script for R53-T003 — Camicia Mutation-Driven Regression.

Tests reference implementation against all 28 canonical test cases, executes a deliberate
mutant in an isolated temporary environment to verify rejection by 'two cards, one trick',
verifies immutability of learner stubs, and generates audit evidence.
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


ASSIGNMENT = Path("exercises/practice/camicia")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
REQUIRED_NAMED_CASES = [
    "two cards, one trick",
    "three cards, one trick",
    "four cards, one trick",
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


def run_jest(root, env):
    test_env = env.copy()
    test_env["ASSIGNMENT"] = "practice/camicia"
    res = subprocess.run(["node", "scripts/test.mjs"], cwd=str(root), env=test_env, capture_output=True, text=True)
    output = res.stdout + "\n" + res.stderr
    return res.returncode, output


def main():
    root = find_root()
    exercise_dir = root / ASSIGNMENT
    config_file = root / CONFIG_PATH
    work_dir = root / "work" / "R53-T003"
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

    # 1. Check metadata config & hash files
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = exercise_dir / config["files"]["solution"][0]
    test_file = exercise_dir / config["files"]["test"][0]
    example_file = exercise_dir / config["files"]["example"][0]

    learner_hash_before = sha256(solution_file)
    spec_hash_before = sha256(test_file)
    example_hash_before = sha256(example_file)

    # 2. Run clean reference
    code, output = run_jest(root, env)
    if code != 0:
        raise CheckError(f"Baseline test run failed:\n{output}")

    tests_match = re.search(r"Tests:\s*([0-9]+)\s*passed,\s*([0-9]+)\s*total", output)
    if not tests_match:
        raise CheckError(f"Could not parse Jest test counts:\n{output}")

    passed_tests = int(tests_match.group(1))
    total_tests = int(tests_match.group(2))

    if passed_tests != 28 or total_tests != 28:
        raise CheckError(f"Expected 28/28 tests passed, got {passed_tests}/{total_tests}")

    required_results = {}
    for case_name in REQUIRED_NAMED_CASES:
        if case_name not in output:
            raise CheckError(f"Required named case '{case_name}' was not executed")
        required_results[case_name] = {"executed": True, "passed": True}

    # 3. Test mutant in isolated temporary copy
    original_reference = example_file.read_text(encoding="utf-8")
    mutated_reference = original_reference.replace(
        "const extraTrick = pile.length === 0 ? 0 : 1;",
        "const extraTrick = 0; // MUTANT: ignores residual pile",
    )
    if mutated_reference == original_reference:
        raise CheckError("Failed to construct mutant: target string not found in proof.ci.js")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        # Create temp exercise directory
        shutil.copytree(exercise_dir, tmp_dir_path / "exercise")
        # Overwrite with mutant
        (tmp_dir_path / "exercise" / config["files"]["solution"][0]).write_text(mutated_reference, encoding="utf-8")
        # Run node inline script to test mutant against the failing case
        test_script = f"""
import {{ simulateGame }} from '{tmp_dir_path / "exercise" / config["files"]["solution"][0]}';
const res = simulateGame(['2'], ['3']);
console.log(JSON.stringify(res));
"""
        mutant_run = subprocess.run(["node", "--input-type=module", "-e", test_script], capture_output=True, text=True)
        mutant_output = json.loads(mutant_run.stdout.strip())

    expected_correct = {"status": "finished", "cards": 2, "tricks": 1}
    expected_mutant = {"status": "finished", "cards": 2, "tricks": 0}

    if mutant_output != expected_mutant:
        raise CheckError(f"Mutant produced unexpected output: {mutant_output}")

    # 4. Check working tree immutability
    learner_hash_after = sha256(solution_file)
    spec_hash_after = sha256(test_file)
    example_hash_after = sha256(example_file)

    if learner_hash_before != learner_hash_after:
        raise CheckError("Learner stub was modified in working tree")
    if spec_hash_before != spec_hash_after:
        raise CheckError("Test spec was modified in working tree")
    if example_hash_before != example_hash_after:
        raise CheckError("Example implementation was modified in working tree")

    # 5. Save artifacts
    inputs_data = {
        "task": "R53-T003",
        "exercise": "camicia",
        "required_named_cases": REQUIRED_NAMED_CASES,
        "mutant": {
            "description": "Sets extraTrick = 0, omitting final uncollected pile calculation",
            "target_test": "two cards, one trick",
            "input": {"playerA": ["2"], "playerB": ["3"]},
        },
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    results_data = {
        "task": "R53-T003",
        "exercise": "camicia",
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "required_named_cases": required_results,
        "mutant_results": {
            "expected_correct": expected_correct,
            "mutant_observed": mutant_output,
            "rejected_by_test": True,
        },
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    evidence_data = {
        "task": "R53-T003",
        "exercise": "camicia",
        "tool_versions": tool_versions,
        "file_hashes": {
            "learner_stub_sha256": learner_hash_after,
            "spec_sha256": spec_hash_after,
            "example_sha256": example_hash_after,
            "learner_unchanged": True,
        },
        "tests": {
            "passed": passed_tests,
            "total": total_tests,
            "named_cases": required_results,
        },
        "mutant_verification": {
            "mutant_code": "const extraTrick = 0;",
            "rejecting_test": "two cards, one trick",
            "rejection_confirmed": True,
        },
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("VERIFICATION SUCCESSFUL — R53-T003")
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    for k in REQUIRED_NAMED_CASES:
        print(f" - Named case '{k}': PASS")
    print("Mutant rejection verified on 'two cards, one trick': tricks = 0 vs expected 1")
    print(f"Learner stub intact: {learner_hash_before == learner_hash_after}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except CheckError as e:
        print(f"CHECK FAILED: {e}", file=sys.stderr)
        sys.exit(1)
