import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_REL = os.path.join("exercises", "practice", "square-root")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

NAMED_CASES = [
    "root of 1",
    "root of 4",
    "root of 5",
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

    # 1. Verify learner stub remains unsolved
    with open(os.path.join(EXERCISE_DIR, solution_file), "r", encoding="utf-8") as f:
        stub_content = f.read()
    if "Remove this line and implement the function" not in stub_content:
        raise AssertionError("Learner stub has been modified or solved in the working tree!")

    # 2. Verify canonical cases in tests.toml and spec.js
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

    # 3. Verify hints.md content (worked example, trade-offs, no full solution export)
    hints_path = os.path.join(EXERCISE_DIR, ".docs", "hints.md")
    if not os.path.exists(hints_path):
        raise AssertionError("exercises/practice/square-root/.docs/hints.md does not exist!")
    with open(hints_path, "r", encoding="utf-8") as f:
        hints_content = f.read()
    if "export const squareRoot" in hints_content:
        raise AssertionError("hints.md must not contain a full solution listing!")
    if "Worked example" not in hints_content or "Trade-Offs" not in hints_content:
        raise AssertionError("hints.md must include a worked example and trade-offs section!")

    # 4. Read exercise package.json test script, reference, and alternative implementations
    with open(os.path.join(EXERCISE_DIR, "package.json"), "r", encoding="utf-8") as f:
        ex_pkg = json.load(f)
    pkg_test_script = ex_pkg.get("scripts", {}).get("test", "corepack pnpm jest")

    with open(os.path.join(EXERCISE_DIR, example_file), "r", encoding="utf-8") as f:
        ref_source = f.read()

    alt_path = os.path.join(WORK_DIR, "alternative.js")
    with open(alt_path, "r", encoding="utf-8") as f:
        alt_source = f.read()

    if ref_source.strip() == alt_source.strip():
        raise AssertionError("Alternative implementation must differ from proof.ci.js!")

    # 5. Execute Jest against both implementations
    ref_code, ref_out, ref_passed = run_jest_in_copy(ref_source, test_file, solution_file)
    if ref_code != 0 or ref_passed == 0:
        raise AssertionError(f"Reference implementation failed or ran zero tests:\n{ref_out}")

    alt_code, alt_out, alt_passed = run_jest_in_copy(alt_source, test_file, solution_file)
    if alt_code != 0 or alt_passed == 0:
        raise AssertionError(f"Alternative implementation failed or ran zero tests:\n{alt_out}")

    if ref_passed != alt_passed or ref_passed != len(canonical_uuids):
        raise AssertionError(
            f"Test count mismatch: ref={ref_passed}, alt={alt_passed}, canonical={len(canonical_uuids)}"
        )

    for case_name in NAMED_CASES:
        if case_name not in ref_out or case_name not in alt_out:
            raise AssertionError(f"Named case {case_name!r} missing from Jest verbose output!")

    node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    npm_v = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()

    report = {
        "task_id": "R53-T026",
        "exercise": "square-root",
        "package_json_test_script": pkg_test_script,
        "named_cases_verified": NAMED_CASES,
        "canonical_case_count": len(canonical_uuids),
        "reference_bitwise_base2": {
            "exit_code": ref_code,
            "executed_passed_tests": ref_passed,
            "status": "PASSED",
        },
        "alternative_binary_search": {
            "exit_code": alt_code,
            "executed_passed_tests": alt_passed,
            "status": "PASSED",
        },
        "behavioral_agreement": "AGREED_ON_ALL_CANONICAL_CASES",
        "learner_stub_status": "UNSOLVED",
        "tool_versions": {
            "node": node_v,
            "npm": npm_v,
            "python": sys.version.split()[0],
        },
        "status": "PASSED",
    }

    log_text = (
        "=== REFERENCE (BITWISE BASE-2) JEST RUN ===\n"
        + ref_out
        + "\n=== ALTERNATIVE (INTERVAL BINARY SEARCH) JEST RUN ===\n"
        + alt_out
    )

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(log_text)

    print("=== R53-T026 Implementation Comparison Check Passed ===")
    print(f"Named cases verified: {NAMED_CASES}")
    print(f"Reference (Bitwise Base-2):        PASSED ({ref_passed}/{len(canonical_uuids)} tests)")
    print(f"Alternative (Interval Binary Search): PASSED ({alt_passed}/{len(canonical_uuids)} tests)")
    print("Evidence saved in work/R53-T026/results.json and work/R53-T026/results.log")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
