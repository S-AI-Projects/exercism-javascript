import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_REL = os.path.join("exercises", "practice", "line-up")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

ANCHOR_CASES = [
    "format smallest non-exceptional ordinal numeral 4",
    "format greatest single digit non-exceptional ordinal numeral 9",
    "format non-exceptional ordinal numeral 5",
]


def run_jest_in_copy(solution_source: str, test_file: str, solution_file: str):
    with tempfile.TemporaryDirectory() as tmp_dir:
        dest_exercise = os.path.join(tmp_dir, "exercise")
        shutil.copytree(EXERCISE_DIR, dest_exercise, symlinks=True)

        temp_spec = os.path.join(dest_exercise, test_file)
        with open(temp_spec, "r", encoding="utf-8") as f:
            spec_text = f.read().replace("xtest(", "test(")
        with open(temp_spec, "w", encoding="utf-8") as f:
            f.write(spec_text)

        with open(os.path.join(dest_exercise, solution_file), "w", encoding="utf-8") as f:
            f.write(solution_source)

        root_nm = os.path.join(REPO_ROOT, "node_modules")
        dest_nm = os.path.join(dest_exercise, "node_modules")
        if os.path.exists(root_nm) and not os.path.exists(dest_nm):
            os.symlink(root_nm, dest_nm)

        env = os.environ.copy()
        env["CI"] = "true"
        local_jest = os.path.join(REPO_ROOT, "node_modules", ".bin", "jest")

        res = subprocess.run(
            [local_jest, "--watchAll=false", "--no-watchman", "--verbose"],
            cwd=dest_exercise,
            env=env,
            capture_output=True,
            text=True,
        )
        combined = res.stdout + "\n" + res.stderr
        passed_match = re.search(r"Tests:\s+(\d+)\s+passed", combined)
        passed_count = int(passed_match.group(1)) if passed_match else 0
        return res.returncode, combined, passed_count


def main():
    config_path = os.path.join(EXERCISE_DIR, ".meta", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = config["files"]["solution"][0]
    test_file = config["files"]["test"][0]
    example_file = config["files"]["example"][0]

    with open(os.path.join(EXERCISE_DIR, solution_file), "r", encoding="utf-8") as f:
        stub_content = f.read()
    if "Remove this line and implement the function" not in stub_content:
        raise AssertionError("Learner stub has been modified or solved in the working tree!")

    with open(os.path.join(EXERCISE_DIR, ".meta", "tests.toml"), "r", encoding="utf-8") as f:
        toml_content = f.read()
    canonical_uuids = re.findall(r"^\[([0-9a-f-]+)\]", toml_content, flags=re.MULTILINE)
    if len(canonical_uuids) == 0:
        raise AssertionError("No canonical UUIDs found in .meta/tests.toml")

    with open(os.path.join(EXERCISE_DIR, test_file), "r", encoding="utf-8") as f:
        spec_content = f.read()
    for anchor in ANCHOR_CASES:
        if anchor not in toml_content or anchor not in spec_content:
            raise AssertionError(f"Missing baseline anchor case: {anchor}")

    with open(os.path.join(EXERCISE_DIR, "package.json"), "r", encoding="utf-8") as f:
        ex_pkg = json.load(f)
    pkg_test_script = ex_pkg.get("scripts", {}).get("test", "corepack pnpm jest")

    example_rel_git = f"{EXERCISE_REL}/{example_file}".replace("\\", "/")
    head_res = subprocess.run(
        ["git", "show", f"HEAD:{example_rel_git}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if head_res.returncode != 0:
        raise AssertionError(f"Failed to read HEAD reference: {head_res.stderr}")
    before_ref = head_res.stdout

    with open(os.path.join(EXERCISE_DIR, example_file), "r", encoding="utf-8") as f:
        after_ref = f.read()

    if before_ref == after_ref:
        raise AssertionError("Refactored proof.ci.js is identical to HEAD; no refactor applied!")
    if "export const format" not in after_ref or "getSuffix" not in after_ref:
        raise AssertionError("Public API format or helper getSuffix missing in refactored proof.ci.js")

    before_code, before_out, before_passed = run_jest_in_copy(before_ref, test_file, solution_file)
    if before_code != 0 or before_passed == 0:
        raise AssertionError(f"Pre-refactor reference failed or ran zero tests:\n{before_out}")

    after_code, after_out, after_passed = run_jest_in_copy(after_ref, test_file, solution_file)
    if after_code != 0 or after_passed == 0:
        raise AssertionError(f"Post-refactor reference failed or ran zero tests:\n{after_out}")

    if before_passed != after_passed or after_passed != len(canonical_uuids):
        raise AssertionError(
            f"Test count mismatch: before={before_passed}, after={after_passed}, canonical={len(canonical_uuids)}"
        )

    for anchor in ANCHOR_CASES:
        if anchor not in after_out:
            raise AssertionError(f"Anchor case {anchor!r} did not appear in verbose Jest output!")

    diff_res = subprocess.run(
        ["git", "diff", example_rel_git],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    npm_v = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()

    report = {
        "task_id": "R53-T024",
        "exercise": "line-up",
        "package_json_test_script": pkg_test_script,
        "anchor_cases_verified": ANCHOR_CASES,
        "canonical_case_count": len(canonical_uuids),
        "before_refactor": {
            "exit_code": before_code,
            "executed_passed_tests": before_passed,
            "status": "PASSED",
        },
        "after_refactor": {
            "exit_code": after_code,
            "executed_passed_tests": after_passed,
            "status": "PASSED",
        },
        "behavioral_equivalence": "AGREED_ON_ALL_CASES",
        "learner_stub_status": "UNSOLVED",
        "tool_versions": {
            "node": node_v,
            "npm": npm_v,
            "python": sys.version.split()[0],
        },
        "status": "PASSED",
    }

    log_text = (
        "=== PRE-REFACTOR (HEAD) JEST RUN ===\n"
        + before_out
        + "\n=== POST-REFACTOR JEST RUN ===\n"
        + after_out
        + "\n=== GIT DIFF ===\n"
        + diff_res.stdout
    )

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(log_text)

    print("=== R53-T024 Reference Refactor Check Passed ===")
    print(f"Anchor cases verified: {ANCHOR_CASES}")
    print(f"Before refactor: PASSED ({before_passed}/{len(canonical_uuids)} tests)")
    print(f"After refactor:  PASSED ({after_passed}/{len(canonical_uuids)} tests)")
    print("Evidence saved in work/R53-T024/results.json and work/R53-T024/results.log")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
