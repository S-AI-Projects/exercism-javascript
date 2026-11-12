import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_REL = os.path.join("exercises", "practice", "split-second-stopwatch")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

NAMED_CASES = [
    "new stopwatch starts in ready state",
    "new stopwatch's current lap has no elapsed time",
    "new stopwatch's total has no elapsed time",
]


def load_course_checker():
    checker_path = os.path.join(REPO_ROOT, "tools", "course_checks", "r53-t028.py")
    spec = importlib.util.spec_from_file_location("r53_t028_checker", checker_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    checker = load_course_checker()
    valid_meta = checker.validate_exercise_metadata(EXERCISE_DIR)
    negative_results = checker.run_negative_fixtures(EXERCISE_DIR)

    solution_file = valid_meta["roles"]["solution"][0]["resolved"]
    test_file = valid_meta["roles"]["test"][0]["resolved"]
    example_file = valid_meta["roles"]["example"][0]["resolved"]

    with open(os.path.join(EXERCISE_DIR, solution_file), "r", encoding="utf-8") as f:
        stub_content = f.read()
    if "Remove this line and implement the function" not in stub_content:
        raise AssertionError("Learner stub has been modified or solved in the working tree!")

    maint_doc = os.path.join(REPO_ROOT, "docs", "maintenance", "split-second-stopwatch.md")
    if not os.path.isfile(maint_doc):
        raise AssertionError("docs/maintenance/split-second-stopwatch.md does not exist!")
    with open(maint_doc, "r", encoding="utf-8") as f:
        doc_text = f.read()
    for required_token in (
        "split-second-stopwatch.js",
        "split-second-stopwatch.spec.js",
        ".meta/proof.ci.js",
        ".meta/tests.toml",
        "configlet sync",
    ):
        if required_token not in doc_text:
            raise AssertionError(f"Maintenance doc missing expected reference: {required_token}")

    with open(os.path.join(EXERCISE_DIR, ".meta", "tests.toml"), "r", encoding="utf-8") as f:
        toml_content = f.read()
    canonical_uuids = re.findall(r"^\[([0-9a-f-]+)\]", toml_content, flags=re.MULTILINE)
    if len(canonical_uuids) == 0:
        raise AssertionError("No canonical UUIDs found in .meta/tests.toml")

    with open(os.path.join(EXERCISE_DIR, test_file), "r", encoding="utf-8") as f:
        spec_content = f.read()
    for case_name in NAMED_CASES:
        if case_name not in spec_content:
            raise AssertionError(f"Missing required named case in spec: {case_name}")

    with open(os.path.join(EXERCISE_DIR, "package.json"), "r", encoding="utf-8") as f:
        ex_pkg = json.load(f)
    pkg_test_script = ex_pkg.get("scripts", {}).get("test", "corepack pnpm jest")

    with open(os.path.join(EXERCISE_DIR, example_file), "r", encoding="utf-8") as f:
        ref_source = f.read()

    jest_code, jest_out, jest_passed = run_jest_in_copy(ref_source, test_file, solution_file)
    if jest_code != 0 or jest_passed == 0:
        raise AssertionError(f"Reference implementation failed or ran zero tests:\n{jest_out}")
    if jest_passed != len(canonical_uuids):
        raise AssertionError(f"Expected {len(canonical_uuids)} passed tests, got {jest_passed}")
    for case_name in NAMED_CASES:
        if case_name not in jest_out:
            raise AssertionError(f"Named case {case_name!r} missing from Jest verbose output!")

    node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    npm_v = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()

    report = {
        "task_id": "R53-T028",
        "exercise": "split-second-stopwatch",
        "package_json_test_script": pkg_test_script,
        "valid_metadata": valid_meta,
        "negative_fixtures": negative_results,
        "named_cases_verified": NAMED_CASES,
        "canonical_case_count": len(canonical_uuids),
        "jest_suite": {
            "exit_code": jest_code,
            "executed_passed_tests": jest_passed,
            "status": "PASSED",
        },
        "learner_stub_status": "UNSOLVED",
        "tool_versions": {
            "node": node_v,
            "npm": npm_v,
            "python": sys.version.split()[0],
        },
        "status": "PASSED",
    }

    log_text = (
        "=== METADATA & NEGATIVE FIXTURE CHECK ===\n"
        + json.dumps({"valid_metadata": valid_meta, "negative_fixtures": negative_results}, indent=2)
        + "\n=== JEST SUITE RUN ===\n"
        + jest_out
    )

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(log_text)

    print("=== R53-T028 Maintained File Map & Metadata Check Passed ===")
    print(f"Real metadata: VALID ({valid_meta['exercise_dir']})")
    print(f"Negative fixtures rejected: {[f['fixture'] for f in negative_results]}")
    print(f"Named cases verified: {NAMED_CASES}")
    print(f"Jest suite: PASSED ({jest_passed}/{len(canonical_uuids)} tests)")
    print("Evidence saved in work/R53-T028/results.json and work/R53-T028/results.log")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
