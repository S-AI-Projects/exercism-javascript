import os
import shutil
import subprocess
import sys
import tempfile
import json
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXERCISE_REL = os.path.join("exercises", "practice", "robot-name")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)
WORK_DIR = os.path.abspath(os.path.dirname(__file__))

def main():
    print("=== Running R53-T021 Automated Check ===")

    # 1. Verify tests.toml parsing
    toml_path = os.path.join(EXERCISE_DIR, ".meta", "tests.toml")
    if not os.path.isfile(toml_path):
        print(f"Error: {toml_path} does not exist.")
        sys.exit(1)

    with open(toml_path, "r", encoding="utf-8") as f:
        toml_content = f.read()

    uuids = re.findall(r'\[([a-f0-9\-]{36})\]', toml_content)
    print(f"Parsed {len(uuids)} UUIDs from tests.toml: {uuids}")
    if len(uuids) != 4:
        print("Error: Expected 4 canonical test cases.")
        sys.exit(1)

    # 2. Read config.json
    config_path = os.path.join(EXERCISE_DIR, ".meta", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = config["files"]["solution"][0]
    test_file = config["files"]["test"][0]
    example_file = config["files"]["example"][0]

    # Verify learner stub is unsolved
    with open(os.path.join(EXERCISE_DIR, solution_file), "r", encoding="utf-8") as f:
        stub_content = f.read()
    if "generateName" in stub_content or "shuffled" in stub_content:
        print("Error: Learner stub has been solved in the repository!")
        sys.exit(1)
    print("Verified: Learner stub remains unsolved.")

    # 3. Create isolated temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_exercise = os.path.join(temp_dir, "exercise")
        shutil.copytree(EXERCISE_DIR, dest_exercise)

        # In the temp copy, enable all 'xtest' so all cases run
        temp_spec = os.path.join(dest_exercise, test_file)
        with open(temp_spec, "r", encoding="utf-8") as f:
            spec_content = f.read()
        
        spec_content = spec_content.replace("xtest(", "test(")
        with open(temp_spec, "w", encoding="utf-8") as f:
            f.write(spec_content)

        # Substitute example/reference implementation into solution file
        ref_src = os.path.join(EXERCISE_DIR, example_file)
        dest_solution = os.path.join(dest_exercise, solution_file)
        shutil.copyfile(ref_src, dest_solution)

        # Symlink root node_modules and config files so Jest works in the temp folder
        root_node_modules = os.path.join(REPO_ROOT, "node_modules")
        exercise_node_modules = os.path.join(dest_exercise, "node_modules")
        if os.path.exists(root_node_modules) and not os.path.exists(exercise_node_modules):
            try:
                os.symlink(root_node_modules, exercise_node_modules)
            except Exception:
                pass

        for cfg in ["babel.config.js", "package.json", "jest.config.js"]:
            src_cfg = os.path.join(REPO_ROOT, cfg)
            dst_cfg = os.path.join(dest_exercise, cfg)
            if os.path.isfile(src_cfg) and not os.path.isfile(dst_cfg):
                try:
                    shutil.copy2(src_cfg, dst_cfg)
                except Exception:
                    pass

        local_jest = os.path.join(REPO_ROOT, "node_modules", ".bin", "jest")
        cmd = [local_jest, test_file, "--no-watchman"]

        print("Executing tests against reference implementation in temporary directory...")
        result = subprocess.run(
            cmd,
            cwd=dest_exercise,
            capture_output=True,
            text=True
        )

        test_output = result.stdout + "\n" + result.stderr
        print(test_output)

        if result.returncode != 0:
            print(f"Error: Tests failed with exit code {result.returncode}")
            with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
                f.write(test_output)
            sys.exit(result.returncode)

        tests_passed_match = re.search(r"(\d+)\s+passed,\s+\d+\s+total", test_output)
        passed_count = int(tests_passed_match.group(1)) if tests_passed_match else 0
        if passed_count == 0:
            print("Error: Zero tests were executed.")
            sys.exit(1)

        print(f"Success! {passed_count} tests executed and passed.")

        node_version = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
        npm_version = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()
        python_version = sys.version.split()[0]

        evidence = {
            "task_id": "R53-T021",
            "exercise": "robot-name",
            "canonical_uuids_count": len(uuids),
            "executed_passed_tests": passed_count,
            "tool_versions": {
                "node": node_version,
                "npm": npm_version,
                "python": python_version
            },
            "status": "PASSED"
        }

        with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2)

        with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
            f.write(test_output)

    print("Evidence successfully saved in work/R53-T021/")

if __name__ == "__main__":
    main()