#!/usr/bin/env python3
"""Exercise metadata validation checker for R53-T048 (Poker).

Validates that files declared in exercises/practice/poker/.meta/config.json
resolve within the exercise directory and exist. Also tests invalid fixtures
for missing references, missing tests, and directory escaping.
"""

import json
import os
import sys
from pathlib import Path


ASSIGNMENT = Path("exercises/practice/poker")
CONFIG_RELATIVE = Path(".meta/config.json")


class MetadataValidationError(Exception):
    """Raised when exercise metadata fails validation."""
    pass


def find_root():
    """Locate the repository root directory."""
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / ASSIGNMENT / CONFIG_RELATIVE).is_file()
        ):
            return candidate
    raise MetadataValidationError("Could not locate repository root directory")


def validate_config_data(config_dict, exercise_dir):
    """Validate a parsed config.json dictionary against an exercise directory.

    Args:
        config_dict: Parsed JSON object from config.json.
        exercise_dir: Path to the exercise root directory.

    Returns:
        dict: Mapping of category -> list of (relative_path, resolved_absolute_path).

    Raises:
        MetadataValidationError: When any validation rule is violated.
    """
    if not isinstance(config_dict, dict):
        raise MetadataValidationError("Malformed metadata: root configuration must be a JSON object")

    file_config = config_dict.get("files")
    if not isinstance(file_config, dict):
        raise MetadataValidationError("Malformed metadata: missing or non-object 'files' property")

    # Required file categories for practice exercises
    required_categories = ["solution", "test"]
    for req in required_categories:
        if req not in file_config:
            raise MetadataValidationError(f"Missing required file category 'files.{req}'")

    # Either 'example' (practice) or 'exemplar' (concept) must be declared
    if "example" not in file_config and "exemplar" not in file_config:
        raise MetadataValidationError("Missing required reference implementation category ('files.example' or 'files.exemplar')")

    all_categories = ["solution", "test", "example", "exemplar", "editor"]
    resolved = {}
    exercise_root = exercise_dir.resolve()

    for category in all_categories:
        if category not in file_config:
            continue

        file_list = file_config.get(category)
        if not isinstance(file_list, list) or not file_list:
            raise MetadataValidationError(f"Invalid metadata: 'files.{category}' must be a non-empty list of file paths")

        resolved[category] = []
        for entry in file_list:
            if not isinstance(entry, str) or not entry.strip():
                raise MetadataValidationError(f"Invalid metadata: entry in 'files.{category}' must be a non-empty string")

            # Check for parent directory traversal
            path_parts = Path(entry).parts
            if ".." in path_parts:
                raise MetadataValidationError(
                    f"Parent-directory traversal rejected: path '{entry}' in 'files.{category}' contains '..'"
                )

            # Resolve relative to exercise directory
            relative_path = Path(entry.replace("%{kebab_slug}", exercise_dir.name))
            resolved_path = (exercise_dir / relative_path).resolve()

            # Ensure path does not escape the exercise directory
            try:
                resolved_path.relative_to(exercise_root)
            except ValueError:
                raise MetadataValidationError(
                    f"Path escaping rejected: '{entry}' in 'files.{category}' resolves to '{resolved_path}', "
                    f"which escapes exercise root '{exercise_root}'"
                )

            # Ensure declared file exists
            if not resolved_path.is_file():
                if category in ("example", "exemplar"):
                    role_desc = "reference implementation"
                elif category == "test":
                    role_desc = "test file"
                elif category == "solution":
                    role_desc = "solution stub"
                else:
                    role_desc = f"{category} file"

                raise MetadataValidationError(
                    f"Missing {role_desc}: declared path '{entry}' in 'files.{category}' does not exist at '{resolved_path}'"
                )

            resolved[category].append((relative_path, resolved_path))

    return resolved


def validate_file(config_path, exercise_dir):
    """Read, parse, and validate an exercise config.json file."""
    if not config_path.is_file():
        raise MetadataValidationError(f"Configuration file not found: {config_path}")

    try:
        content = config_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as err:
        raise MetadataValidationError(f"Malformed JSON in {config_path}: {err}")

    return validate_config_data(data, exercise_dir)


def run_fixtures(exercise_dir):
    """Run invalid metadata fixtures and verify that each fails for the intended reason."""
    fixtures = [
        {
            "name": "missing_reference_path",
            "description": "A missing-reference path ('files.example')",
            "config": {
                "files": {
                    "solution": ["poker.js"],
                    "test": ["poker.spec.js"],
                    "example": [".meta/nonexistent-proof.ci.js"],
                }
            },
            "expected_error_substring": "Missing reference implementation: declared path '.meta/nonexistent-proof.ci.js'",
        },
        {
            "name": "missing_test_path",
            "description": "A missing-test path ('files.test')",
            "config": {
                "files": {
                    "solution": ["poker.js"],
                    "test": ["nonexistent-poker.spec.js"],
                    "example": [".meta/proof.ci.js"],
                }
            },
            "expected_error_substring": "Missing test file: declared path 'nonexistent-poker.spec.js'",
        },
        {
            "name": "outside_exercise_path",
            "description": "An outside-exercise path attempting parent directory traversal",
            "config": {
                "files": {
                    "solution": ["../../outside.js"],
                    "test": ["poker.spec.js"],
                    "example": [".meta/proof.ci.js"],
                }
            },
            "expected_error_substring": "Parent-directory traversal rejected",
        },
    ]

    fixture_results = []
    for f in fixtures:
        failed_as_expected = False
        actual_error = None
        try:
            validate_config_data(f["config"], exercise_dir)
        except MetadataValidationError as err:
            actual_error = str(err)
            if f["expected_error_substring"] in actual_error:
                failed_as_expected = True
            else:
                actual_error = f"Error raised, but missing expected substring '{f['expected_error_substring']}': {actual_error}"
        except Exception as err:
            actual_error = f"Unexpected exception type {type(err).__name__}: {err}"

        if not failed_as_expected and actual_error is None:
            actual_error = "Validation unexpectedly passed on invalid fixture"

        fixture_results.append({
            "fixture": f["name"],
            "description": f["description"],
            "passed": failed_as_expected,
            "expected_error_substring": f["expected_error_substring"],
            "actual_error": actual_error,
        })

    return fixture_results


def main():
    try:
        root = find_root()
    except MetadataValidationError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    exercise_dir = root / ASSIGNMENT
    config_path = exercise_dir / CONFIG_RELATIVE

    print(f"=== Validating Exercise Metadata for Poker ===")
    print(f"Repository Root:    {root}")
    print(f"Exercise Directory: {exercise_dir}")
    print(f"Config File:        {config_path}")

    # Validate actual config.json
    try:
        resolved = validate_file(config_path, exercise_dir)
        print("\n[PASS] Real config.json validated successfully:")
        for category, items in resolved.items():
            for rel, abs_path in items:
                print(f"  - files.{category}: {rel} -> {abs_path}")
    except MetadataValidationError as err:
        print(f"\n[FAIL] Real config.json validation failed: {err}", file=sys.stderr)
        return 1

    # Run fixture tests
    print("\n=== Testing Invalid Metadata Fixtures ===")
    fixture_results = run_fixtures(exercise_dir)
    all_fixtures_passed = True
    for res in fixture_results:
        status = "PASS" if res["passed"] else "FAIL"
        print(f"[{status}] Fixture '{res['fixture']}': {res['description']}")
        print(f"       Observed Error: {res['actual_error']}")
        if not res["passed"]:
            all_fixtures_passed = False

    if not all_fixtures_passed:
        print("\nERROR: One or more invalid fixture checks did not fail for the intended reason", file=sys.stderr)
        return 1

    print("\nAll metadata validations and fixture rejection checks succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

