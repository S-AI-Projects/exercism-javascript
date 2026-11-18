#!/usr/bin/env python3
"""Isolated test runner for exercises/practice/list-ops.

Copies the exercise to a temporary directory, substitutes the reference
implementation from .meta/proof.ci.js for the learner stub, enables all
test cases (removes xtest), runs Jest, reports the real case count, and
cleans up.  The learner files in the working tree are never modified.

Usage:
    python3 tools/course_checks/r53-t009.py [--fail-ref | --empty-tests]

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
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXERCISE = Path("exercises/practice/list-ops")


def find_root():
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
    """Hash all solution (learner) files and return a dict of path -> hash."""
    hashes = {}
    for sol_file in config["files"]["solution"]:
        p = root / EXERCISE / sol_file
        if p.exists():
            hashes[sol_file] = sha256(p)
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

    solution_file = config["files"]["solution"][0]  # list-ops.js
    test_file = config["files"]["test"][0]           # list-ops.spec.js
    example_file = config["files"]["example"][0]     # .meta/proof.ci.js

    # Hash learner files BEFORE run
    hashes_before = hash_learner_files(root, config)

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"

    tmpdir = tempfile.mkdtemp(prefix="list-ops-runner-")
    try:
        # Copy the full exercise directory including dotfiles
        tmp_exercise = Path(tmpdir) / "list-ops"
        shutil.copytree(str(exercise_dir), str(tmp_exercise))

        # Substitute reference implementation for learner stub
        ref_src = tmp_exercise / example_file
        sol_dst = tmp_exercise / solution_file

        if fail_ref:
            # Inject a deliberately broken reference
            sol_dst.write_text(
                'export class List {\n'
                '  constructor() { throw new Error("DELIBERATE FAILURE"); }\n'
                '  append() { return this; }\n'
                '  concat() { return this; }\n'
                '  filter() { return this; }\n'
                '  map() { return this; }\n'
                '  length() { return -1; }\n'
                '  foldl() { return undefined; }\n'
                '  foldr() { return undefined; }\n'
                '  reverse() { return this; }\n'
                '}\n',
                encoding="utf-8",
            )
        else:
            shutil.copy2(str(ref_src), str(sol_dst))

        # Enable all test cases
        spec_path = tmp_exercise / test_file
        spec_content = spec_path.read_text(encoding="utf-8")

        if empty_tests:
            # Write an empty test file for zero-test guard
            spec_path.write_text(
                "import { describe } from '@jest/globals';\n"
                "describe('empty', () => {});\n",
                encoding="utf-8",
            )
        else:
            spec_path.write_text(enable_all_tests(spec_content), encoding="utf-8")

        # Copy package scaffolding needed by Jest
        for needed in ["package.json", "babel.config.js", "jest.config.js", "eslint.config.mjs"]:
            src = tmp_exercise / needed
            if not src.exists():
                # Try from exercise dir
                orig = exercise_dir / needed
                if orig.exists():
                    shutil.copy2(str(orig), str(src))

        # Ensure node_modules are available (symlink from repo root)
        nm_link = tmp_exercise / "node_modules"
        if not nm_link.exists():
            nm_target = root / "node_modules"
            if nm_target.exists():
                os.symlink(str(nm_target), str(nm_link))

        # Run Jest
        jest_cmd = [
            str(root / "node_modules" / ".bin" / "jest"),
            "--no-cache",
            "--ci",
            str(tmp_exercise / test_file),
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

        # Parse test count
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
            # Check for zero tests
            no_tests = re.search(r"Test Suites:.*0 of", output) or "no tests" in output.lower()
            if no_tests or empty_tests:
                passed = 0
                total = 0
            else:
                passed = 0
                total = 0

        print(f"Test results: {passed} passed, {total} total")
        print(f"Exit code: {result.returncode}")

    finally:
        # Clean up temporary directory
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Temporary directory cleaned up: {tmpdir}")

    # Hash learner files AFTER run
    hashes_after = hash_learner_files(root, config)

    # Verify immutability
    if hashes_before != hashes_after:
        print("ERROR: Learner files were modified during the run!")
        for f in hashes_before:
            if hashes_before[f] != hashes_after.get(f, "MISSING"):
                print(f"  Changed: {f}")
        sys.exit(1)
    else:
        print("Learner file integrity verified: hashes unchanged.")

    # Determine exit status
    if empty_tests:
        if total == 0:
            print("PASS: Zero-test guard correctly detected no tests.")
            sys.exit(2)
        else:
            print("FAIL: Expected zero tests but got some.")
            sys.exit(1)
    elif fail_ref:
        if result.returncode != 0:
            print("PASS: Failure correctly propagated from bad reference.")
            sys.exit(1)  # Expected non-zero
        else:
            print("FAIL: Bad reference should have caused test failure.")
            sys.exit(1)
    else:
        if result.returncode == 0 and passed > 0:
            print(f"PASS: All {passed} tests passed with the reference implementation.")
            sys.exit(0)
        else:
            print(f"FAIL: Tests did not pass. Output:\n{output}")
            sys.exit(1)


if __name__ == "__main__":
    main()
