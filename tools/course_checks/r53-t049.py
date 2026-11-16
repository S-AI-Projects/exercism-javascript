#!/usr/bin/env python3
"""Isolated test runner for R53-T049 (Protein Translation).

Executes the Protein Translation exercise test suite in an isolated temporary
copy, substituting the maintained reference implementation without modifying
the learner's solution in the working tree. Enforces test execution, zero-test
rejection, and guaranteed temporary directory cleanup even on failure or interruption.
"""

import argparse
import atexit
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/protein-translation")
CONFIG_RELATIVE = Path(".meta/config.json")
REQUIRED_NAMED_CASES = [
    "Empty RNA sequence results in no proteins",
    "Methionine RNA sequence",
    "Phenylalanine RNA sequence 1",
]

# Track active temporary directories globally for signal/exit cleanup
_ACTIVE_TEMP_DIRS = set()


def _cleanup_registered_temp_dirs():
    """Remove any registered temporary directories still present."""
    for temp_dir in list(_ACTIVE_TEMP_DIRS):
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
        _ACTIVE_TEMP_DIRS.discard(temp_dir)


atexit.register(_cleanup_registered_temp_dirs)


def _signal_handler(sig, frame):
    """Handle interruption signals by cleaning up and exiting with appropriate code."""
    _cleanup_registered_temp_dirs()
    sys.exit(128 + sig)


try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
except (ValueError, AttributeError):
    # Signals might not be interceptable in non-main threads or some environments
    pass


class RunnerError(Exception):
    """Base exception for isolated runner errors."""
    def __init__(self, message, result_payload=None):
        super().__init__(message)
        self.result_payload = result_payload or {}


class ZeroTestsExecutedError(RunnerError):
    """Raised when zero test cases are executed."""
    pass


class TestFailureError(RunnerError):
    """Raised when one or more test assertions fail."""
    pass


def find_root():
    """Locate repository root directory."""
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / ASSIGNMENT / CONFIG_RELATIVE).is_file()
        ):
            return candidate
    raise RunnerError("Could not locate repository root directory")


def sha256_file(path):
    """Compute the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_package_manager(root):
    """Detect package manager from lockfile and package.json."""
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "package-lock.json").is_file():
        return "npm"
    raise RunnerError("No known lockfile found in repository root")


def resolve_files(exercise_dir, config_path):
    """Read and validate file declarations from config.json."""
    if not config_path.is_file():
        raise RunnerError(f"Exercise config.json not found: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise RunnerError(f"Malformed config.json at {config_path}: {err}")

    files_obj = config.get("files")
    if not isinstance(files_obj, dict):
        raise RunnerError("Missing or non-object 'files' in config.json")

    resolved = {}
    exercise_root = exercise_dir.resolve()

    for kind in ("solution", "test", "example"):
        declared = files_obj.get(kind)
        if not isinstance(declared, list) or not declared:
            raise RunnerError(f"Config category 'files.{kind}' must be a non-empty list")
        resolved[kind] = []
        for entry in declared:
            if not isinstance(entry, str) or not entry.strip():
                raise RunnerError(f"Invalid entry in 'files.{kind}'")
            rel_path = Path(entry.replace("%{kebab_slug}", exercise_dir.name))
            abs_path = (exercise_dir / rel_path).resolve()
            if not abs_path.is_relative_to(exercise_root):
                raise RunnerError(f"Path '{entry}' escapes exercise root directory")
            if not abs_path.is_file():
                raise RunnerError(f"Declared file '{entry}' in 'files.{kind}' does not exist: {abs_path}")
            resolved[kind].append((rel_path, abs_path))

    return resolved


def enable_all_tests(source_text):
    """Promote xtest and xit to test and it, and xdescribe to describe."""
    text = re.sub(r"\bx(test|it)\(", "test(", source_text)
    return re.sub(r"\bxdescribe\(", "describe(", text)


def run_isolated_test(
    root=None,
    custom_reference=None,
    custom_spec=None,
    empty_tests=False,
    test_name_pattern=None,
):
    """Run the Protein Translation test suite in an isolated temporary directory.

    Args:
        root: Optional Path to repository root.
        custom_reference: Optional Path to alternate reference implementation file.
        custom_spec: Optional Path to alternate test specification file.
        empty_tests: If True, simulate an empty test suite execution.
        test_name_pattern: Optional regex pattern for Jest --testNamePattern.

    Returns:
        dict: Detailed execution results, counts, and named case outcomes.

    Raises:
        ZeroTestsExecutedError: If zero tests execute.
        TestFailureError: If one or more tests fail.
        RunnerError: If any configuration or subprocess error occurs.
    """
    if root is None:
        root = find_root()

    exercise_dir = root / ASSIGNMENT
    config_path = exercise_dir / CONFIG_RELATIVE
    files = resolve_files(exercise_dir, config_path)

    learner_solution_path = files["solution"][0][1]
    default_reference_path = files["example"][0][1]
    test_spec_path = files["test"][0][1]

    reference_to_substitute = Path(custom_reference) if custom_reference else default_reference_path
    if not reference_to_substitute.is_file():
        raise RunnerError(f"Reference implementation file does not exist: {reference_to_substitute}")

    # Baseline learner hash
    learner_hash_before = sha256_file(learner_solution_path)

    # Determine package manager and inspect package.json
    pkg_manager = detect_package_manager(root)
    pkg_json_file = exercise_dir / "package.json"
    if not pkg_json_file.is_file():
        raise RunnerError(f"Exercise package.json missing: {pkg_json_file}")
    pkg_data = json.loads(pkg_json_file.read_text(encoding="utf-8"))
    test_script = pkg_data.get("scripts", {}).get("test")
    if not test_script:
        raise RunnerError("Exercise package.json does not declare a test script")

    # Create temporary isolated directory
    temp_dir = Path(tempfile.mkdtemp(prefix="r53_t049_protein_"))
    _ACTIVE_TEMP_DIRS.add(str(temp_dir))

    # Announce temporary directory path so parent harnesses can verify lifecycle and cleanup
    print(f"[RUNNER_TEMP_DIR] {temp_dir}", flush=True)

    result_payload = {
        "temp_dir": str(temp_dir),
        "executed_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "pending_tests": 0,
        "named_cases": {},
        "return_code": None,
        "error": None,
    }

    try:
        isolated_exercise = temp_dir / "exercise"
        shutil.copytree(exercise_dir, isolated_exercise)

        # Substitute reference implementation ONLY inside isolated copy
        dest_solution = isolated_exercise / files["solution"][0][0]
        shutil.copy2(reference_to_substitute, dest_solution)

        # Configure test spec inside isolated copy
        dest_spec = isolated_exercise / files["test"][0][0]
        if empty_tests:
            # Simulate zero test selection / empty suite
            dest_spec.write_text(
                "import { describe } from '@jest/globals';\ndescribe('Empty suite', () => {});\n",
                encoding="utf-8",
            )
        elif custom_spec:
            shutil.copy2(custom_spec, dest_spec)
        else:
            # Promote all skipped tests so that the full suite runs
            original_spec = dest_spec.read_text(encoding="utf-8")
            dest_spec.write_text(enable_all_tests(original_spec), encoding="utf-8")

        # Prepare child environment
        env = os.environ.copy()
        node_bin = str(root / "node_modules" / ".bin")
        env["PATH"] = node_bin + ":" + env.get("PATH", "")
        env["NODE_PATH"] = str(root / "node_modules")
        env["CI"] = "1"

        jest_json_output = isolated_exercise / "jest-test-result.json"

        # Build Jest invocation command
        cmd = [
            "corepack",
            pkg_manager,
            "--dir",
            str(isolated_exercise),
            "run",
            "test",
            "--runInBand",
            "--watch=false",
            "--runTestsByPath",
            files["test"][0][0].as_posix(),
            "--json",
            f"--outputFile={jest_json_output}",
        ]
        if test_name_pattern:
            cmd.append(f"--testNamePattern={test_name_pattern}")

        # Execute test runner process
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        result_payload["return_code"] = proc.returncode
        result_payload["stdout"] = proc.stdout
        result_payload["stderr"] = proc.stderr

        # Parse test results
        if jest_json_output.is_file():
            try:
                jest_data = json.loads(jest_json_output.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                jest_data = {}
        else:
            jest_data = {}

        total_tests = jest_data.get("numTotalTests", 0)
        passed_tests = jest_data.get("numPassedTests", 0)
        failed_tests = jest_data.get("numFailedTests", 0)
        pending_tests = jest_data.get("numPendingTests", 0)

        # Executed tests are tests that actually ran (passed or failed), excluding pending
        executed_tests = passed_tests + failed_tests

        result_payload["total_tests"] = total_tests
        result_payload["executed_tests"] = executed_tests
        result_payload["passed_tests"] = passed_tests
        result_payload["failed_tests"] = failed_tests
        result_payload["pending_tests"] = pending_tests

        # Extract named case outcomes if available
        if jest_data.get("testResults"):
            for suite in jest_data["testResults"]:
                for assertion in suite.get("assertionResults", []):
                    title = assertion.get("title")
                    status = assertion.get("status")
                    if title in REQUIRED_NAMED_CASES:
                        result_payload["named_cases"][title] = status

        # Learner file immutability check
        learner_hash_after = sha256_file(learner_solution_path)
        if learner_hash_after != learner_hash_before:
            raise RunnerError("CRITICAL: Original learner solution file was modified in working tree!")

        # Enforce execution guards
        if executed_tests == 0:
            err_msg = (
                f"Zero tests executed (total: {total_tests}, passed: {passed_tests}, "
                f"failed: {failed_tests}, pending: {pending_tests}). Guard triggered."
            )
            result_payload["error"] = err_msg
            raise ZeroTestsExecutedError(err_msg, result_payload)

        if failed_tests > 0 or proc.returncode != 0:
            err_msg = (
                f"Test execution failed: {failed_tests} failure(s) out of {executed_tests} "
                f"executed test(s) (process exit code: {proc.returncode})"
            )
            result_payload["error"] = err_msg
            raise TestFailureError(err_msg, result_payload)

        return result_payload

    finally:
        # Guarantee temporary directory cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        _ACTIVE_TEMP_DIRS.discard(str(temp_dir))


def main():
    parser = argparse.ArgumentParser(
        description="Isolated Protein Translation exercise test runner (R53-T049)"
    )
    parser.add_argument(
        "--reference",
        "--reference-path",
        dest="reference_path",
        help="Optional path to custom reference implementation file",
        default=None,
    )
    parser.add_argument(
        "--spec",
        "--spec-path",
        dest="spec_path",
        help="Optional path to custom test specification file",
        default=None,
    )
    parser.add_argument(
        "--empty-tests",
        action="store_true",
        help="Simulate an empty test run (zero tests executed)",
    )
    parser.add_argument(
        "--test-name-pattern",
        dest="test_name_pattern",
        help="Optional regex pattern to filter test names via Jest",
        default=None,
    )
    parser.add_argument(
        "--json-output",
        dest="json_output",
        help="Optional path to write structured execution results as JSON",
        default=None,
    )

    args = parser.parse_args()

    try:
        root = find_root()
    except RunnerError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    exercise_dir = root / ASSIGNMENT
    print("=== Protein Translation Isolated Test Runner (R53-T049) ===")
    print(f"Repository Root:    {root}")
    print(f"Exercise Directory: {exercise_dir}")

    status_code = 0
    results = None
    try:
        results = run_isolated_test(
            root=root,
            custom_reference=args.reference_path,
            custom_spec=args.spec_path,
            empty_tests=args.empty_tests,
            test_name_pattern=args.test_name_pattern,
        )
        print("\n[PASS] Test suite execution succeeded:")
        print(f"  - Executed tests: {results['executed_tests']}")
        print(f"  - Passed tests:   {results['passed_tests']}")
        print(f"  - Failed tests:   {results['failed_tests']}")
        if results.get("named_cases"):
            print("  - Named cases verified:")
            for case_name, outcome in results["named_cases"].items():
                print(f"    * {case_name}: {outcome.upper()}")
        print("\nTemporary directory successfully cleaned up.")
        print("Original learner files remain strictly unmodified.")
    except ZeroTestsExecutedError as err:
        print(f"\n[FAIL] Zero tests executed: {err}", file=sys.stderr)
        status_code = 2
        results = err.result_payload
    except TestFailureError as err:
        print(f"\n[FAIL] Test failure detected: {err}", file=sys.stderr)
        status_code = 1
        results = err.result_payload
    except RunnerError as err:
        print(f"\n[FAIL] Runner error: {err}", file=sys.stderr)
        status_code = 1
        results = err.result_payload
    except Exception as err:
        print(f"\n[FAIL] Unexpected error: {err}", file=sys.stderr)
        status_code = 1

    if args.json_output:
        payload = results or {}
        payload["exit_status"] = status_code
        try:
            Path(args.json_output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Warning: could not write JSON output: {e}", file=sys.stderr)

    return status_code


if __name__ == "__main__":
    sys.exit(main())
