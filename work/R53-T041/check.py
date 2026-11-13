#!/usr/bin/env python3
"""Verify the Sieve reference implementation in an isolated exercise copy."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "sieve"
EVIDENCE = Path(__file__).resolve().parent / "evidence.json"
INITIAL_COUNTS = {"included": 1, "excluded": 4}
CASES = {
    "88529125-c4ce-43cc-bb36-1eb4ddd7b44f": {
        "description": "no primes under two",
        "test_name": "no primes under two",
    },
    "4afe9474-c705-4477-9923-840e1024cc2b": {
        "description": "find first prime",
        "test_name": "finds first prime",
    },
    "974945d8-8cd9-4f00-9463-7d813c7f17b7": {
        "description": "find primes up to 10",
        "test_name": "finds primes up to 10",
    },
    "2e2417b7-3f3a-452a-8594-b9af08af6d82": {
        "description": "limit is prime",
        "test_name": "limit is prime",
    },
    "92102a05-4c7c-47de-9ed0-b7d5fcd00f21": {
        "description": "find primes up to 1000",
        "test_name": "finds primes up to 1000",
    },
}
TEST_PATTERN = re.compile(r"\b(x?test|xit|it)\s*\(\s*(['\"])(.*?)\2", re.S)


class VerificationError(Exception):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_config_paths(exercise, config):
    files = config.get("files")
    if not isinstance(files, dict):
        raise VerificationError("Configuration is missing its files object")

    resolved = {}
    for kind in ("solution", "test", "example"):
        paths = files.get(kind)
        if not isinstance(paths, list) or not paths:
            raise VerificationError("Configuration files.%s must be a non-empty list" % kind)
        resolved[kind] = []
        for item in paths:
            if not isinstance(item, str) or not item:
                raise VerificationError("Configuration files.%s contains an invalid path" % kind)
            relative = item.replace("%{kebab_slug}", exercise.name)
            path = exercise / relative
            if not path.is_file():
                raise VerificationError("Configured %s file is missing: %s" % (kind, path))
            resolved[kind].append((relative, path))
    return resolved


def read_test_cases(source):
    return [
        {"name": match.group(3), "enabled": not match.group(1).startswith("x")}
        for match in TEST_PATTERN.finditer(source)
    ]


def enable_optional_tests(source):
    source = re.sub(r"\bxtest(?=\s*\()", "test", source)
    source = re.sub(r"\bxit(?=\s*\()", "it", source)
    source = re.sub(r"\bxdescribe(?=\s*\()", "describe", source)
    return source


def count_cases(test_cases):
    return {
        "included": sum(case["enabled"] for case in test_cases),
        "excluded": sum(not case["enabled"] for case in test_cases),
    }


def assert_jest_success(return_code, result):
    if not isinstance(result, dict):
        raise VerificationError("Jest did not produce a valid JSON result")
    total = result.get("numTotalTests")
    passed = result.get("numPassedTests")
    failed = result.get("numFailedTests")
    if not all(isinstance(value, int) for value in (total, passed, failed)):
        raise VerificationError("Jest JSON is missing test counts")
    if total == 0:
        raise VerificationError("Jest executed zero tests")
    if failed:
        raise VerificationError("Jest reported %d failed test(s)" % failed)
    if return_code != 0:
        raise VerificationError("Test process exited with status %d" % return_code)
    return {"executed": total, "passed": passed, "failed": failed}


def format_summary(counts, initial_counts, final_counts, versions, temp_result):
    return "\n".join(
        [
            "Sieve reference verification",
            "Tests executed: %s" % counts.get("executed", 0),
            "Tests passed: %s" % counts.get("passed", 0),
            "Tests failed: %s" % counts.get("failed", 0),
            "Canonical cases before: %d included, %d excluded"
            % (initial_counts["included"], initial_counts["excluded"]),
            "Canonical cases after: %d included, %d excluded"
            % (final_counts["included"], final_counts["excluded"]),
            "Tool versions: Node %s; pnpm %s; Python %s; tomli %s"
            % (
                versions.get("node", "unavailable"),
                versions.get("pnpm", "unavailable"),
                versions.get("python", sys.version.split()[0]),
                versions.get("tomli", "unavailable"),
            ),
            "Temporary-copy verification: %s" % temp_result,
        ]
    )


def expect_rejection(action):
    try:
        action()
    except VerificationError:
        return True
    return False


def verify_checker_guards():
    passing_result = {
        "numTotalTests": 1,
        "numPassedTests": 1,
        "numFailedTests": 0,
    }
    checks = {
        "non_zero_exit_rejected": expect_rejection(
            lambda: assert_jest_success(1, passing_result)
        ),
        "zero_tests_rejected": expect_rejection(
            lambda: assert_jest_success(
                0,
                {"numTotalTests": 0, "numPassedTests": 0, "numFailedTests": 0},
            )
        ),
        "assertion_failure_rejected": expect_rejection(
            lambda: assert_jest_success(
                0,
                {"numTotalTests": 1, "numPassedTests": 0, "numFailedTests": 1},
            )
        ),
    }
    rendered = format_summary(
        {"executed": 3, "passed": 3, "failed": 0},
        INITIAL_COUNTS,
        INITIAL_COUNTS,
        {},
        "PASS",
    )
    checks["executed_count_reported"] = "Tests executed: 3" in rendered
    if not all(checks.values()):
        raise VerificationError("A checker failure-handling self-test failed")
    return checks


def run_version(command):
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise VerificationError(
            "Version command failed (%s): %s" % (" ".join(command), result.stderr.strip())
        )
    return result.stdout.strip()


def expected_test_statuses(jest_result):
    actual = {}
    for suite in jest_result.get("testResults", []):
        for assertion in suite.get("assertionResults", []):
            actual[assertion.get("title")] = assertion.get("status")
    return actual


def main():
    learner_solution = EXERCISE / "sieve.js"
    learner_hash_before = sha256(learner_solution) if learner_solution.is_file() else None
    report = {
        "task": "R53-T041",
        "inputs": {},
        "expected": {
            "initial_canonical_counts": INITIAL_COUNTS,
            "all_five_reference_cases_pass": True,
        },
        "actual": {},
        "checks": {},
        "process": {},
        "tool_versions": {},
        "temporary_copy_result": "NOT RUN",
        "success": False,
    }
    error = None
    temp_result = "FAIL"

    try:
        root_package_path = ROOT / "package.json"
        exercise_package_path = EXERCISE / "package.json"
        config_path = EXERCISE / ".meta" / "config.json"
        tests_toml_path = EXERCISE / ".meta" / "tests.toml"
        for required in (root_package_path, exercise_package_path, config_path, tests_toml_path,
                         learner_solution):
            if not required.is_file():
                raise VerificationError("Required file is missing: %s" % required)

        root_package = json.loads(root_package_path.read_text(encoding="utf-8"))
        exercise_package = json.loads(exercise_package_path.read_text(encoding="utf-8"))
        config = json.loads(config_path.read_text(encoding="utf-8"))
        canonical = tomllib.loads(tests_toml_path.read_text(encoding="utf-8"))
        report["checks"]["toml_parsing"] = True

        resolved = resolve_config_paths(EXERCISE, config)
        report["checks"]["configuration_path_resolution"] = True
        reference_paths = resolved["example"]
        if not reference_paths:
            raise VerificationError("Configuration has no reference implementation")
        reference_path = reference_paths[0][1]
        if not reference_path.is_file():
            raise VerificationError("Reference implementation is missing: %s" % reference_path)

        if "pnpm-lock.yaml" not in {path.name for path in ROOT.iterdir()}:
            raise VerificationError("pnpm-lock.yaml is required to select the package manager")
        package_manager = root_package.get("packageManager", "")
        if not package_manager.startswith("pnpm@"):
            raise VerificationError("Root packageManager must select pnpm")
        versions = {
            "node": run_version(["node", "--version"]),
            "pnpm": run_version(["corepack", "pnpm", "--version"]),
            "python": sys.version.split()[0],
            "tomli": getattr(tomllib, "__version__", "stdlib"),
        }
        expected_pnpm = package_manager.split("@", 1)[1]
        if versions["pnpm"] != expected_pnpm:
            raise VerificationError(
                "Installed pnpm %s does not match root packageManager %s"
                % (versions["pnpm"], package_manager)
            )
        report["tool_versions"] = versions

        original_cases = []
        test_inputs = []
        for relative, path in resolved["test"]:
            source = path.read_text(encoding="utf-8")
            original_cases.extend(read_test_cases(source))
            test_inputs.append({"path": relative, "source": source})
        initial_counts = count_cases(original_cases)
        if initial_counts != INITIAL_COUNTS:
            raise VerificationError(
                "Current canonical selection %r differs from recorded initial counts %r"
                % (initial_counts, INITIAL_COUNTS)
            )
        for case_uuid, case in CASES.items():
            metadata = canonical.get(case_uuid)
            if not isinstance(metadata, dict) or metadata.get("description") != case["description"]:
                raise VerificationError("Canonical TOML entry mismatch for %s" % case_uuid)
            if not any(item["name"] == case["test_name"] for item in original_cases):
                raise VerificationError("JavaScript test missing for %s" % case_uuid)

        report["inputs"] = {
            "config": str(config_path.relative_to(ROOT)),
            "configured_files": {
                kind: [relative for relative, _ in items]
                for kind, items in resolved.items()
            },
            "reference_implementation": str(reference_path.relative_to(ROOT)),
            "test_script": exercise_package.get("scripts", {}).get("test"),
            "canonical_cases": [
                {
                    "uuid": case_uuid,
                    "description": case["description"],
                    "test_name": case["test_name"],
                    "selected_before_verification": next(
                        item["enabled"]
                        for item in original_cases
                        if item["name"] == case["test_name"]
                    ),
                }
                for case_uuid, case in CASES.items()
            ],
            "initial_canonical_counts": initial_counts,
        }

        report["checks"].update(verify_checker_guards())
        report["checks"]["canonical_uuid_and_test_mapping"] = True

        root_lock_manager = ["corepack", "pnpm"]
        test_script = exercise_package.get("scripts", {}).get("test")
        if not isinstance(test_script, str) or not test_script.strip():
            raise VerificationError("Exercise package.json has no test script")

        with tempfile.TemporaryDirectory(prefix="sieve-r53-t041-") as temporary:
            temp_exercise = Path(temporary) / "sieve"
            shutil.copytree(EXERCISE, temp_exercise)
            original_files = {
                str(path.relative_to(EXERCISE))
                for path in EXERCISE.rglob("*")
                if path.is_file()
            }
            copied_files = {
                str(path.relative_to(temp_exercise))
                for path in temp_exercise.rglob("*")
                if path.is_file()
            }
            report["checks"]["all_exercise_files_copied_including_hidden"] = (
                copied_files == original_files
            )
            if copied_files != original_files:
                raise VerificationError("Temporary copy is missing exercise files")

            copied_package_path = temp_exercise / "package.json"
            copied_package = json.loads(copied_package_path.read_text(encoding="utf-8"))
            copied_package["packageManager"] = package_manager
            copied_package_path.write_text(
                json.dumps(copied_package, indent=2) + "\n", encoding="utf-8"
            )

            for relative, _ in resolved["solution"]:
                copied_solution = temp_exercise / relative
                copied_solution.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(reference_path, copied_solution)
                if copied_solution.read_bytes() != reference_path.read_bytes():
                    raise VerificationError("Reference substitution did not match in temp copy")
            report["checks"]["reference_substituted_only_in_temporary_copy"] = True

            transformed_cases = []
            for test_input in test_inputs:
                relative = test_input["path"]
                source = test_input["source"]
                transformed = enable_optional_tests(source)
                copied_test = temp_exercise / relative
                copied_test.write_text(transformed, encoding="utf-8")
                transformed_cases.extend(read_test_cases(transformed))
            enabled_counts = count_cases(transformed_cases)
            if enabled_counts["excluded"] != 0:
                raise VerificationError("One or more canonical tests remain disabled in temp copy")
            test_names = {item["name"] for item in transformed_cases}
            missing_cases = [
                case["test_name"]
                for case in CASES.values()
                if case["test_name"] not in test_names
            ]
            if missing_cases:
                raise VerificationError("Temporary copy is missing canonical tests: %s" % missing_cases)
            report["checks"]["all_five_canonical_cases_enabled_in_temp_copy"] = True

            json_result_path = Path(temporary) / "jest-result.json"
            relative_tests = [relative for relative, _ in resolved["test"]]
            command = (
                root_lock_manager
                + ["--dir", str(temp_exercise), "run", "test"]
                + ["--runInBand", "--watch=false", "--runTestsByPath"]
                + relative_tests
                + ["--json", "--outputFile", str(json_result_path)]
            )
            environment = os.environ.copy()
            environment["PATH"] = str(ROOT / "node_modules" / ".bin") + os.pathsep + environment.get("PATH", "")
            environment["NODE_PATH"] = str(ROOT / "node_modules")
            environment["CI"] = "1"
            process = subprocess.run(
                command,
                cwd=str(ROOT),
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            report["process"] = {
                "command": command,
                "return_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
            if not json_result_path.is_file():
                raise VerificationError("Jest did not create its JSON result file")
            jest_result = json.loads(json_result_path.read_text(encoding="utf-8"))
            test_counts = assert_jest_success(process.returncode, jest_result)
            if test_counts["executed"] != len(transformed_cases):
                raise VerificationError(
                    "Jest executed %d tests; expected %d declared cases"
                    % (test_counts["executed"], len(transformed_cases))
                )
            actual_statuses = expected_test_statuses(jest_result)
            case_results = []
            for case_uuid, case in CASES.items():
                actual_status = actual_statuses.get(case["test_name"], "missing")
                case_results.append(
                    {
                        "uuid": case_uuid,
                        "test_name": case["test_name"],
                        "expected_reference_status": "passed",
                        "actual_reference_status": actual_status,
                    }
                )
                if actual_status != "passed":
                    raise VerificationError(
                        "Canonical test %s did not pass in reference verification"
                        % case["test_name"]
                    )

            final_counts = count_cases(original_cases)
            if final_counts != INITIAL_COUNTS:
                raise VerificationError("Canonical inclusion state changed during verification")
            report["actual"] = {
                "canonical_counts_before": initial_counts,
                "canonical_counts_after": final_counts,
                "temporary_copy_enabled_counts": enabled_counts,
                "tests": test_counts,
                "canonical_case_results": case_results,
            }
            report["checks"]["executed_test_count_matches_declared_cases"] = True
            report["checks"]["all_five_canonical_cases_pass"] = True
            temp_result = "PASS"

        learner_hash_after = sha256(learner_solution)
        report["checks"]["learner_solution_unchanged"] = learner_hash_after == learner_hash_before
        report["actual"]["learner_solution_sha256_before"] = learner_hash_before
        report["actual"]["learner_solution_sha256_after"] = learner_hash_after
        if learner_hash_after != learner_hash_before:
            raise VerificationError("Learner solution changed during reference verification")

        report["success"] = True
    except Exception as exception:
        error = "%s: %s" % (type(exception).__name__, exception)
        report["error"] = error
    finally:
        if learner_solution.is_file() and learner_hash_before is not None:
            learner_hash_after = sha256(learner_solution)
            report.setdefault("checks", {})["learner_solution_unchanged"] = (
                learner_hash_after == learner_hash_before
            )
            report.setdefault("actual", {})["learner_solution_sha256_before"] = learner_hash_before
            report["actual"]["learner_solution_sha256_after"] = learner_hash_after
            if learner_hash_after != learner_hash_before:
                report["success"] = False
                report["error"] = "Learner solution changed during reference verification"
                temp_result = "FAIL"
        report["temporary_copy_result"] = temp_result
        try:
            EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            EVIDENCE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as write_error:
            report["success"] = False
            report["error"] = "Could not write evidence: %s" % write_error
        summary_counts = report.get("actual", {}).get(
            "tests", {"executed": 0, "passed": 0, "failed": 0}
        )
        initial_counts = report.get("inputs", {}).get("initial_canonical_counts", INITIAL_COUNTS)
        final_counts = report.get("actual", {}).get("canonical_counts_after", INITIAL_COUNTS)
        print(
            format_summary(
                summary_counts,
                initial_counts,
                final_counts,
                report.get("tool_versions", {}),
                temp_result,
            )
        )
        if error or not report["success"]:
            print("Result: FAIL" + (" (%s)" % error if error else ""), file=sys.stderr)
        else:
            print("Result: PASS")

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())