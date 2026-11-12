import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_REL = os.path.join("exercises", "practice", "hello-world")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

REJECTING_TEST_ID = "af9ffe10-dc13-42d8-a742-e7bdafac449d"
REJECTING_TEST_NAME = "Say Hi!"


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
            [local_jest, "--watchAll=false", "--no-watchman"],
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
    if "Goodbye, Mars!" not in stub_content or "Hello, World!" in stub_content:
        raise AssertionError("Learner stub has been modified or solved in the working tree!")

    with open(os.path.join(EXERCISE_DIR, ".meta", "tests.toml"), "r", encoding="utf-8") as f:
        toml_content = f.read()
    if REJECTING_TEST_ID not in toml_content or REJECTING_TEST_NAME not in toml_content:
        raise AssertionError("Expected canonical test ID/name missing from .meta/tests.toml")

    with open(os.path.join(EXERCISE_DIR, test_file), "r", encoding="utf-8") as f:
        spec_content = f.read()
    if REJECTING_TEST_NAME not in spec_content:
        raise AssertionError("Expected test name missing from hello-world.spec.js")

    with open(os.path.join(EXERCISE_DIR, "package.json"), "r", encoding="utf-8") as f:
        ex_pkg = json.load(f)
    pkg_test_script = ex_pkg.get("scripts", {}).get("test", "corepack pnpm jest")

    with open(os.path.join(EXERCISE_DIR, example_file), "r", encoding="utf-8") as f:
        original_ref = f.read()

    orig_code, orig_out, orig_passed = run_jest_in_copy(original_ref, test_file, solution_file)
    if orig_code != 0 or orig_passed == 0:
        raise AssertionError(f"Original reference failed or ran zero tests:\n{orig_out}")

    mutant_ref = original_ref.replace("Hello, World!", "Hello, World")
    if mutant_ref == original_ref:
        raise AssertionError("Mutant transformation did not alter the reference implementation!")

    mut_code, mut_out, mut_passed = run_jest_in_copy(mutant_ref, test_file, solution_file)
    if mut_code == 0 or mut_passed != 0:
        raise AssertionError("Mutant was NOT rejected by the test suite!")
    if REJECTING_TEST_NAME not in mut_out:
        raise AssertionError(f"Mutant failure output did not identify rejecting test {REJECTING_TEST_NAME!r}")

    node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    npm_v = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()

    report = {
        "task_id": "R53-T023",
        "exercise": "hello-world",
        "package_json_test_script": pkg_test_script,
        "minimal_input": "hello()",
        "expected_output": "Hello, World!",
        "mutant_output": "Hello, World",
        "rejecting_test_id": REJECTING_TEST_ID,
        "rejecting_test_name": REJECTING_TEST_NAME,
        "original_reference": {
            "exit_code": orig_code,
            "executed_passed_tests": orig_passed,
            "status": "PASSED",
        },
        "mutated_reference": {
            "exit_code": mut_code,
            "executed_passed_tests": mut_passed,
            "status": "REJECTED_AS_EXPECTED",
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
        "=== ORIGINAL REFERENCE RUN ===\n"
        + orig_out
        + "\n=== MUTATED REFERENCE RUN ===\n"
        + mut_out
    )

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(log_text)

    print("=== R53-T023 Mutation Regression Check Passed ===")
    print(f"Original reference: PASSED ({orig_passed} test executed & passed)")
    print(f"Mutated reference ('Hello, World'): REJECTED by '{REJECTING_TEST_NAME}' ({REJECTING_TEST_ID})")
    print("Evidence saved in work/R53-T023/results.json and work/R53-T023/results.log")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
