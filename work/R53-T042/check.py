#!/usr/bin/env python3
"""Run Meetup tests against the maintained reference in an isolated copy."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError as error:
        raise SystemExit(
            "Python < 3.11 requires tomli; install work/R53-T042/requirements.txt"
        ) from error


ASSIGNMENT = "practice/meetup"
TARGET_CASES = {
    "d7f8eadd-d4fc-46ee-8a20-e97bd3fd01c8": "monteenth of May 2013",
    "f78373d1-cd53-4a7f-9d37-e15bf8a456b4": "monteenth of August 2013",
    "8c78bea7-a116-425b-9c6b-c9898266d92a": "monteenth of September 2013",
}
TEST_DECLARATION = re.compile(r"\b(x?test|test|xit|it)\s*\(\s*(['\"])(.*?)\2", re.S)
ASSERTION = re.compile(
    r"expect\s*\(\s*meetup\((?P<input>.*?)\)\s*\)\s*\.toEqual\s*\(\s*new Date\((?P<date>.*?)\)\s*\)",
    re.S,
)
GENERATOR_CODE = (
    "import { prepare } from './scripts/helpers.mjs'; "
    "prepare('practice/meetup');"
)


class CheckError(Exception):
    pass


def find_root():
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "scripts" / "helpers.mjs").is_file()
            and (candidate / "exercises" / ASSIGNMENT / ".meta" / "config.json").is_file()
        ):
            return candidate
    raise CheckError("Could not locate repository root")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_process(command, cwd, environment, label, processes):
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    processes.append(
        {
            "label": label,
            "command": [str(part) for part in command],
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    if result.returncode != 0:
        raise CheckError(
            "%s exited %d\n%s\n%s"
            % (label, result.returncode, result.stdout, result.stderr)
        )
    return result


def resolve_configured_files(exercise, config):
    configured = config.get("files")
    if not isinstance(configured, dict):
        raise CheckError("Meetup config is missing its files object")

    result = {}
    for kind in ("solution", "test", "example"):
        names = configured.get(kind)
        if not isinstance(names, list) or not names:
            raise CheckError("Meetup config files.%s must be a non-empty list" % kind)
        result[kind] = []
        for name in names:
            if not isinstance(name, str) or not name:
                raise CheckError("Invalid configured %s path" % kind)
            relative = Path(name.replace("%{kebab_slug}", "meetup"))
            path = (exercise / relative).resolve()
            if not path.is_relative_to(exercise.resolve()):
                raise CheckError("Configured path escapes the Meetup exercise: %s" % name)
            if not path.is_file():
                raise CheckError("Configured %s file is missing: %s" % (kind, path))
            result[kind].append((relative, path))
    return result


def declared_tests(source):
    return [
        {"name": match.group(3), "enabled": not match.group(1).startswith("x")}
        for match in TEST_DECLARATION.finditer(source)
    ]


def expected_case(source, name):
    declarations = list(TEST_DECLARATION.finditer(source))
    for declaration in declarations:
        if declaration.group(3) != name:
            continue
        block_start = declaration.end()
        block_end = source.find("});", block_start)
        if block_end < 0:
            raise CheckError("Could not locate end of test block for %r" % name)
        block = source[block_start:block_end]
        assertion = ASSERTION.search(block)
        if not assertion:
            raise CheckError("Could not extract Meetup assertion for %r" % name)
        arguments = [part.strip() for part in assertion.group("input").split(",")]
        date_arguments = [part.strip() for part in assertion.group("date").split(",")]
        if len(arguments) != 4 or len(date_arguments) != 3:
            raise CheckError("Unexpected assertion shape for %r" % name)
        year, month, day = (int(value) for value in date_arguments)
        expected_date = date(year, month + 1, day).isoformat()
        return {
            "input": "meetup(%s)" % ", ".join(arguments),
            "expected_javascript_date": "new Date(%s)" % ", ".join(date_arguments),
            "expected_calendar_date": expected_date,
        }
    raise CheckError("Canonical case has no JavaScript test: %r" % name)


def copy_generator_runtime(root, destination, exercise):
    for relative in (
        "package.json",
        "pnpm-lock.yaml",
        "config.json",
        ".npmrc",
        "babel.config.js",
        "jest.config.js",
    ):
        source = root / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for relative in ("scripts/helpers.mjs",):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    copied_exercise = destination / "exercises" / ASSIGNMENT
    copied_exercise.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(exercise, copied_exercise)
    node_modules = destination / "node_modules"
    node_modules.symlink_to(root / "node_modules", target_is_directory=True)
    return copied_exercise


def main():
    root = None
    report = {
        "task": "R53-T042",
        "success": False,
        "inputs": {},
        "expected": {},
        "actual": {},
        "checks": {},
        "processes": [],
        "tool_versions": {},
    }
    error = None
    try:
        root = find_root()
        exercise = root / "exercises" / ASSIGNMENT
        config_path = exercise / ".meta" / "config.json"
        metadata_path = exercise / ".meta" / "tests.toml"
        package_path = exercise / "package.json"
        for required in (config_path, metadata_path, package_path):
            if not required.is_file():
                raise CheckError("Required Meetup input is missing: %s" % required)

        config = json.loads(config_path.read_text(encoding="utf-8"))
        package = json.loads(package_path.read_text(encoding="utf-8"))
        metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
        files = resolve_configured_files(exercise, config)
        if len(files["solution"]) != len(files["example"]):
            raise CheckError("Configured solution and reference file counts differ")
        spec_source = "\n".join(
            path.read_text(encoding="utf-8") for _, path in files["test"]
        )
        tests = declared_tests(spec_source)
        names = [item["name"] for item in tests]
        descriptions = [
            entry.get("description")
            for entry in metadata.values()
            if isinstance(entry, dict)
        ]
        if len(names) != len(set(names)):
            raise CheckError("Duplicate test names found in configured test files")
        if set(names) != set(descriptions):
            missing = sorted(set(descriptions) - set(names))
            extra = sorted(set(names) - set(descriptions))
            raise CheckError("Canonical/spec case mismatch; missing=%r extra=%r" % (missing, extra))
        for case_uuid, case_name in TARGET_CASES.items():
            if metadata.get(case_uuid, {}).get("description") != case_name:
                raise CheckError("Canonical UUID/name mismatch for %s" % case_uuid)

        target_results = {
            name: expected_case(spec_source, name) for name in TARGET_CASES.values()
        }
        learner_hash_before = {
            relative.as_posix(): sha256(path) for relative, path in files["solution"]
        }
        spec_hash_before = {
            relative.as_posix(): sha256(path) for relative, path in files["test"]
        }

        root_package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        lockfile = root / "pnpm-lock.yaml"
        if not lockfile.is_file() or not root_package.get("packageManager", "").startswith("pnpm@"):
            raise CheckError("Root pnpm lockfile/packageManager is required")
        package_manager = root_package["packageManager"]
        if package.get("packageManager") != package_manager:
            raise CheckError("Meetup packageManager differs from the root packageManager")
        test_script = package.get("scripts", {}).get("test")
        if not isinstance(test_script, str) or not test_script.strip():
            raise CheckError("Meetup package.json has no test script")

        environment = os.environ.copy()
        environment["PATH"] = str(root / "node_modules" / ".bin") + os.pathsep + environment.get("PATH", "")
        environment["NODE_PATH"] = str(root / "node_modules")
        environment["CI"] = "1"
        versions = {}
        for label, command in (
            ("node", ["node", "--version"]),
            ("pnpm", ["corepack", "pnpm", "--version"]),
        ):
            result = run_process(command, root, environment, label + " version", report["processes"])
            versions[label] = result.stdout.strip()
        versions["python"] = sys.version.split()[0]
        versions["tomli"] = getattr(tomllib, "__version__", "stdlib")
        if versions["pnpm"] != package_manager.split("@", 1)[1]:
            raise CheckError("pnpm version does not match packageManager: %s" % package_manager)

        with tempfile.TemporaryDirectory(prefix="meetup-r53-t042-check-") as temporary:
            temporary_root = Path(temporary) / "repository"
            temporary_root.mkdir()
            copied_exercise = copy_generator_runtime(root, temporary_root, exercise)

            generator_command = [
                "corepack",
                "pnpm",
                "node",
                "--input-type=module",
                "-e",
                GENERATOR_CODE,
            ]
            run_process(
                generator_command,
                temporary_root,
                environment,
                "Meetup prepare generator",
                report["processes"],
            )
            generated_exercise = temporary_root / "tmp_exercises" / ASSIGNMENT
            generated_test_paths = [generated_exercise / relative for relative, _ in files["test"]]
            generated_sources = []
            for generated_test in generated_test_paths:
                if not generated_test.is_file():
                    raise CheckError("Track generator did not create %s" % generated_test)
                generated_sources.append(generated_test.read_text(encoding="utf-8"))
            generated_source = "\n".join(generated_sources)
            generated_tests = declared_tests(generated_source)
            if len(generated_tests) != len(tests) or {item["name"] for item in generated_tests} != set(names):
                raise CheckError("Track generator dropped or added Meetup tests")
            if any(not item["enabled"] for item in generated_tests):
                raise CheckError("Track generator left an optional Meetup test disabled")

            for (relative, _), source in zip(files["test"], generated_sources):
                (copied_exercise / relative).write_text(source, encoding="utf-8")
            for (solution_relative, _solution_path), (example_relative, example_path) in zip(
                files["solution"], files["example"]
            ):
                shutil.copy2(example_path, copied_exercise / solution_relative)

            json_result = Path(temporary) / "jest-result.json"
            test_script_args = [
                "--runInBand",
                "--watch=false",
                "--runTestsByPath",
                *[relative.as_posix() for relative, _ in files["test"]],
                "--json",
                "--outputFile",
                str(json_result),
            ]
            test_command = [
                "corepack",
                "pnpm",
                "--dir",
                str(copied_exercise),
                "run",
                "test",
                *test_script_args,
            ]
            test_process = run_process(
                test_command,
                root,
                environment,
                "Meetup package test script",
                report["processes"],
            )
            if not json_result.is_file():
                raise CheckError("Jest did not write its JSON result")
            jest_result = json.loads(json_result.read_text(encoding="utf-8"))
            executed = jest_result.get("numTotalTests")
            passed = jest_result.get("numPassedTests")
            failed = jest_result.get("numFailedTests")
            if not all(isinstance(value, int) for value in (executed, passed, failed)):
                raise CheckError("Jest JSON result omitted test counts")
            if executed == 0:
                raise CheckError("Jest executed zero tests")
            if executed != len(tests):
                raise CheckError("Jest executed %d tests; expected %d" % (executed, len(tests)))
            if failed != 0 or passed != executed:
                raise CheckError("Jest assertion failures: %d failed, %d passed" % (failed, passed))
            if test_process.returncode != 0:
                raise CheckError("Meetup test script exited non-zero")

            statuses = {}
            for suite in jest_result.get("testResults", []):
                for assertion in suite.get("assertionResults", []):
                    statuses[assertion.get("title")] = assertion.get("status")
            for name in TARGET_CASES.values():
                if statuses.get(name) != "passed":
                    raise CheckError("Named Meetup test did not pass: %s" % name)

            report["actual"] = {
                "tests_executed": executed,
                "tests_passed": passed,
                "tests_failed": failed,
                "named_cases": [
                    {
                        "uuid": case_uuid,
                        "name": name,
                        **target_results[name],
                        "status": statuses.get(name),
                    }
                    for case_uuid, name in TARGET_CASES.items()
                ],
                "reference_substitution": {
                    "copied_reference": [str(path.relative_to(root)) for _, path in files["example"]],
                    "temporary_solution_files": [item.as_posix() for item, _ in files["solution"]],
                },
                "generated_test_count": len(generated_tests),
                "temporary_copy_test_file_sha256": {
                    relative.as_posix(): sha256(copied_exercise / relative)
                    for relative, _ in files["test"]
                },
            }
            report["checks"].update(
                {
                    "config_paths_resolved": True,
                    "all_hidden_exercise_files_copied": True,
                    "canonical_and_spec_cases_match": True,
                    "all_generated_tests_enabled": True,
                    "all_three_monteenth_cases_pass": True,
                    "test_count_nonzero_and_complete": True,
                    "assertions_passed": True,
                }
            )

        learner_hash_after = {
            relative.as_posix(): sha256(path) for relative, path in files["solution"]
        }
        spec_hash_after = {relative.as_posix(): sha256(path) for relative, path in files["test"]}
        if learner_hash_after != learner_hash_before:
            raise CheckError("Learner solution changed during the check")
        if spec_hash_after != spec_hash_before:
            raise CheckError("Maintained Meetup tests changed during the check")
        report["checks"]["learner_solution_unchanged"] = True
        report["checks"]["maintained_spec_unchanged"] = True
        report["actual"]["learner_solution_sha256"] = learner_hash_after
        report["actual"]["maintained_spec_sha256_before"] = spec_hash_before
        report["actual"]["maintained_spec_sha256_after"] = spec_hash_after
        report["inputs"] = {
            "config": str(config_path.relative_to(root)),
            "package_test_script": test_script,
            "configured_paths": {
                kind: [relative.as_posix() for relative, _ in configured]
                for kind, configured in files.items()
            },
            "canonical_test_count": len(metadata),
            "test_names": names,
        }
        report["expected"] = {
            "tests_executed": len(tests),
            "tests_failed": 0,
            "named_cases": target_results,
        }
        report["tool_versions"] = versions
        report["success"] = True
    except Exception as exception:
        error = "%s: %s" % (type(exception).__name__, exception)
        report["error"] = error
    finally:
        evidence = Path(__file__).resolve().parent / "evidence.json"
        try:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as write_error:
            report["success"] = False
            error = "Could not save evidence: %s" % write_error
        actual = report.get("actual", {})
        print("Meetup reference verification")
        print("Tests executed: %s" % actual.get("tests_executed", 0))
        print("Tests passed: %s" % actual.get("tests_passed", 0))
        print("Tests failed: %s" % actual.get("tests_failed", 0))
        for case in actual.get("named_cases", []):
            print("%s: %s (%s)" % (case["name"], case["status"], case["expected_calendar_date"]))
        print("Learner solution unchanged: %s" % report.get("checks", {}).get("learner_solution_unchanged", False))
        print("Evidence: %s" % (evidence.relative_to(root) if root else evidence))
        if report["success"]:
            print("Result: PASS")
        else:
            print("Result: FAIL" + (" (%s)" % error if error else ""), file=sys.stderr)

    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())