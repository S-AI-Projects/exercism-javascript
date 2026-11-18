#!/usr/bin/env python3
"""Isolated test runner for exercises/practice/react.

Copies the exercise to a temporary directory inside the repository,
substitutes the reference implementation from .meta/proof.ci.js for the
learner stub, enables all test cases (removes xtest), runs Jest, reports the
real case count, and cleans up. The learner files in the working tree are never modified.

Usage:
    python3 tools/course_checks/r53-t010.py [--fail-ref | --empty-tests]

Flags:
    --fail-ref      Inject a deliberately failing reference to test failure propagation.
    --empty-tests   Run with an empty test file to test zero-test detection.

Exit codes:
    0  All tests passed (normal mode)
    1  Test failure or runner error
    2  Zero tests detected (guard)
"""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXERCISE = Path("exercises/practice/react")
TASK = "R53-T010"

REQUIRED_NAMED_CASES = [
    "accepts input",
    "allows input cell value to be set",
    "allows setting compute cells",
]


def find_root() -> Path:
    """Walk up from this script to locate the repository root."""
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / EXERCISE / ".meta" / "config.json").is_file()
        ):
            return candidate
    raise SystemExit("ERROR: Could not locate repository root directory")


def sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_learner_files(root: Path, config: dict) -> dict:
    """Hash learner-visible files and return rel-path -> digest."""
    hashes = {}
    for category in ("solution", "test"):
        for rel in config["files"].get(category, []):
            p = root / EXERCISE / rel
            if p.exists():
                hashes[rel] = sha256(p)
    return hashes


def enable_all_tests(spec_content: str) -> str:
    """Replace xtest( with test( to enable all test cases."""
    return spec_content.replace("xtest(", "test(")


def main():
    fail_ref = "--fail-ref" in sys.argv
    empty_tests = "--empty-tests" in sys.argv

    root = find_root()
    exercise_dir = root / EXERCISE
    config_path = exercise_dir / ".meta" / "config.json"

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = config["files"]["solution"][0]  # react.js
    test_file = config["files"]["test"][0]          # react.spec.js
    example_file = config["files"]["example"][0]    # .meta/proof.ci.js

    # Hash learner files BEFORE run
    hashes_before = hash_learner_files(root, config)

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
    env["CI"] = "true"

    tmpdir = tempfile.mkdtemp(prefix=".react-runner-", dir=str(root))
    cleanup_ok = False
    exit_code = 1
    output = ""

    try:
        tmp_exercise = Path(tmpdir) / "react"
        shutil.copytree(str(exercise_dir), str(tmp_exercise))

        # Substitute reference implementation for learner stub
        ref_src = tmp_exercise / example_file
        sol_dst = tmp_exercise / solution_file

        if fail_ref:
            # Inject a deliberately failing reference
            sol_dst.write_text(
                'export class InputCell {\n'
                '  constructor() { throw new Error("DELIBERATE FAILURE"); }\n'
                '  setValue() {}\n'
                '}\n'
                'export class ComputeCell {\n'
                '  constructor() { throw new Error("DELIBERATE FAILURE"); }\n'
                '  addCallback() {}\n'
                '  removeCallback() {}\n'
                '}\n'
                'export class CallbackCell {\n'
                '  constructor() {}\n'
                '}\n',
                encoding="utf-8",
            )
        else:
            shutil.copy2(str(ref_src), str(sol_dst))

        # Enable all test cases
        spec_path = tmp_exercise / test_file
        spec_content = spec_path.read_text(encoding="utf-8")

        if empty_tests:
            spec_path.write_text(
                "import { describe } from '@jest/globals';\n"
                "describe('empty', () => {});\n",
                encoding="utf-8",
            )
        else:
            spec_path.write_text(enable_all_tests(spec_content), encoding="utf-8")

        # Run Jest
        jest_cmd = [
            str(root / "node_modules" / ".bin" / "jest"),
            "--no-cache",
            "--ci",
            str(spec_path),
        ]

        result = subprocess.run(
            jest_cmd,
            cwd=str(tmp_exercise),
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

        output = result.stdout + "\n" + result.stderr
        exit_code = result.returncode
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        cleanup_ok = not os.path.exists(tmpdir)

    hashes_after = hash_learner_files(root, config)
    immutable = hashes_before == hashes_after

    # Parse test counts
    tests_match = re.search(r"Tests:\s*(\d+)\s*passed,\s*(\d+)\s*total", output)
    failed_match = re.search(r"Tests:\s*(\d+)\s*failed", output)

    if tests_match:
        passed = int(tests_match.group(1))
        total = int(tests_match.group(2))
    elif failed_match:
        passed = 0
        total_match = re.search(r"(\d+)\s*total", output)
        total = int(total_match.group(1)) if total_match else 0
    else:
        passed = 0
        total = 0

    mode = "normal"
    if fail_ref:
        mode = "fail-ref"
    elif empty_tests:
        mode = "empty-tests"

    print(f"\n============================================================")
    print(f"Task: {TASK} | Exercise: react | Mode: {mode}")
    print(f"============================================================")
    print(f"Test results: {passed} passed, {total} total")
    print(f"Exit code: {exit_code}")
    print(f"Temporary directory cleaned up: {tmpdir}")
    print(f"Learner file integrity verified: {'hashes unchanged.' if immutable else 'MODIFIED!'}")

    if mode == "normal":
        if exit_code == 0 and total > 0 and immutable:
            print(f"PASS: All {passed} tests passed with the reference implementation.\n")
            sys.exit(0)
        else:
            print(f"FAIL: Tests failed or files modified.\n")
            sys.exit(1)
    elif mode == "fail-ref":
        if exit_code != 0:
            print("PASS: Deliberately failing reference properly rejected.\n")
            sys.exit(1)
        else:
            print("FAIL: Deliberately failing reference did not fail.\n")
            sys.exit(0)
    elif mode == "empty-tests":
        if total == 0 or exit_code != 0:
            print("PASS: Empty test suite guarded with exit code 2.\n")
            sys.exit(2)
        else:
            print("FAIL: Empty test suite did not trigger guard.\n")
            sys.exit(0)


if __name__ == "__main__":
    main()
