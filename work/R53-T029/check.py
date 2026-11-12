import importlib.util
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_REL = os.path.join("exercises", "practice", "grade-school")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

NAMED_CASES = [
    "Roster is empty when no student is added",
    "Add a student",
    "Student is added to the roster",
]


def load_runner():
    runner_path = os.path.join(REPO_ROOT, "tools", "course_checks", "r53-t029.py")
    spec = importlib.util.spec_from_file_location("r53_t029_runner", runner_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def count_enabled_canonical_cases(toml_text: str) -> int:
    blocks = re.split(r"(?=^\[([0-9a-f-]+)\])", toml_text, flags=re.MULTILINE)
    enabled = 0
    for block in blocks:
        if not block.startswith("["):
            continue
        if "include = false" not in block:
            enabled += 1
    return enabled


def main():
    runner = load_runner()
    baseline_hashes = runner.hash_exercise_files(EXERCISE_DIR)

    # 1. Verify learner stub remains unsolved
    stub_path = os.path.join(EXERCISE_DIR, "grade-school.js")
    with open(stub_path, "r", encoding="utf-8") as f:
        stub_content = f.read()
    if "Remove this line and implement the function" not in stub_content:
        raise AssertionError("Learner stub has been modified or solved in the working tree!")

    # 2. Count enabled canonical cases in tests.toml
    with open(os.path.join(EXERCISE_DIR, ".meta", "tests.toml"), "r", encoding="utf-8") as f:
        toml_content = f.read()
    enabled_canonical_count = count_enabled_canonical_cases(toml_content)
    if enabled_canonical_count == 0:
        raise AssertionError("No enabled canonical cases found in .meta/tests.toml")

    # 3. Scenario A: Real reference must pass all enabled cases
    real_res = runner.run_isolated_suite(EXERCISE_DIR)
    if real_res["exit_code"] != 0 or real_res["executed_passed_tests"] != enabled_canonical_count:
        raise AssertionError(
            f"Expected {enabled_canonical_count} passed tests, got {real_res['executed_passed_tests']}"
        )
    for case_name in NAMED_CASES:
        if case_name not in real_res["output"]:
            raise AssertionError(f"Named case {case_name!r} missing from Jest verbose output!")
    hashes_after_real = runner.hash_exercise_files(EXERCISE_DIR)
    if baseline_hashes != hashes_after_real:
        raise AssertionError("Learner file hashes changed after real reference run!")

    # 4. Scenario B: Deliberately failing reference must fail non-zero
    failing_ref = (
        "export class GradeSchool {\n"
        "  roster() { return ['WrongStudent']; }\n"
        "  add() { return false; }\n"
        "  grade() { return []; }\n"
        "}\n"
    )
    try:
        runner.run_isolated_suite(EXERCISE_DIR, solution_override=failing_ref)
    except runner.RunnerError as err:
        failing_ref_msg = str(err).splitlines()[0]
    else:
        raise AssertionError("Deliberately failing reference unexpectedly passed!")
    hashes_after_fail = runner.hash_exercise_files(EXERCISE_DIR)
    if baseline_hashes != hashes_after_fail:
        raise AssertionError("Learner file hashes changed after failing reference run!")

    # 5. Scenario C: Empty test selection (zero-test run) must fail non-zero
    try:
        runner.run_isolated_suite(
            EXERCISE_DIR, test_name_pattern="__NONEXISTENT_TEST_PATTERN_R53_T029__"
        )
    except runner.RunnerError as err:
        zero_test_msg = str(err).splitlines()[0]
    else:
        raise AssertionError("Empty test selection (zero-test run) unexpectedly passed!")
    hashes_after_zero = runner.hash_exercise_files(EXERCISE_DIR)
    if baseline_hashes != hashes_after_zero:
        raise AssertionError("Learner file hashes changed after zero-test run!")

    node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    npm_v = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()

    report = {
        "task_id": "R53-T029",
        "exercise": "grade-school",
        "named_cases_verified": NAMED_CASES,
        "enabled_canonical_case_count": enabled_canonical_count,
        "scenarios": {
            "real_reference": {
                "exit_code": real_res["exit_code"],
                "executed_passed_tests": real_res["executed_passed_tests"],
                "hashes_unchanged": baseline_hashes == hashes_after_real,
                "status": "PASSED",
            },
            "deliberately_failing_reference": {
                "rejected_non_zero": True,
                "reason": failing_ref_msg,
                "hashes_unchanged": baseline_hashes == hashes_after_fail,
                "status": "FAILED_AS_EXPECTED",
            },
            "empty_test_selection": {
                "rejected_non_zero": True,
                "reason": zero_test_msg,
                "hashes_unchanged": baseline_hashes == hashes_after_zero,
                "status": "FAILED_AS_EXPECTED",
            },
        },
        "learner_stub_sha256": baseline_hashes["grade-school.js"],
        "learner_stub_status": "UNSOLVED",
        "tool_versions": {
            "node": node_v,
            "npm": npm_v,
            "python": sys.version.split()[0],
        },
        "status": "PASSED",
    }

    log_text = (
        "=== SCENARIO A: REAL REFERENCE JEST RUN ===\n"
        + real_res["output"]
        + "\n=== SCENARIO B & C: NEGATIVE RUNNER CHECKS ===\n"
        + json.dumps(report["scenarios"], indent=2)
    )

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(log_text)

    print("=== R53-T029 Isolated Runner Check Passed ===")
    print(f"Named cases verified: {NAMED_CASES}")
    print(f"Scenario A (Real Reference):      PASSED ({real_res['executed_passed_tests']}/{enabled_canonical_count} tests)")
    print(f"Scenario B (Failing Reference):   REJECTED NON-ZERO AS EXPECTED")
    print(f"Scenario C (Empty Test Selection): REJECTED NON-ZERO AS EXPECTED")
    print(f"Learner stub SHA-256 unchanged:   {baseline_hashes['grade-school.js']}")
    print("Evidence saved in work/R53-T029/results.json and work/R53-T029/results.log")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
