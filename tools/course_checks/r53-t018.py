#!/usr/bin/env python3
"""Check that the file paths in an exercise config stay inside the exercise."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXERCISE = ROOT / "exercises" / "practice" / "luhn"


def validate_metadata(exercise_dir):
    exercise = Path(exercise_dir).resolve()
    config_path = exercise / ".meta" / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file does not exist: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Could not parse {config_path}: {error}") from error

    files = config.get("files")
    if not isinstance(files, dict):
        raise ValueError("The config must contain a files object.")

    checked = []
    for role, paths in files.items():
        if not isinstance(paths, list):
            raise ValueError(f"The files entry for {role!r} must be a list.")
        for file_path in paths:
            if not isinstance(file_path, str) or not file_path:
                raise ValueError(f"The files entry for {role!r} has an invalid path.")

            resolved_path = (exercise / file_path).resolve()
            try:
                resolved_path.relative_to(exercise)
            except ValueError as error:
                raise ValueError(
                    f"Path {file_path!r} escapes the exercise directory."
                ) from error

            if not resolved_path.is_file():
                raise FileNotFoundError(
                    f"Declared {role} file does not exist: {file_path}"
                )
            checked.append((role, file_path))

    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exercise-dir",
        type=Path,
        default=DEFAULT_EXERCISE,
        help="Exercise directory to validate (defaults to the Luhn exercise).",
    )
    arguments = parser.parse_args()

    try:
        checked = validate_metadata(arguments.exercise_dir)
    except (FileNotFoundError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(
        f"PASS: checked {len(checked)} declared file paths in "
        f"{arguments.exercise_dir.resolve()}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
