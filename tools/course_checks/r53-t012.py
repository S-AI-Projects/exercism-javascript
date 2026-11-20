#!/usr/bin/env python3
"""Check zebra-puzzle metadata and reproducible track test preparation."""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "zebra-puzzle"
HELPERS = ROOT / "scripts" / "helpers.mjs"
OUTPUT = ROOT / "work" / "R53-T012" / "preparation-results.json"
EXPECTED_CASES = {
    "16efb4e4-8ad7-4d5e-ba96-e5537b66fd42": {
        "description": "resident who drinks water",
        "test_name": "resident who drinks water",
        "method": "waterDrinker",
        "expected": "Norwegian",
    },
    "084d5b8b-24e2-40e6-b008-c800da8cd257": {
        "description": "resident who owns zebra",
        "test_name": "resident who owns zebra",
        "method": "zebraOwner",
        "expected": "Japanese",
    },
}
TEST_NAMES = re.compile(r"\btest\s*\(\s*(['\"])(.*?)\1")


def sha256(contents):
    return hashlib.sha256(contents).hexdigest()


def check_case_source(source, case, enabled):
    marker = "test" if enabled else "(?:x?test)"
    assertion = re.compile(
        rf"\b{marker}\s*\(\s*(['\"]){re.escape(case['test_name'])}\1"
        rf"[\s\S]*?expect\(puzzle\.{case['method']}\(\)\)"
        rf"\.toEqual\(['\"]{re.escape(case['expected'])}['\"]\)"
    )
    return assertion.search(source) is not None


def prepare_copy(temp_root):
    exercise_copy = temp_root / "exercises" / "practice" / "zebra-puzzle"
    exercise_copy.parent.mkdir(parents=True)
    shutil.copytree(
        EXERCISE,
        exercise_copy,
        ignore=shutil.ignore_patterns("node_modules"),
    )
    (temp_root / "exercises" / "concept").mkdir(parents=True)

    source = (
        f"import {{ prepare }} from {json.dumps(HELPERS.as_uri())}; "
        "prepare('practice/zebra-puzzle');"
    )
    command = ["node", "--input-type=module", "-e", source]
    result = subprocess.run(
        command,
        cwd=temp_root,
        capture_output=True,
        text=True,
        check=False,
    )
    prepared_test = (
        temp_root
        / "tmp_exercises"
        / "practice"
        / "zebra-puzzle"
        / "zebra-puzzle.spec.js"
    )
    return {
        "command": command,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "test_source": (
            prepared_test.read_text(encoding="utf-8")
            if prepared_test.is_file()
            else None
        ),
    }


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    original_test = (EXERCISE / "zebra-puzzle.spec.js").read_bytes()
    original_solution = (EXERCISE / "zebra-puzzle.js").read_bytes()
    metadata = tomllib.loads(
        (EXERCISE / ".meta" / "tests.toml").read_text(encoding="utf-8")
    )
    failures = []
    selected_metadata = {}

    for case_id, expected in EXPECTED_CASES.items():
        actual = metadata.get(case_id)
        if actual is None:
            failures.append(f"Canonical UUID {case_id} is missing from tests.toml.")
            selected_metadata[case_id] = None
            continue
        selected_metadata[case_id] = actual
        if actual.get("description") != expected["description"]:
            failures.append(f"Canonical UUID {case_id} has an unexpected description.")
        if actual.get("include", True) is False:
            failures.append(f"Canonical UUID {case_id} is excluded.")
        if not check_case_source(
            original_test.decode("utf-8"), expected, enabled=False
        ):
            failures.append(
                f"The maintained JavaScript test for {case_id} does not match."
            )

    with tempfile.TemporaryDirectory(prefix="zebra-preparation-") as temp_dir:
        temp_root = Path(temp_dir)
        first = prepare_copy(temp_root / "first")
        second = prepare_copy(temp_root / "second")

    for index, result in enumerate((first, second), start=1):
        if result["return_code"] != 0:
            failures.append(
                f"Preparation copy {index} exited with status "
                f"{result['return_code']}."
            )
        if result["test_source"] is None:
            failures.append(f"Preparation copy {index} did not create its test file.")
        elif any(
            not check_case_source(result["test_source"], case, enabled=True)
            for case in EXPECTED_CASES.values()
        ):
            failures.append(
                f"Preparation copy {index} did not retain both enabled cases."
            )

    prepared_tests_match = (
        first["test_source"] is not None
        and second["test_source"] is not None
        and first["test_source"] == second["test_source"]
    )
    if not prepared_tests_match:
        failures.append("The two freshly prepared test files are different.")

    unchanged = (
        original_test == (EXERCISE / "zebra-puzzle.spec.js").read_bytes()
        and original_solution == (EXERCISE / "zebra-puzzle.js").read_bytes()
    )
    if not unchanged:
        failures.append("The maintained test or learner solution changed.")

    prepared_names = (
        TEST_NAMES.findall(first["test_source"])
        if first["test_source"] is not None
        else []
    )
    report = {
        "success": not failures,
        "canonical_cases": EXPECTED_CASES,
        "metadata_entries": selected_metadata,
        "included_case_count": sum(
            case.get("include", True) is not False
            for case in metadata.values()
            if isinstance(case, dict)
        ),
        "excluded_case_count": sum(
            case.get("include", True) is False
            for case in metadata.values()
            if isinstance(case, dict)
        ),
        "prepared_test_count": len(prepared_names),
        "prepared_test_names": [name for _, name in prepared_names],
        "prepared_test_files_identical": prepared_tests_match,
        "original_test_and_solution_unchanged": unchanged,
        "preparation_runs": [
            {key: value for key, value in first.items() if key != "test_source"},
            {key: value for key, value in second.items() if key != "test_source"},
        ],
        "prepared_test_source": first["test_source"],
        "failure_reasons": failures,
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(
        f"PASS: both canonical cases are present; "
        f"{len(prepared_names)} prepared tests match across two fresh copies."
    )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
