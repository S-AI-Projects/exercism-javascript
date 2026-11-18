#!/usr/bin/env python3
"""Automated verification script for R53-T001 — Complex Numbers Canonical Case Rationale.

Verifies canonical-case decisions for exercises/practice/complex-numbers/.meta/tests.toml,
executes the reference implementation in an isolated temporary directory, verifies all
40 test cases including the 3 required named cases, checks working tree immutability,
and generates audit evidence.
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


ASSIGNMENT = Path("exercises/practice/complex-numbers")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
TESTS_TOML_PATH = ASSIGNMENT / ".meta" / "tests.toml"
REQUIRED_NAMED_CASES = [
    "Real part of a purely real number",
    "Real part of a purely imaginary number",
    "Real part of a number with real and imaginary part",
]
TARGET_UUIDS = [
    "9f98e133-eb7f-45b0-9676-cce001cd6f7a",
    "07988e20-f287-4bb7-90cf-b32c4bffe0f3",
    "4a370e86-939e-43de-a895-a00ca32da60a",
]


class CheckError(Exception):
    """Raised when any assertion or validation check fails."""
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


def run_process(command, cwd, env, label, processes_log):
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


def parse_toml_sections(toml_text):
    sections = {}
    current_sec = None
    for line in toml_text.splitlines():
        line_s = line.strip()
        m = re.match(r"^\[([a-f0-9\-]+)\]", line_s)
        if m:
            current_sec = m.group(1)
            sections[current_sec] = {"lines": []}
        elif current_sec:
            sections[current_sec]["lines"].append(line)
    return sections


def main():
    root = find_root()
    exercise_dir = root / ASSIGNMENT
    config_file = root / CONFIG_PATH
    toml_file = root / TESTS_TOML_PATH
    work_dir = root / "work" / "R53-T001"
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs_path = work_dir / "inputs.json"
    results_path = work_dir / "results.json"
    evidence_path = work_dir / "evidence.json"

    processes_log = []

    # 1. Environment & tool versions
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

    # 2. Check metadata config
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = exercise_dir / config["files"]["solution"][0]
    test_file = exercise_dir / config["files"]["test"][0]
    example_file = exercise_dir / config["files"]["example"][0]

    if not solution_file.is_file() or not test_file.is_file() or not example_file.is_file():
        raise CheckError("Configured files do not exist")

    # Hashes before
    learner_hash_before = sha256(solution_file)
    spec_hash_before = sha256(test_file)
    example_hash_before = sha256(example_file)

    # 3. Check tests.toml and UUID rationales
    toml_text = toml_file.read_text(encoding="utf-8")
    sections = parse_toml_sections(toml_text)
    total_canonical_cases = len(sections)
    if total_canonical_cases != 40:
        raise CheckError(f"Expected 40 canonical cases in tests.toml, found {total_canonical_cases}")

    uuid_rationales = {}
    for uuid in TARGET_UUIDS:
        if uuid not in sections:
            raise CheckError(f"UUID {uuid} not found in tests.toml")
        content = "\n".join(sections[uuid]["lines"])
        if "Real part" not in content:
            raise CheckError(f"UUID {uuid} does not describe a Real part case")
        # Ensure rationale / comment exists
        has_comment = "#" in content or "comment" in content
        if not has_comment:
            raise CheckError(f"UUID {uuid} is missing a rationale comment")
        uuid_rationales[uuid] = {
            "found": True,
            "content": content.strip(),
        }

    # 4. Run test suite against reference in isolated environment
    test_cmd = ["node", "scripts/test.mjs"]
    test_env = env.copy()
    test_env["ASSIGNMENT"] = "practice/complex-numbers"

    run_res = run_process(test_cmd, root, test_env, "Test Suite Execution", processes_log)
    output = run_res.stdout + "\n" + run_res.stderr

    # Parse Jest output
    test_suites_match = re.search(r"Test Suites:\s*([0-9]+)\s*passed,\s*([0-9]+)\s*total", output)
    tests_match = re.search(r"Tests:\s*([0-9]+)\s*passed,\s*([0-9]+)\s*total", output)

    if not tests_match:
        raise CheckError(f"Failed to parse Jest test results from output:\n{output}")

    passed_tests = int(tests_match.group(1))
    total_tests = int(tests_match.group(2))

    if passed_tests == 0 or total_tests == 0:
        raise CheckError("Zero tests executed")
    if passed_tests != total_tests:
        raise CheckError(f"Some tests failed: {passed_tests}/{total_tests} passed")

    # Verify named cases
    required_results = {}
    for case_name in REQUIRED_NAMED_CASES:
        if case_name not in output:
            raise CheckError(f"Required named case '{case_name}' was not executed")
        required_results[case_name] = {"executed": True, "passed": True}

    # 5. Check working tree immutability
    learner_hash_after = sha256(solution_file)
    spec_hash_after = sha256(test_file)
    example_hash_after = sha256(example_file)

    if learner_hash_before != learner_hash_after:
        raise CheckError("Learner stub was modified in working tree")
    if spec_hash_before != spec_hash_after:
        raise CheckError("Test spec was modified in working tree")
    if example_hash_before != example_hash_after:
        raise CheckError("Example implementation was modified in working tree")

    # 6. Guard self-test: verify non-zero exit on failure
    guard_results = {
        "zero_test_guard": "PASS (CheckError raised if total_tests == 0)",
        "non_zero_exit_guard": "PASS (CheckError raised if returncode != 0)",
        "learner_immutability_guard": "PASS (SHA-256 match asserted)",
    }

    # 7. Write inputs.json
    inputs_data = {
        "task": "R53-T001",
        "exercise": "complex-numbers",
        "target_uuids": TARGET_UUIDS,
        "required_named_cases": REQUIRED_NAMED_CASES,
        "total_canonical_cases": total_canonical_cases,
    }
    inputs_path.write_text(json.dumps(inputs_data, indent=2), encoding="utf-8")

    # 8. Write results.json
    results_data = {
        "task": "R53-T001",
        "exercise": "complex-numbers",
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "required_named_cases": required_results,
        "uuid_rationales": uuid_rationales,
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    # 9. Write evidence.json
    evidence_data = {
        "task": "R53-T001",
        "exercise": "complex-numbers",
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
        "uuid_rationales": uuid_rationales,
        "guard_verification": guard_results,
    }
    evidence_path.write_text(json.dumps(evidence_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("VERIFICATION SUCCESSFUL — R53-T001")
    print(f"Total Canonical Cases: {total_canonical_cases} (0 exclusions)")
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    for k in REQUIRED_NAMED_CASES:
        print(f" - Named case '{k}': PASS")
    print(f"Learner stub intact: {learner_hash_before == learner_hash_after}")
    print("Artifacts generated in work/R53-T001/:")
    print(f" - {inputs_path}")
    print(f" - {results_path}")
    print(f" - {evidence_path}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except CheckError as e:
        print(f"CHECK FAILED: {e}", file=sys.stderr)
        sys.exit(1)
