import json
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_EXERCISE_DIR = os.path.join(
    REPO_ROOT, "exercises", "practice", "split-second-stopwatch"
)

REQUIRED_ROLES = ("solution", "test", "example")
ALLOWED_ROLES = ("solution", "test", "example", "editor")


class MetadataValidationError(Exception):
    """Raised when exercise metadata declares invalid, missing, or escaping paths."""


def validate_exercise_metadata(exercise_dir: str) -> dict:
    exercise_root = os.path.realpath(exercise_dir)
    config_path = os.path.join(exercise_root, ".meta", "config.json")
    if not os.path.isfile(config_path):
        raise MetadataValidationError(f"Missing config.json at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    files_obj = config.get("files")
    if not isinstance(files_obj, dict):
        raise MetadataValidationError("config.json missing 'files' object")

    resolved_roles = {}
    for role in ALLOWED_ROLES:
        entries = files_obj.get(role, [])
        if role in REQUIRED_ROLES and (not isinstance(entries, list) or len(entries) == 0):
            raise MetadataValidationError(f"Missing required role entries for '{role}'")
        if not isinstance(entries, list):
            raise MetadataValidationError(f"Role '{role}' must be a list of relative paths")

        resolved_list = []
        for rel_path in entries:
            if not isinstance(rel_path, str) or not rel_path.strip():
                raise MetadataValidationError(f"Invalid path entry in role '{role}': {rel_path!r}")
            if os.path.isabs(rel_path):
                raise MetadataValidationError(
                    f"Absolute path rejected in role '{role}': {rel_path}"
                )

            norm_parts = os.path.normpath(rel_path).split(os.sep)
            if ".." in norm_parts:
                raise MetadataValidationError(
                    f"Parent traversal rejected in role '{role}': {rel_path}"
                )

            candidate = os.path.realpath(os.path.join(exercise_root, rel_path))
            if os.path.commonpath([exercise_root, candidate]) != exercise_root:
                raise MetadataValidationError(
                    f"Path escapes exercise directory in role '{role}': {rel_path}"
                )

            if not os.path.isfile(candidate):
                raise MetadataValidationError(
                    f"Declared {role} file does not exist: {rel_path}"
                )

            resolved_list.append(
                {
                    "declared": rel_path,
                    "resolved": os.path.relpath(candidate, exercise_root),
                }
            )
        resolved_roles[role] = resolved_list

    return {
        "exercise_dir": os.path.relpath(exercise_root, REPO_ROOT),
        "roles": resolved_roles,
    }


def run_negative_fixtures(exercise_dir: str) -> list:
    fixtures = [
        {
            "name": "missing-reference",
            "mutate": lambda cfg, root: cfg["files"]["example"].__setitem__(
                0, ".meta/nonexistent-proof.ci.js"
            ),
            "expected_substring": "Declared example file does not exist",
        },
        {
            "name": "missing-test",
            "mutate": lambda cfg, root: cfg["files"]["test"].__setitem__(
                0, "missing-stopwatch.spec.js"
            ),
            "expected_substring": "Declared test file does not exist",
        },
        {
            "name": "outside-exercise",
            "mutate": lambda cfg, root: cfg["files"]["solution"].__setitem__(
                0, "../two-fer/two-fer.js"
            ),
            "expected_substring": "Parent traversal rejected",
        },
    ]

    results = []
    for fx in fixtures:
        with tempfile.TemporaryDirectory() as tmp_dir:
            copy_dir = os.path.join(tmp_dir, "split-second-stopwatch")
            shutil.copytree(exercise_dir, copy_dir, symlinks=True)
            cfg_path = os.path.join(copy_dir, ".meta", "config.json")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            fx["mutate"](cfg, copy_dir)
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

            try:
                validate_exercise_metadata(copy_dir)
            except MetadataValidationError as err:
                msg = str(err)
                if fx["expected_substring"] not in msg:
                    raise AssertionError(
                        f"Fixture '{fx['name']}' failed with unexpected message: {msg}"
                    )
                results.append(
                    {
                        "fixture": fx["name"],
                        "status": "REJECTED_AS_EXPECTED",
                        "reason": msg,
                    }
                )
            else:
                raise AssertionError(
                    f"Invalid metadata fixture '{fx['name']}' unexpectedly passed validation!"
                )
    return results


def main():
    exercise_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXERCISE_DIR
    valid = validate_exercise_metadata(exercise_dir)
    negatives = run_negative_fixtures(exercise_dir)
    print("=== R53-T028 Metadata & Path Check Passed ===")
    print(json.dumps({"valid_metadata": valid, "negative_fixtures": negatives}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
