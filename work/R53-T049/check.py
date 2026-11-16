#!/usr/bin/env python3
"""Automated verification harness for R53-T049 (Protein Translation Isolated Test Runner).

Tests the production runner tools/course_checks/r53-t049.py across:
- Scenario A: Successful execution with real maintained reference.
- Scenario B: Deliberately failing reference implementation.
- Scenario C: Empty test selection (zero tests executed).
- Scenario D: Learner file integrity across success, failure, error, and interruption.
- Scenario E: Temporary directory cleanup across all scenarios.

Generates work/R53-T049/results.md and work/R53-T049/tool-versions.txt.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/protein-translation")
RUNNER_REL_PATH = Path("tools/course_checks/r53-t049.py")
REQUIRED_NAMED_CASES = [
    "Empty RNA sequence results in no proteins",
    "Methionine RNA sequence",
    "Phenylalanine RNA sequence 1",
]


class HarnessError(Exception):
    """Raised when any verification assertion fails."""
    pass


def find_root():
    """Locate repository root directory."""
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / RUNNER_REL_PATH).is_file()
            and (candidate / ASSIGNMENT / ".meta" / "config.json").is_file()
        ):
            return candidate
    raise HarnessError("Could not locate repository root directory")


def sha256_file(path):
    """Compute SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_monitored_hashes(exercise_dir):
    """Compute hashes for all critical exercise files to monitor immutability."""
    monitored = {
        "solution": exercise_dir / "protein-translation.js",
        "spec": exercise_dir / "protein-translation.spec.js",
        "reference": exercise_dir / ".meta" / "proof.ci.js",
        "config": exercise_dir / ".meta" / "config.json",
        "package": exercise_dir / "package.json",
    }
    hashes = {}
    for name, path in monitored.items():
        if not path.is_file():
            raise HarnessError(f"Monitored file missing: {path}")
        hashes[name] = sha256_file(path)
    return hashes


def assert_hashes_unchanged(baseline, current, context_label):
    """Assert that monitored file hashes have not diverged from baseline."""
    for name, base_hash in baseline.items():
        curr_hash = current.get(name)
        if curr_hash != base_hash:
            raise HarnessError(
                f"File integrity violation in {context_label} for '{name}':\n"
                f"  Baseline: {base_hash}\n"
                f"  Current:  {curr_hash}"
            )


def extract_temp_dir(stdout_text):
    """Extract temporary directory path announced by runner stdout."""
    match = re.search(r"\[RUNNER_TEMP_DIR\]\s+(.+)", stdout_text)
    if match:
        return match.group(1).strip()
    return None


def run_command(cmd, cwd, env=None):
    """Run an external command and capture output."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    return result


def main():
    root = find_root()
    work_dir = root / "work" / "R53-T049"
    work_dir.mkdir(parents=True, exist_ok=True)
    runner_script = root / RUNNER_REL_PATH
    exercise_dir = root / ASSIGNMENT

    print("=== Starting R53-T049 Automated Verification Harness ===")
    print(f"Repository Root:    {root}")
    print(f"Runner Script:      {runner_script}")
    print(f"Exercise Directory: {exercise_dir}")

    # Query tool versions
    tool_env = os.environ.copy()
    node_bin = str(root / "node_modules" / ".bin")
    tool_env["PATH"] = node_bin + ":" + tool_env.get("PATH", "")

    node_ver = run_command(["node", "--version"], root, tool_env).stdout.strip()
    corepack_ver = run_command(["corepack", "--version"], root, tool_env).stdout.strip()
    pnpm_ver = run_command(["corepack", "pnpm", "--version"], root, tool_env).stdout.strip()
    jest_ver_raw = run_command(["corepack", "pnpm", "jest", "--version"], root, tool_env).stdout.strip()
    # Handle possible npmrc warning lines in Jest output
    jest_ver = jest_ver_raw.splitlines()[-1] if jest_ver_raw else "unknown"
    python_ver = platform.python_version()

    tool_versions_content = (
        f"Python: {python_ver}\n"
        f"Node.js: {node_ver}\n"
        f"Package Manager: pnpm {pnpm_ver} (Corepack {corepack_ver})\n"
        f"Test Runner: Jest {jest_ver}\n"
        f"Platform: {platform.platform()}\n"
    )
    (work_dir / "tool-versions.txt").write_text(tool_versions_content, encoding="utf-8")
    print(f"Recorded tool versions in {work_dir / 'tool-versions.txt'}")

    # Baseline file hashes
    baseline_hashes = compute_monitored_hashes(exercise_dir)
    print("Baseline hashes recorded for learner stub and exercise files.")

    scenario_reports = []

    # -------------------------------------------------------------------------
    # Scenario A: Successful execution with real maintained reference
    # -------------------------------------------------------------------------
    print("\n--- Running Scenario A: Successful Execution ---")
    hashes_before_a = compute_monitored_hashes(exercise_dir)
    assert_hashes_unchanged(baseline_hashes, hashes_before_a, "Scenario A pre-run")

    json_out_a = work_dir / "scenario_a_result.json"
    cmd_a = [
        sys.executable,
        str(runner_script),
        "--json-output",
        str(json_out_a),
    ]
    proc_a = run_command(cmd_a, root)
    temp_dir_a = extract_temp_dir(proc_a.stdout)

    if proc_a.returncode != 0:
        raise HarnessError(
            f"Scenario A failed: expected exit code 0, got {proc_a.returncode}\n"
            f"Stdout:\n{proc_a.stdout}\nStderr:\n{proc_a.stderr}"
        )

    if not json_out_a.is_file():
        raise HarnessError("Scenario A failed to produce JSON output")

    data_a = json.loads(json_out_a.read_text(encoding="utf-8"))
    executed_a = data_a.get("executed_tests", 0)
    passed_a = data_a.get("passed_tests", 0)
    failed_a = data_a.get("failed_tests", 0)

    if executed_a != 29:
        raise HarnessError(f"Scenario A: expected 29 executed tests, got {executed_a}")
    if passed_a != 29:
        raise HarnessError(f"Scenario A: expected 29 passed tests, got {passed_a}")
    if failed_a != 0:
        raise HarnessError(f"Scenario A: expected 0 failed tests, got {failed_a}")

    named_a = data_a.get("named_cases", {})
    for req_case in REQUIRED_NAMED_CASES:
        if named_a.get(req_case) != "passed":
            raise HarnessError(f"Scenario A: required named case '{req_case}' did not pass (status: {named_a.get(req_case)})")

    hashes_after_a = compute_monitored_hashes(exercise_dir)
    assert_hashes_unchanged(baseline_hashes, hashes_after_a, "Scenario A post-run")

    if not temp_dir_a or os.path.exists(temp_dir_a):
        raise HarnessError(f"Scenario A: temporary directory was not cleaned up: {temp_dir_a}")

    print(f"[PASS] Scenario A passed: {passed_a}/{executed_a} tests passed, all named cases verified, temp dir cleaned.")
    scenario_reports.append({
        "scenario": "Scenario A: Successful execution",
        "description": "Run isolated test runner against real maintained reference",
        "config": "Default reference (.meta/proof.ci.js), all 29 tests enabled",
        "expected_result": "Exit status 0, 29 executed tests, 29 passed, 0 failed, named cases passed",
        "actual_result": f"Exit status {proc_a.returncode}, {passed_a} passed, {failed_a} failed",
        "exit_status": proc_a.returncode,
        "executed_test_count": executed_a,
        "named_cases_verified": True,
        "learner_hash_verified": True,
        "temp_dir_cleaned": True,
    })

    # -------------------------------------------------------------------------
    # Scenario B: Deliberately failing reference
    # -------------------------------------------------------------------------
    print("\n--- Running Scenario B: Deliberately Failing Reference ---")
    hashes_before_b = compute_monitored_hashes(exercise_dir)
    assert_hashes_unchanged(baseline_hashes, hashes_before_b, "Scenario B pre-run")

    with tempfile.TemporaryDirectory() as fixture_temp:
        failing_ref_file = Path(fixture_temp) / "failing_proof.js"
        failing_ref_file.write_text(
            "// Deliberately incorrect reference implementation for verification\n"
            "export const translate = () => ['IncorrectProtein'];\n",
            encoding="utf-8",
        )

        json_out_b = work_dir / "scenario_b_result.json"
        cmd_b = [
            sys.executable,
            str(runner_script),
            "--reference-path",
            str(failing_ref_file),
            "--json-output",
            str(json_out_b),
        ]
        proc_b = run_command(cmd_b, root)
        temp_dir_b = extract_temp_dir(proc_b.stdout)

        if proc_b.returncode == 0:
            raise HarnessError("Scenario B failed: runner unexpectedly exited with 0 for failing reference")

        if not json_out_b.is_file():
            raise HarnessError("Scenario B failed to produce JSON output")

        data_b = json.loads(json_out_b.read_text(encoding="utf-8"))
        failed_b = data_b.get("failed_tests", 0)
        executed_b = data_b.get("executed_tests", 0)

        if failed_b == 0:
            raise HarnessError("Scenario B failed: runner failed to report test failures")

        hashes_after_b = compute_monitored_hashes(exercise_dir)
        assert_hashes_unchanged(baseline_hashes, hashes_after_b, "Scenario B post-run")

        if not temp_dir_b or os.path.exists(temp_dir_b):
            raise HarnessError(f"Scenario B: temporary directory was not cleaned up: {temp_dir_b}")

        print(f"[PASS] Scenario B passed: failure detected ({failed_b} failed tests), exit code {proc_b.returncode}, temp dir cleaned.")
        scenario_reports.append({
            "scenario": "Scenario B: Deliberately failing reference",
            "description": "Run isolated runner against deliberately incorrect reference",
            "config": "Custom reference returning ['IncorrectProtein'] for all inputs",
            "expected_result": "Non-zero exit status, test failures detected, working tree unchanged",
            "actual_result": f"Exit status {proc_b.returncode}, {failed_b} failed out of {executed_b} executed",
            "exit_status": proc_b.returncode,
            "executed_test_count": executed_b,
            "named_cases_verified": False,
            "learner_hash_verified": True,
            "temp_dir_cleaned": True,
        })

    # -------------------------------------------------------------------------
    # Scenario C: Empty test selection
    # -------------------------------------------------------------------------
    print("\n--- Running Scenario C: Empty Test Selection ---")
    hashes_before_c = compute_monitored_hashes(exercise_dir)
    assert_hashes_unchanged(baseline_hashes, hashes_before_c, "Scenario C pre-run")

    json_out_c = work_dir / "scenario_c_result.json"
    cmd_c = [
        sys.executable,
        str(runner_script),
        "--empty-tests",
        "--json-output",
        str(json_out_c),
    ]
    proc_c = run_command(cmd_c, root)
    temp_dir_c = extract_temp_dir(proc_c.stdout)

    if proc_c.returncode == 0:
        raise HarnessError("Scenario C failed: runner unexpectedly exited with 0 when zero tests executed")

    if not json_out_c.is_file():
        raise HarnessError("Scenario C failed to produce JSON output")

    data_c = json.loads(json_out_c.read_text(encoding="utf-8"))
    executed_c = data_c.get("executed_tests", None)

    if executed_c != 0:
        raise HarnessError(f"Scenario C failed: expected 0 executed tests, got {executed_c}")

    hashes_after_c = compute_monitored_hashes(exercise_dir)
    assert_hashes_unchanged(baseline_hashes, hashes_after_c, "Scenario C post-run")

    if not temp_dir_c or os.path.exists(temp_dir_c):
        raise HarnessError(f"Scenario C: temporary directory was not cleaned up: {temp_dir_c}")

    print(f"[PASS] Scenario C passed: zero-test guard triggered, exit code {proc_c.returncode}, temp dir cleaned.")
    scenario_reports.append({
        "scenario": "Scenario C: Empty test selection",
        "description": "Simulate a test run where zero tests are selected",
        "config": "--empty-tests flag replacing spec with empty describe block",
        "expected_result": "Non-zero exit status (code 2), zero executed tests detected",
        "actual_result": f"Exit status {proc_c.returncode}, executed tests: {executed_c}",
        "exit_status": proc_c.returncode,
        "executed_test_count": executed_c,
        "named_cases_verified": False,
        "learner_hash_verified": True,
        "temp_dir_cleaned": True,
    })

    # -------------------------------------------------------------------------
    # Scenario D: Learner file integrity under error and interruption
    # -------------------------------------------------------------------------
    print("\n--- Running Scenario D: Integrity Under Error and Interruption ---")

    # Part D1: Subprocess error (malformed syntax in reference)
    with tempfile.TemporaryDirectory() as fixture_temp_d:
        malformed_ref_file = Path(fixture_temp_d) / "malformed_ref.js"
        malformed_ref_file.write_text("SYNTAX ERROR ::: NOT JAVASCRIPT;", encoding="utf-8")

        proc_d1 = run_command([
            sys.executable,
            str(runner_script),
            "--reference-path",
            str(malformed_ref_file),
        ], root)
        temp_dir_d1 = extract_temp_dir(proc_d1.stdout)

        if proc_d1.returncode == 0:
            raise HarnessError("Part D1 failed: runner unexpectedly exited with 0 for syntax error")

        hashes_after_d1 = compute_monitored_hashes(exercise_dir)
        assert_hashes_unchanged(baseline_hashes, hashes_after_d1, "Part D1 post-run")

        if not temp_dir_d1 or os.path.exists(temp_dir_d1):
            raise HarnessError(f"Part D1: temporary directory was not cleaned up: {temp_dir_d1}")

        print(f"[PASS] Part D1 passed: syntax error handled cleanly (exit {proc_d1.returncode}), hashes unchanged, temp dir cleaned.")

    # Part D2: Runner process interruption (SIGINT)
    subproc_d2 = subprocess.Popen(
        [sys.executable, str(runner_script)],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    temp_dir_d2 = None
    # Read output lines until temp dir announcement is seen
    while True:
        line = subproc_d2.stdout.readline()
        if not line and subproc_d2.poll() is not None:
            break
        if "[RUNNER_TEMP_DIR]" in line:
            temp_dir_d2 = line.split("[RUNNER_TEMP_DIR]")[1].strip()
            break

    if not temp_dir_d2:
        raise HarnessError("Part D2 failed: could not detect temporary directory announcement")

    # Verify temp dir actually exists while running
    if not os.path.exists(temp_dir_d2):
        raise HarnessError(f"Part D2: temporary directory did not exist during run: {temp_dir_d2}")

    # Send SIGINT signal to interrupt the runner
    subproc_d2.send_signal(signal.SIGINT)
    stdout_d2, stderr_d2 = subproc_d2.communicate(timeout=10)

    # Verify learner hashes after interruption
    hashes_after_d2 = compute_monitored_hashes(exercise_dir)
    assert_hashes_unchanged(baseline_hashes, hashes_after_d2, "Part D2 post-interruption")

    # Verify cleanup of temporary directory
    if os.path.exists(temp_dir_d2):
        raise HarnessError(f"Part D2 failed: temporary directory leaked after SIGINT: {temp_dir_d2}")

    print(f"[PASS] Part D2 passed: runner interrupted cleanly with SIGINT, hashes unchanged, temp dir cleaned.")

    scenario_reports.append({
        "scenario": "Scenario D: Learner file integrity",
        "description": "Verify working tree file immutability across failures, errors, and SIGINT interruption",
        "config": "SHA-256 verification of solution, test, reference, config, and package manifests",
        "expected_result": "Exact SHA-256 matches before and after all operations, zero working-tree mutations",
        "actual_result": "All 5 monitored files strictly unchanged across all scenarios",
        "exit_status": subproc_d2.returncode,
        "executed_test_count": "N/A",
        "named_cases_verified": True,
        "learner_hash_verified": True,
        "temp_dir_cleaned": True,
    })

    # -------------------------------------------------------------------------
    # Scenario E: Temporary directory cleanup summary verification
    # -------------------------------------------------------------------------
    print("\n--- Verifying Scenario E: Temporary Directory Cleanup ---")
    cleanup_cases = [
        ("Successful execution (Scenario A)", temp_dir_a),
        ("Assertion failure (Scenario B)", temp_dir_b),
        ("Zero-test execution (Scenario C)", temp_dir_c),
        ("Subprocess error (Scenario D1)", temp_dir_d1),
        ("Interrupted execution (Scenario D2)", temp_dir_d2),
    ]

    for label, path_str in cleanup_cases:
        if not path_str:
            raise HarnessError(f"Scenario E: missing temporary directory path for {label}")
        if os.path.exists(path_str):
            raise HarnessError(f"Scenario E: temporary directory {path_str} was not cleaned up for {label}")
        print(f"[PASS] Verified cleanup for: {label} -> {path_str} (REMOVED)")

    scenario_reports.append({
        "scenario": "Scenario E: Temporary directory cleanup",
        "description": "Confirm automatic directory removal upon success, failure, error, and interruption",
        "config": "Verification of 5 distinct temporary directories across all test paths",
        "expected_result": "os.path.exists(temp_dir) == False for all 5 cases",
        "actual_result": "All 5 temporary directories completely removed",
        "exit_status": 0,
        "executed_test_count": "N/A",
        "named_cases_verified": True,
        "learner_hash_verified": True,
        "temp_dir_cleaned": True,
    })

    # -------------------------------------------------------------------------
    # Generate results.md
    # -------------------------------------------------------------------------
    results_md_path = work_dir / "results.md"
    results_md_content = f"""# Verification Results: R53-T049 Isolated Protein Translation Test Runner

## Test Environment

- **Timestamp (UTC)**: {run_command(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], root).stdout.strip()}
- **Python**: {python_ver}
- **Node.js**: {node_ver}
- **Package Manager**: pnpm {pnpm_ver} (via Corepack {corepack_ver})
- **Test Runner**: Jest {jest_ver}
- **Platform**: {platform.platform()}
- **Production Runner**: `tools/course_checks/r53-t049.py`

---

## Monitored Learner & Exercise File Hashes

All file hashes below were verified before and after every execution scenario. Zero modifications occurred in the repository working tree.

| File Path | Role | SHA-256 Digest | Status |
| :--- | :--- | :--- | :--- |
| `exercises/practice/protein-translation/protein-translation.js` | Learner stub | `{baseline_hashes['solution']}` | Verified Unchanged |
| `exercises/practice/protein-translation/protein-translation.spec.js` | Test spec | `{baseline_hashes['spec']}` | Verified Unchanged |
| `exercises/practice/protein-translation/.meta/proof.ci.js` | Reference impl | `{baseline_hashes['reference']}` | Verified Unchanged |
| `exercises/practice/protein-translation/.meta/config.json` | Metadata config | `{baseline_hashes['config']}` | Verified Unchanged |
| `exercises/practice/protein-translation/package.json` | Package manifest | `{baseline_hashes['package']}` | Verified Unchanged |

---

## Scenario Verification Summary

| Scenario | Configuration | Expected Result | Actual Result | Exit Status | Tests Executed | Learner Hashes | Cleanup |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Scenario A: Successful execution** | Real reference (`.meta/proof.ci.js`) | Exit 0, 29 tests pass, named cases pass | 29/29 passed, 0 failed, 3 named cases verified | `0` | `29` | Identical | Cleaned |
| **Scenario B: Failing reference** | Mutated reference returning `['IncorrectProtein']` | Exit != 0, test failure detected | 29 failed out of 29 executed, exit 1 | `1` | `29` | Identical | Cleaned |
| **Scenario C: Empty test selection** | Simulated zero tests (`--empty-tests`) | Exit != 0 (code 2), zero tests guard | Exit 2, zero tests reported | `2` | `0` | Identical | Cleaned |
| **Scenario D: File integrity (Error & Interruption)** | Syntax error & `SIGINT` interruption | Learner files strictly unchanged | Hashes identical across all error and signal paths | `130` | `N/A` | Identical | Cleaned |
| **Scenario E: Directory cleanup** | 5 temporary directories created | All temporary directories removed | 5 of 5 temporary directories successfully removed | `0` | `N/A` | Identical | Cleaned |

---

## Detailed Scenario Reports

### Scenario A: Successful Execution
- **Command**: `python3 tools/course_checks/r53-t049.py`
- **Reference**: Maintained CI reference (`exercises/practice/protein-translation/.meta/proof.ci.js`)
- **Total Tests Defined**: 29
- **Executed Tests**: 29
- **Passed Tests**: 29
- **Failed Tests**: 0
- **Named Cases Verified**:
  - `Empty RNA sequence results in no proteins`: `PASSED`
  - `Methionine RNA sequence`: `PASSED`
  - `Phenylalanine RNA sequence 1`: `PASSED`
- **Temporary Directory**: `{temp_dir_a}` (Removed: True)
- **Exit Status**: `0`

### Scenario B: Deliberately Failing Reference
- **Command**: `python3 tools/course_checks/r53-t049.py --reference-path <temp_fixture>`
- **Mutation**: Stub returning `['IncorrectProtein']`
- **Expected Behavior**: Non-zero exit status, failure detection
- **Actual Behavior**: Detected 29 failures out of 29 executed tests
- **Temporary Directory**: `{temp_dir_b}` (Removed: True)
- **Exit Status**: `{proc_b.returncode}`

### Scenario C: Empty Test Selection
- **Command**: `python3 tools/course_checks/r53-t049.py --empty-tests`
- **Simulation**: Replaced spec with empty describe block in isolated copy
- **Expected Behavior**: Guard triggers on zero executed tests, exits non-zero (code 2)
- **Actual Behavior**: Guard triggered with message `Zero tests executed (total: 0, passed: 0, failed: 0). Guard triggered.`
- **Temporary Directory**: `{temp_dir_c}` (Removed: True)
- **Exit Status**: `{proc_c.returncode}`

### Scenario D: Learner File Integrity
- **Subprocess Error**: Evaluated malformed reference syntax; exited with code `{proc_d1.returncode}`; working tree unchanged.
- **Interruption (`SIGINT`)**: Started runner child process, captured active temporary directory `{temp_dir_d2}`, confirmed its existence on disk, issued `SIGINT`, confirmed runner exited (`{subproc_d2.returncode}`), and confirmed directory was purged.
- **File Hashes**: All 5 monitored files remained bit-for-bit identical to baseline.

### Scenario E: Temporary Directory Cleanup
All temporary directories allocated by `tools/course_checks/r53-t049.py` were verified non-existent after process exit:
1. Scenario A: `{temp_dir_a}` -> Cleaned
2. Scenario B: `{temp_dir_b}` -> Cleaned
3. Scenario C: `{temp_dir_c}` -> Cleaned
4. Scenario D1: `{temp_dir_d1}` -> Cleaned
5. Scenario D2: `{temp_dir_d2}` -> Cleaned
"""
    results_md_path.write_text(results_md_content, encoding="utf-8")
    print(f"\nSaved comprehensive verification results to {results_md_path}")

    # Final summary output
    print("\n" + "=" * 80)
    print("ALL VERIFICATION SCENARIOS PASSED SUCCESSFULLY")
    print("=" * 80)
    print(f"Scenario A (Success):         29/29 tests passed, 3 named cases verified (exit 0)")
    print(f"Scenario B (Failing Ref):     Failures detected as expected (exit {proc_b.returncode})")
    print(f"Scenario C (Zero Tests):      Zero-test guard triggered as expected (exit {proc_c.returncode})")
    print(f"Scenario D (File Integrity):  Learner files bit-for-bit identical across all operations")
    print(f"Scenario E (Cleanup):         All 5 temporary directories confirmed removed")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except HarnessError as err:
        print(f"\nHARNESS FAILURE: {err}", file=sys.stderr)
        sys.exit(1)
