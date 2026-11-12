import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_EXERCISE_DIR = os.path.join(
    REPO_ROOT, "exercises", "practice", "grade-school"
)


class RunnerError(Exception):
    """Raised when an isolated test run fails, executes zero tests, or mutates learner files."""


def hash_exercise_files(exercise_dir: str) -> dict:
    hashes = {}
    for root, dirs, files in os.walk(exercise_dir):
        dirs.sort()
        for fname in sorted(files):
            full_path = os.path.join(root, fname)
            if os.path.islink(full_path):
                continue
            rel = os.path.relpath(full_path, exercise_dir)
            h = hashlib.sha256()
            with open(full_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            hashes[rel] = h.hexdigest()
    return hashes


def run_isolated_suite(
    exercise_dir: str = DEFAULT_EXERCISE_DIR,
    solution_override: str | None = None,
    test_name_pattern: str | None = None,
) -> dict:
    exercise_root = os.path.realpath(exercise_dir)
    config_path = os.path.join(exercise_root, ".meta", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = config["files"]["solution"][0]
    test_file = config["files"]["test"][0]
    example_file = config["files"]["example"][0]

    before_hashes = hash_exercise_files(exercise_root)
    temp_dir_path = None

    try:
        if solution_override is None:
            with open(os.path.join(exercise_root, example_file), "r", encoding="utf-8") as f:
                target_solution = f.read()
        else:
            target_solution = solution_override

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_dir_path = tmp_dir
            dest_exercise = os.path.join(tmp_dir, "grade-school")
            shutil.copytree(exercise_root, dest_exercise, symlinks=True)

            temp_spec = os.path.join(dest_exercise, test_file)
            with open(temp_spec, "r", encoding="utf-8") as f:
                spec_text = f.read().replace("xtest(", "test(")
            with open(temp_spec, "w", encoding="utf-8") as f:
                f.write(spec_text)

            with open(os.path.join(dest_exercise, solution_file), "w", encoding="utf-8") as f:
                f.write(target_solution)

            root_nm = os.path.join(REPO_ROOT, "node_modules")
            dest_nm = os.path.join(dest_exercise, "node_modules")
            if os.path.exists(root_nm) and not os.path.exists(dest_nm):
                os.symlink(root_nm, dest_nm)

            env = os.environ.copy()
            env["CI"] = "true"
            local_jest = os.path.join(REPO_ROOT, "node_modules", ".bin", "jest")
            cmd = [local_jest, "--watchAll=false", "--no-watchman", "--verbose"]
            if test_name_pattern is not None:
                cmd.extend(["-t", test_name_pattern])

            res = subprocess.run(
                cmd,
                cwd=dest_exercise,
                env=env,
                capture_output=True,
                text=True,
            )
            combined = res.stdout + "\n" + res.stderr
            passed_match = re.search(r"Tests:.*?(\d+)\s+passed", combined)
            total_match = re.search(r"Tests:.*?(\d+)\s+total", combined)
            passed_count = int(passed_match.group(1)) if passed_match else 0
            total_count = int(total_match.group(1)) if total_match else 0

            if res.returncode != 0:
                raise RunnerError(
                    f"Child Jest process exited non-zero ({res.returncode}):\n{combined}"
                )
            if total_count == 0 or passed_count == 0:
                raise RunnerError(
                    f"Zero-test run detected (passed={passed_count}, total={total_count}):\n{combined}"
                )

            return {
                "exit_code": res.returncode,
                "executed_total_tests": total_count,
                "executed_passed_tests": passed_count,
                "temp_dir_cleaned": True,
                "output": combined,
            }
    finally:
        after_hashes = hash_exercise_files(exercise_root)
        if before_hashes != after_hashes:
            raise RunnerError("Working tree files were modified during isolated run!")
        if temp_dir_path and os.path.exists(temp_dir_path):
            shutil.rmtree(temp_dir_path, ignore_errors=True)


def main():
    result = run_isolated_suite(DEFAULT_EXERCISE_DIR)
    print(
        f"=== R53-T029 Isolated Runner Passed ({result['executed_passed_tests']}/{result['executed_total_tests']} tests) ==="
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
