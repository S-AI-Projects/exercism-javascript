#!/usr/bin/env python3
"""Exercise metadata validation checker for R53-T008 (Scrabble Score).

Validates that files declared in exercises/practice/scrabble-score/.meta/config.json
resolve within the exercise directory and exist. Also tests invalid fixtures
for missing references, missing tests, and directory escaping.
"""

import json
import os
import sys
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/scrabble-score")
CONFIG_RELATIVE = Path(".meta/config.json")


class MetadataValidationError(Exception):
    pass


def find_root():
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / ASSIGNMENT / CONFIG_RELATIVE).is_file()
        ):
            return candidate
    raise MetadataValidationError("Could not locate repository root directory")


def validate_config_data(config_dict, exercise_dir):
    files = config_dict.get("files")
    if not isinstance(files, dict):
        raise MetadataValidationError("Missing or invalid 'files' object in config")

    resolved = {}
    for kind in ("solution", "test", "example"):
        paths = files.get(kind)
        if not isinstance(paths, list) or len(paths) == 0:
            raise MetadataValidationError(f"Category '{kind}' must be a non-empty list")
        resolved[kind] = []
        for p in paths:
            rel = Path(p)
            target = (exercise_dir / rel).resolve()
            if not target.is_relative_to(exercise_dir.resolve()):
                raise MetadataValidationError(f"Path escapes exercise root: {p}")
            if not target.is_file():
                raise MetadataValidationError(f"Declared file does not exist: {p}")
            resolved[kind].append(str(rel))
    return resolved


def run_checks(root):
    exercise_dir = root / ASSIGNMENT
    config_path = exercise_dir / CONFIG_RELATIVE

    # 1. Validate real config
    real_data = json.loads(config_path.read_text(encoding="utf-8"))
    real_resolved = validate_config_data(real_data, exercise_dir)

    # 2. Test invalid fixture 1: missing reference
    fixture_missing_ref = json.loads(json.dumps(real_data))
    fixture_missing_ref["files"]["example"] = [".meta/non_existent_proof.js"]
    try:
        validate_config_data(fixture_missing_ref, exercise_dir)
        raise AssertionError("Failed to reject missing reference fixture")
    except MetadataValidationError as e:
        if "Declared file does not exist" not in str(e):
            raise AssertionError(f"Unexpected error for missing reference: {e}")

    # 3. Test invalid fixture 2: missing test
    fixture_missing_test = json.loads(json.dumps(real_data))
    fixture_missing_test["files"]["test"] = ["missing.spec.js"]
    try:
        validate_config_data(fixture_missing_test, exercise_dir)
        raise AssertionError("Failed to reject missing test fixture")
    except MetadataValidationError as e:
        if "Declared file does not exist" not in str(e):
            raise AssertionError(f"Unexpected error for missing test: {e}")

    # 4. Test invalid fixture 3: outside exercise parent traversal
    fixture_outside = json.loads(json.dumps(real_data))
    fixture_outside["files"]["solution"] = ["../../outside.js"]
    try:
        validate_config_data(fixture_outside, exercise_dir)
        raise AssertionError("Failed to reject outside exercise traversal fixture")
    except MetadataValidationError as e:
        if "escapes exercise root" not in str(e):
            raise AssertionError(f"Unexpected error for path traversal: {e}")

    return {
        "real_config_passed": True,
        "resolved_files": real_resolved,
        "invalid_fixtures_tested": ["missing_reference", "missing_test", "outside_traversal"],
    }


def main():
    try:
        root = find_root()
        res = run_checks(root)
        print("Scrabble Score metadata validation: PASS")
        print(f"Resolved files: {res['resolved_files']}")
    except Exception as e:
        print(f"Scrabble Score metadata validation FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
