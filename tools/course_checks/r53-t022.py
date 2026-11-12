import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXERCISE_REL = os.path.join("exercises", "practice", "parallel-letter-frequency")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

ANCHOR_CASES = [
    "no texts",
    "one text with one letter",
    "one text with multiple letters",
]


def normalize_timestamps(text: str) -> str:
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?", "<TIMESTAMP>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "<TIMESTAMP>", text)
    return text


def run_sync_in_temp_repo(temp_root: str) -> str:
    shutil.copytree(EXERCISE_DIR, os.path.join(temp_root, EXERCISE_REL), symlinks=True)
    shutil.copytree(os.path.join(REPO_ROOT, "scripts"), os.path.join(temp_root, "scripts"), symlinks=True)

    root_files = [
        "package.json",
        "exercise-package.json",
        ".npmrc",
        "babel.config.js",
        "eslint.config.mjs",
        "jest.config.js",
        "LICENSE",
        ".gitignore",
    ]
    for rf in root_files:
        src = os.path.join(REPO_ROOT, rf)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(temp_root, rf))

    root_nm = os.path.join(REPO_ROOT, "node_modules")
    if os.path.exists(root_nm):
        os.symlink(root_nm, os.path.join(temp_root, "node_modules"))

    env = os.environ.copy()
    env["ASSIGNMENT"] = "practice/parallel-letter-frequency"
    sync_res = subprocess.run(
        ["node", os.path.join("scripts", "sync.mjs")],
        cwd=temp_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if sync_res.returncode != 0:
        raise RuntimeError(f"scripts/sync.mjs failed in temp copy:\n{sync_res.stdout}\n{sync_res.stderr}")

    spec_path = os.path.join(temp_root, EXERCISE_REL, "parallel-letter-frequency.spec.js")
    with open(spec_path, "r", encoding="utf-8") as f:
        return normalize_timestamps(f.read())


def run_verification() -> dict:
    config_path = os.path.join(EXERCISE_DIR, ".meta", "config.json")
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Missing config.json at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = config["files"]["solution"][0]
    test_file = config["files"]["test"][0]
    example_file = config["files"]["example"][0]

    stub_path = os.path.join(EXERCISE_DIR, solution_file)
    with open(stub_path, "r", encoding="utf-8") as f:
        stub_content = f.read()
    if "Remove this line and implement the function" not in stub_content:
        raise AssertionError("Learner stub has been modified or solved in the working tree!")

    toml_path = os.path.join(EXERCISE_DIR, ".meta", "tests.toml")
    with open(toml_path, "r", encoding="utf-8") as f:
        toml_content = f.read()

    canonical_cases = re.findall(r'description\s*=\s*"([^"]+)"', toml_content)
    if not canonical_cases:
        raise AssertionError("No canonical test descriptions found in .meta/tests.toml")

    spec_path = os.path.join(EXERCISE_DIR, test_file)
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    spec_cases = re.findall(r"(?:x?test)\(\s*['\"]([^'\"]+)['\"]", spec_content)

    for anchor in ANCHOR_CASES:
        if anchor not in canonical_cases:
            raise AssertionError(f"Anchor case missing from tests.toml: {anchor}")
        if anchor not in spec_cases:
            raise AssertionError(f"Anchor case missing from spec.js: {anchor}")

    missing_in_spec = [c for c in canonical_cases if c not in spec_cases]
    if missing_in_spec:
        raise AssertionError(f"Cases silently dropped from spec.js: {missing_in_spec}")

    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        spec_copy_1 = run_sync_in_temp_repo(tmp1)
        spec_copy_2 = run_sync_in_temp_repo(tmp2)
        if spec_copy_1 != spec_copy_2:
            raise AssertionError("Two temporary generations produced differing spec files after timestamp normalization!")

    with tempfile.TemporaryDirectory() as exec_tmp:
        dest_exercise = os.path.join(exec_tmp, "exercise")
        shutil.copytree(EXERCISE_DIR, dest_exercise, symlinks=True)

        temp_spec = os.path.join(dest_exercise, test_file)
        with open(temp_spec, "r", encoding="utf-8") as f:
            temp_spec_content = f.read()
        temp_spec_content = temp_spec_content.replace("xtest(", "test(")
        with open(temp_spec, "w", encoding="utf-8") as f:
            f.write(temp_spec_content)

        shutil.copyfile(
            os.path.join(EXERCISE_DIR, example_file),
            os.path.join(dest_exercise, solution_file),
        )

        root_nm = os.path.join(REPO_ROOT, "node_modules")
        dest_nm = os.path.join(dest_exercise, "node_modules")
        if os.path.exists(root_nm) and not os.path.exists(dest_nm):
            os.symlink(root_nm, dest_nm)

        with open(os.path.join(dest_exercise, "package.json"), "r", encoding="utf-8") as f:
            ex_pkg = json.load(f)
        pkg_test_script = ex_pkg.get("scripts", {}).get("test", "corepack pnpm jest")

        env = os.environ.copy()
        env["CI"] = "true"
        local_jest = os.path.join(REPO_ROOT, "node_modules", ".bin", "jest")

        cmd = [local_jest, "--watchAll=false", "--no-watchman"]
        res = subprocess.run(cmd, cwd=dest_exercise, env=env, capture_output=True, text=True)
        combined_output = res.stdout + "\n" + res.stderr

        if res.returncode != 0:
            raise RuntimeError(f"Test runner exited with non-zero code {res.returncode}:\n{combined_output}")

        passed_match = re.search(r"Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total", combined_output)
        if not passed_match:
            passed_match = re.search(r"(\d+)\s+passed,\s+(\d+)\s+total", combined_output)
        passed_count = int(passed_match.group(1)) if passed_match else 0

        if passed_count == 0:
            raise AssertionError("Zero tests executed or passed!")
        if passed_count != len(canonical_cases):
            raise AssertionError(f"Expected {len(canonical_cases)} passed tests, got {passed_count}")

        node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
        npm_v = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()

        return {
            "task_id": "R53-T022",
            "exercise": "parallel-letter-frequency",
            "package_json_test_script": pkg_test_script,
            "anchor_cases_verified": ANCHOR_CASES,
            "canonical_cases_count": len(canonical_cases),
            "executed_passed_tests": passed_count,
            "double_copy_diff": "IDENTICAL_AFTER_TIMESTAMP_NORMALIZATION",
            "learner_stub_status": "UNSOLVED",
            "tool_versions": {
                "node": node_v,
                "npm": npm_v, "packageManager_lock": ex_pkg.get("packageManager", "pnpm@9.15.2"),
                "python": sys.version.split()[0],
            },
            "raw_output": combined_output,
            "status": "PASSED",
        }


def main():
    try:
        report = run_verification()
        print("=== R53-T022 Reusable Check Passed ===")
        print(f"Anchor cases verified: {report['anchor_cases_verified']}")
        print(f"Canonical cases mapped: {report['canonical_cases_count']}")
        print(f"Executed & passed tests: {report['executed_passed_tests']}")
        print(f"Double-copy regeneration check: {report['double_copy_diff']}")
        sys.exit(0)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
