import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_REL = os.path.join("exercises", "practice", "grains")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

NAMED_CASES = [
    "grains on square 1",
    "grains on square 2",
    "grains on square 3",
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


def verify_micro_examples():
    node_code = """
const exact = (BigInt(2) ** BigInt(63)).toString();
const imprecise = (2 ** 63).toString();
let mixedThrew = false;
try {
  BigInt(2) ** 63;
} catch (err) {
  mixedThrew = err instanceof TypeError;
}
console.log(JSON.stringify({ exact, imprecise, mixedThrew }));
"""
    res = subprocess.run(["node", "-e", node_code], capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"Micro-example evaluation failed:\n{res.stderr}")
    data = json.loads(res.stdout.strip())
    if data["exact"] != "9223372036854775808":
        raise AssertionError(f"Unexpected BigInt micro-example output: {data['exact']}")
    if data["imprecise"] != "9223372036854776000":
        raise AssertionError(f"Unexpected Number pitfall output: {data['imprecise']}")
    if not data["mixedThrew"]:
        raise AssertionError("Expected BigInt(2) ** 63 to throw TypeError")
    return data


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
    for case_name in NAMED_CASES:
        if case_name not in spec_content:
            raise AssertionError(f"Missing required named case in spec: {case_name}")

    micro = verify_micro_examples()
    hints_path = os.path.join(EXERCISE_DIR, ".docs", "hints.md")
    if not os.path.exists(hints_path):
        raise AssertionError("exercises/practice/grains/.docs/hints.md does not exist!")
    with open(hints_path, "r", encoding="utf-8") as f:
        hints_content = f.read()

    if "export const square" in hints_content or "export const total" in hints_content:
        raise AssertionError("hints.md must not expose full solution exports!")
    if micro["exact"] not in hints_content or micro["imprecise"] not in hints_content:
        raise AssertionError("hints.md outputs do not match asserted micro-example outputs!")
    if "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/BigInt" not in hints_content:
        raise AssertionError("hints.md must link to MDN BigInt reference!")

    with open(os.path.join(EXERCISE_DIR, "package.json"), "r", encoding="utf-8") as f:
        ex_pkg = json.load(f)
    pkg_test_script = ex_pkg.get("scripts", {}).get("test", "corepack pnpm jest")

    with open(os.path.join(EXERCISE_DIR, example_file), "r", encoding="utf-8") as f:
        ref_source = f.read()

    if "BigInt(" not in ref_source:
        raise AssertionError("Expected BigInt construct in proof.ci.js")

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
        "task_id": "R53-T027",
        "exercise": "grains",
        "package_json_test_script": pkg_test_script,
        "selected_construct": "BigInt numeric coercion and arbitrary-precision exponentiation",
        "named_cases_verified": NAMED_CASES,
        "canonical_case_count": len(canonical_uuids),
        "jest_suite": {
            "exit_code": jest_code,
            "executed_passed_tests": jest_passed,
            "status": "PASSED",
        },
        "micro_examples": {
            "bigint_expression": "(BigInt(2) ** BigInt(63)).toString()",
            "bigint_expected": "9223372036854775808",
            "bigint_actual": micro["exact"],
            "pitfall_expression": "(2 ** 63).toString()",
            "pitfall_expected": "9223372036854776000",
            "pitfall_actual": micro["imprecise"],
            "mixed_type_throws_type_error": micro["mixedThrew"],
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
        "=== JEST SUITE RUN ===\n"
        + jest_out
        + "\n=== MICRO-EXAMPLE VERIFICATION ===\n"
        + json.dumps(report["micro_examples"], indent=2)
    )

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(log_text)

    print("=== R53-T027 Language-Specific Guidance Check Passed ===")
    print(f"Named cases verified: {NAMED_CASES}")
    print(f"Jest suite: PASSED ({jest_passed}/{len(canonical_uuids)} tests)")
    print(f"Micro-example (BigInt): (BigInt(2) ** BigInt(63)).toString() -> {micro['exact']}")
    print(f"Pitfall (Number):       (2 ** 63).toString() -> {micro['imprecise']}")
    print("Evidence saved in work/R53-T027/results.json and work/R53-T027/results.log")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
