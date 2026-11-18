#!/usr/bin/env python3
"""Automated verification script for R53-T010 — React Contract Cases and Isolated Runner.

Validates the isolated runner against three scenarios:
1. Real reference (all 13 tests pass)
2. Deliberately failing reference (failure propagated)
3. Empty test selection (zero-test guard)

Verifies named cases, learner file immutability, hints walkthrough, and generates audit evidence.
"""

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ASSIGNMENT = Path("exercises/practice/react")
CONFIG_PATH = ASSIGNMENT / ".meta" / "config.json"
REQUIRED_NAMED_CASES = [
    "accepts input",
    "allows input cell value to be set",
    "allows setting compute cells",
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


def main():
    root = find_root()
    exercise_dir = root / ASSIGNMENT
    config_file = root / CONFIG_PATH
    work_dir = root / "work" / "R53-T010"
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs_path = work_dir / "inputs.json"
    results_path = work_dir / "results.json"
    evidence_path = work_dir / "evidence.json"

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"

    tool_versions = {
        "python": platform.python_version(),
        "node": subprocess.run(["node", "-v"], capture_output=True, text=True, env=env).stdout.strip(),
        "pnpm": subprocess.run(["pnpm", "-v"], capture_output=True, text=True, env=env).stdout.strip(),
        "platform": platform.platform(),
    }

    # Load config
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = exercise_dir / config["files"]["solution"][0]
    test_file = exercise_dir / config["files"]["test"][0]

    # Hash learner files BEFORE
    learner_hash_before = sha256(solution_file)
    spec_hash_before = sha256(test_file)

    checks = []
    all_passed = True

    runner_script = root / "tools" / "course_checks" / "r53-t010.py"

    # ── Check 1: Runner script exists ──
    if runner_script.is_file():
        checks.append({"name": "runner_exists", "passed": True, "detail": str(runner_script)})
    else:
        checks.append({"name": "runner_exists", "passed": False, "detail": "Runner script not found"})
        all_passed = False

    # ── Check 2: Hints documentation exists ──
    hints_doc = exercise_dir / ".docs" / "hints.md"
    if hints_doc.is_file():
        checks.append({"name": "hints_doc_exists", "passed": True, "detail": str(hints_doc)})
    else:
        checks.append({"name": "hints_doc_exists", "passed": False, "detail": "Hints doc not found"})
        all_passed = False

    # ── Check 3: Maintenance doc exists ──
    maint_doc = root / "docs" / "maintenance" / "react.md"
    if maint_doc.is_file():
        checks.append({"name": "maintenance_doc_exists", "passed": True, "detail": str(maint_doc)})
    else:
        checks.append({"name": "maintenance_doc_exists", "passed": False, "detail": "Maintenance doc not found"})
        all_passed = False

    # ── Check 4: Run with real reference (all tests pass) ──
    print("Running isolated test runner with real reference...")
    res_normal = subprocess.run(
        [sys.executable, str(runner_script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    normal_output = res_normal.stdout + "\n" + res_normal.stderr

    tests_match = re.search(r"Test results:\s*(\d+)\s*passed,\s*(\d+)\s*total", normal_output)
    if tests_match:
        passed_count = int(tests_match.group(1))
        total_count = int(tests_match.group(2))
    else:
        passed_count = 0
        total_count = 0

    if res_normal.returncode == 0 and passed_count > 0:
        checks.append({
            "name": "real_reference_passes",
            "passed": True,
            "detail": f"{passed_count}/{total_count} tests passed",
        })
        print(f"  ✓ All {passed_count} tests passed")
    else:
        checks.append({
            "name": "real_reference_passes",
            "passed": False,
            "detail": f"Exit code: {res_normal.returncode}, output: {normal_output[-500:]}",
        })
        all_passed = False
        print(f"  ✗ Tests failed (exit {res_normal.returncode})")

    # ── Check 5: Verify named test cases in spec ──
    print("Verifying named test cases...")
    spec_content = test_file.read_text(encoding="utf-8")
    named_cases_found = []
    named_cases_missing = []

    for case_name in REQUIRED_NAMED_CASES:
        if case_name.lower() in spec_content.lower():
            named_cases_found.append(case_name)
        else:
            named_cases_missing.append(case_name)

    if len(named_cases_found) == len(REQUIRED_NAMED_CASES):
        checks.append({
            "name": "named_cases_present",
            "passed": True,
            "detail": f"All named cases found: {named_cases_found}",
        })
        print(f"  ✓ All named cases present: {named_cases_found}")
    else:
        checks.append({
            "name": "named_cases_present",
            "passed": False,
            "detail": f"Missing: {named_cases_missing}",
        })
        all_passed = False
        print(f"  ✗ Missing named cases: {named_cases_missing}")

    # ── Check 6: Run with failing reference (failure propagation) ──
    print("Running isolated test runner with deliberately failing reference...")
    res_fail = subprocess.run(
        [sys.executable, str(runner_script), "--fail-ref"],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    if res_fail.returncode != 0:
        checks.append({
            "name": "failure_propagation",
            "passed": True,
            "detail": f"Runner correctly returned non-zero exit code: {res_fail.returncode}",
        })
        print(f"  ✓ Failure correctly propagated (exit {res_fail.returncode})")
    else:
        checks.append({
            "name": "failure_propagation",
            "passed": False,
            "detail": "Runner returned 0 for a failing reference",
        })
        all_passed = False
        print("  ✗ Failure was not propagated")

    # ── Check 7: Run with empty tests (zero-test guard) ──
    print("Running isolated test runner with empty test selection...")
    res_empty = subprocess.run(
        [sys.executable, str(runner_script), "--empty-tests"],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    empty_output = res_empty.stdout + "\n" + res_empty.stderr

    if res_empty.returncode == 2:
        checks.append({
            "name": "zero_test_guard",
            "passed": True,
            "detail": f"Runner correctly returned exit code 2 for zero tests",
        })
        print("  ✓ Zero-test guard working (exit 2)")
    else:
        checks.append({
            "name": "zero_test_guard",
            "passed": False,
            "detail": f"Expected exit 2, got {res_empty.returncode}. Output: {empty_output[-300:]}",
        })
        all_passed = False
        print(f"  ✗ Zero-test guard failed (exit {res_empty.returncode})")

    # ── Check 8: Learner file immutability ──
    learner_hash_after = sha256(solution_file)
    spec_hash_after = sha256(test_file)

    if learner_hash_before == learner_hash_after and spec_hash_before == spec_hash_after:
        checks.append({
            "name": "learner_file_immutability",
            "passed": True,
            "detail": f"stub hash: {learner_hash_before[:16]}..., spec hash: {spec_hash_before[:16]}...",
        })
        print("  ✓ Learner files unchanged")
    else:
        checks.append({
            "name": "learner_file_immutability",
            "passed": False,
            "detail": "Learner files were modified",
        })
        all_passed = False
        print("  ✗ Learner files modified!")

    # ── Check 9: Temp directory cleanup ──
    if "cleaned up" in normal_output.lower():
        checks.append({"name": "temp_cleanup", "passed": True, "detail": "Temporary directory cleaned up"})
        print("  ✓ Temporary directory cleanup confirmed")
    else:
        checks.append({"name": "temp_cleanup", "passed": False, "detail": "No cleanup confirmation found"})
        all_passed = False
        print("  ✗ Cleanup not confirmed")

    # ── Generate evidence ──
    inputs_data = {
        "task": "R53-T010",
        "exercise": "react",
        "config": config,
        "required_named_cases": REQUIRED_NAMED_CASES,
        "runner_script": str(runner_script.relative_to(root)),
        "hints_doc": str(hints_doc.relative_to(root)),
        "maintenance_doc": str(maint_doc.relative_to(root)),
        "scenarios_tested": ["real_reference", "fail_reference", "empty_tests"],
    }

    results_data = {
        "task": "R53-T010",
        "all_passed": all_passed,
        "test_count": {"passed": passed_count, "total": total_count},
        "named_cases_found": named_cases_found,
        "named_cases_missing": named_cases_missing,
        "checks": checks,
        "real_reference_exit": res_normal.returncode,
        "fail_reference_exit": res_fail.returncode,
        "empty_tests_exit": res_empty.returncode,
        "learner_hashes": {
            "stub_before": learner_hash_before,
            "stub_after": learner_hash_after,
            "spec_before": spec_hash_before,
            "spec_after": spec_hash_after,
        },
    }

    evidence_data = {
        "task": "R53-T010",
        "student": "Takshita Joshi",
        "enrollment": "E26B07F0582",
        "exercise": "react",
        "tool_versions": tool_versions,
        "checks": checks,
        "all_passed": all_passed,
        "test_output_summary": normal_output[:2000],
    }

    with open(inputs_path, "w", encoding="utf-8") as f:
        json.dump(inputs_data, f, indent=2)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f, indent=2)

    print("\nSummary of checks:")
    for c in checks:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"  [{status}] {c['name']}: {c['detail']}")

    if not all_passed:
        sys.exit(1)
    print("\nAll checks completed successfully!")


if __name__ == "__main__":
    main()
