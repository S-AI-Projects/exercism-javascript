#!/usr/bin/env python3
"""Verify Word Search reference behavior and a temporary boundary mutant."""

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
    try:
        import tomli as tomllib
    except ModuleNotFoundError as error:
        raise SystemExit(
            "Python < 3.11 requires tomli; install work/R53-T043/requirements.txt"
        ) from error


ASSIGNMENT = Path("exercises/practice/word-search")
INITIAL_CASE_ID = "b4057815-0d01-41f0-9119-6a91f54b2a0a"
HORIZONTAL_CASE_ID = "6b22bcc5-6cbf-4674-931b-d2edbff73132"
INITIAL_TESTS = [
    "Should accept an initial game grid",
    "Can accept a target search word",
]
HORIZONTAL_TEST = "Should locate a word written left to right"
MUTATION_FROM = "if (startCol) {"
MUTATION_TO = "if (startCol > 1) {"
TEST_DECLARATION = re.compile(r"\b(x?test|test|xit|it)\s*\(\s*(['\"])(.*?)\2", re.S)
EXPECTED_COORDINATES = re.compile(
    r"expectedResults\s*=\s*\{\s*clojure\s*:\s*\{\s*"
    r"start\s*:\s*\[(\d+)\s*,\s*(\d+)\]\s*,\s*"
    r"end\s*:\s*\[(\d+)\s*,\s*(\d+)\]\s*,?\s*\}\s*,?\s*\}",
    re.S,
)
TARGET_ARGUMENTS = re.compile(r"\.find\s*\(\s*\[\s*['\"]([^'\"]+)['\"]\s*\]\s*\)")
DIAGNOSTIC_GRID = ["ab", "cd"]
DIAGNOSTIC_WORD = "ab"
DIAGNOSTIC_EXPECTED = {"ab": {"start": [1, 1], "end": [1, 2]}}
NODE_DIAGNOSTIC = (
    "const WordSearch = require(process.env.WORD_SEARCH_SOLUTION); "
    "const grid = JSON.parse(process.env.WORD_SEARCH_GRID); "
    "const word = process.env.WORD_SEARCH_WORD; "
    "process.stdout.write(JSON.stringify(new WordSearch(grid).find([word]), "
    "(key, value) => value === undefined ? '__undefined__' : value));"
)


class CheckError(Exception):
    pass


def find_root():
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "package.json").is_file()
            and (candidate / "pnpm-lock.yaml").is_file()
            and (candidate / "scripts" / "helpers.mjs").is_file()
            and (candidate / ASSIGNMENT / ".meta" / "config.json").is_file()
        ):
            return candidate
    raise CheckError("Could not locate repository root")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_process(command, cwd, environment, label, processes, accepted_codes=(0,)):
    result = subprocess.run(
        [str(part) for part in command],
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
    if result.returncode not in accepted_codes:
        raise CheckError(
            "%s returned unexpected status %d\n%s\n%s"
            % (label, result.returncode, result.stdout, result.stderr)
        )
    return result


def resolve_configured_files(exercise, config):
    configured = config.get("files")
    if not isinstance(configured, dict):
        raise CheckError("Word Search config is missing its files object")
    resolved = {}
    for kind in ("solution", "test", "example"):
        names = configured.get(kind)
        if not isinstance(names, list) or not names:
            raise CheckError("Config files.%s must be a non-empty list" % kind)
        resolved[kind] = []
        for name in names:
            if not isinstance(name, str) or not name:
                raise CheckError("Invalid configured %s path" % kind)
            relative = Path(name.replace("%{kebab_slug}", "word-search"))
            path = (exercise / relative).resolve()
            if not path.is_relative_to(exercise.resolve()):
                raise CheckError("Configured path escapes the exercise: %s" % name)
            if not path.is_file():
                raise CheckError("Configured %s file is missing: %s" % (kind, path))
            resolved[kind].append((relative, path))
    return resolved


def enable_optional_tests(source):
    source = re.sub(r"\bx(test|it)\(", "test(", source)
    return re.sub(r"\bxdescribe\(", "describe(", source)


def test_names(source):
    return [match.group(3) for match in TEST_DECLARATION.finditer(source)]


def test_result_for(result, title):
    found = []
    for suite in result.get("testResults", []):
        for assertion in suite.get("assertionResults", []):
            if assertion.get("title") == title:
                found.append(assertion)
    if len(found) != 1:
        raise CheckError("Expected exactly one Jest assertion result for %r" % title)
    return found[0]


def parse_jest_result(path):
    if not path.is_file():
        raise CheckError("Jest did not write its JSON result: %s" % path)
    result = json.loads(path.read_text(encoding="utf-8"))
    for field in ("numTotalTests", "numPassedTests", "numFailedTests"):
        if not isinstance(result.get(field), int):
            raise CheckError("Jest JSON omitted %s" % field)
    return result


def prepare_copy(exercise, files, temporary, mutate):
    copy = Path(temporary) / ("mutated" if mutate else "original")
    shutil.copytree(exercise, copy)
    learner_hashes = {relative: sha256(path) for relative, path in files["solution"]}

    for (solution_relative, _), (example_relative, _) in zip(
        files["solution"], files["example"]
    ):
        copied_example = copy / example_relative
        content = copied_example.read_text(encoding="utf-8")
        if mutate:
            if content.count(MUTATION_FROM) != 2:
                raise CheckError("Expected exactly two horizontal start checks in copied reference")
            content = content.replace(MUTATION_FROM, MUTATION_TO, 1)
            if content.count(MUTATION_TO) != 1:
                raise CheckError("Mutation was not applied exactly once in the copied reference")
            copied_example.write_text(content, encoding="utf-8")
        shutil.copy2(copied_example, copy / solution_relative)

    all_test_names = []
    for relative, _ in files["test"]:
        test_path = copy / relative
        source = test_path.read_text(encoding="utf-8")
        transformed = enable_optional_tests(source)
        test_path.write_text(transformed, encoding="utf-8")
        all_test_names.extend(test_names(transformed))

    if len(all_test_names) != len(set(all_test_names)):
        raise CheckError("Duplicate test names in copied Word Search suite")

    package = json.loads((copy / "package.json").read_text(encoding="utf-8"))
    test_script = package.get("scripts", {}).get("test")
    if not isinstance(test_script, str) or not test_script.strip():
        raise CheckError("Word Search package.json has no test script")
    return copy, test_script, all_test_names


def direct_result(root, exercise_copy, solution_relative, grid, word, environment, label, processes):
    direct_env = environment.copy()
    direct_env["WORD_SEARCH_SOLUTION"] = str(exercise_copy / solution_relative)
    direct_env["WORD_SEARCH_GRID"] = json.dumps(grid)
    direct_env["WORD_SEARCH_WORD"] = word
    process = run_process(
        ["node", "-e", NODE_DIAGNOSTIC],
        root,
        direct_env,
        label,
        processes,
    )
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise CheckError("%s did not return valid JSON: %s" % (label, process.stdout)) from error


def run_jest(root, exercise_copy, test_relatives, environment, processes, label, title=None):
    result_fd, result_name = tempfile.mkstemp(prefix="word-search-jest-", suffix=".json")
    os.close(result_fd)
    result_path = Path(result_name)
    result_path.unlink()
    command = [
        "corepack",
        "pnpm",
        "--dir",
        str(exercise_copy),
        "run",
        "test",
        "--runInBand",
        "--watch=false",
        "--runTestsByPath",
        *[relative.as_posix() for relative in test_relatives],
        "--json",
        "--outputFile",
        str(result_path),
    ]
    if title:
        command.append("--testNamePattern=%s" % title)
    accepted = (0, 1) if title else (0,)
    try:
        process = run_process(command, root, environment, label, processes, accepted_codes=accepted)
        result = parse_jest_result(result_path)
        return process, result
    finally:
        result_path.unlink(missing_ok=True)


def main():
    root = None
    report = {
        "task": "R53-T043",
        "success": False,
        "inputs": {},
        "mutation": {
            "location": "first forward-search condition in searchHorizontally",
            "original": MUTATION_FROM,
            "mutated": MUTATION_TO,
            "temporary_copy_only": True,
        },
        "original_reference": {},
        "mutated_reference": {},
        "processes": [],
        "tool_versions": {},
        "checks": {},
    }
    error = None
    evidence_path = Path(__file__).resolve().parent / "evidence.json"

    try:
        root = find_root()
        exercise = root / ASSIGNMENT
        config_path = exercise / ".meta" / "config.json"
        metadata_path = exercise / ".meta" / "tests.toml"
        package_path = exercise / "package.json"
        for required in (config_path, metadata_path, package_path):
            if not required.is_file():
                raise CheckError("Required Word Search file is missing: %s" % required)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
        package = json.loads(package_path.read_text(encoding="utf-8"))
        files = resolve_configured_files(exercise, config)
        if len(files["solution"]) != len(files["example"]):
            raise CheckError("Configured solution and example counts differ")
        learner_solution = files["solution"][0][1]
        spec_source = "\n".join(path.read_text(encoding="utf-8") for _, path in files["test"])
        declared_names = test_names(spec_source)
        learner_hash_before = sha256(learner_solution)
        example_hash_before = {relative.as_posix(): sha256(path) for relative, path in files["example"]}
        test_hash_before = {relative.as_posix(): sha256(path) for relative, path in files["test"]}

        if metadata.get(INITIAL_CASE_ID, {}).get("description") != (
            "Should accept an initial game grid and a target search word"
        ):
            raise CheckError("Initial/target canonical test ID did not match tests.toml")
        if metadata.get(HORIZONTAL_CASE_ID, {}).get("description") != (
            "Should locate one word written left to right"
        ):
            raise CheckError("Horizontal canonical test ID did not match tests.toml")
        for required_name in INITIAL_TESTS + [HORIZONTAL_TEST]:
            if required_name not in declared_names:
                raise CheckError("Required JavaScript test is missing: %s" % required_name)

        horizontal_match = re.search(
            r"xtest\(\s*(['\"])" + re.escape(HORIZONTAL_TEST) + r"\1\s*,(?P<body>[\s\S]*?)\n\s*\}\);",
            spec_source,
        )
        if not horizontal_match:
            raise CheckError("Could not locate the horizontal test body")
        body = horizontal_match.group("body")
        grid_match = re.search(r"const\s+grid\s*=\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", body)
        word_match = TARGET_ARGUMENTS.search(body)
        coordinates_match = EXPECTED_COORDINATES.search(body)
        if not (grid_match and word_match and coordinates_match):
            raise CheckError("Could not extract input and expected coordinates from the existing test")
        rejecting_grid = [grid_match.group(1)]
        rejecting_word = word_match.group(1)
        coords = [int(value) for value in coordinates_match.groups()]
        existing_expected = {
            rejecting_word: {"start": coords[:2], "end": coords[2:]}
        }
        if rejecting_word != "clojure":
            raise CheckError("Existing rejecting test target changed unexpectedly")

        root_package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        package_manager = root_package.get("packageManager", "")
        if not package_manager.startswith("pnpm@") or not (root / "pnpm-lock.yaml").is_file():
            raise CheckError("Root packageManager/pnpm-lock.yaml does not select pnpm")
        if package.get("packageManager") != package_manager:
            raise CheckError("Exercise packageManager differs from root packageManager")
        environment = os.environ.copy()
        environment["PATH"] = str(root / "node_modules" / ".bin") + os.pathsep + environment.get("PATH", "")
        environment["NODE_PATH"] = str(root / "node_modules")
        environment["CI"] = "1"
        versions = {}
        for label, command in (("node", ["node", "--version"]), ("pnpm", ["corepack", "pnpm", "--version"])):
            process = run_process(command, root, environment, label + " version", report["processes"])
            versions[label] = process.stdout.strip()
        versions["python"] = sys.version.split()[0]
        versions["tomli"] = getattr(tomllib, "__version__", "stdlib")
        if versions["pnpm"] != package_manager.split("@", 1)[1]:
            raise CheckError("Installed pnpm does not match packageManager %s" % package_manager)

        with tempfile.TemporaryDirectory(prefix="word-search-r53-t043-") as temporary:
            original_copy, test_script, all_names = prepare_copy(exercise, files, temporary, False)
            if len(all_names) != len(set(all_names)):
                raise CheckError("Duplicate test names in enabled suite")
            original_solution = files["solution"][0][0]
            original_test_process, original_jest = run_jest(
                root,
                original_copy,
                [relative for relative, _ in files["test"]],
                environment,
                report["processes"],
                "full original reference test suite",
            )
            total = original_jest["numTotalTests"]
            passed = original_jest["numPassedTests"]
            failed = original_jest["numFailedTests"]
            if total == 0:
                raise CheckError("Original reference executed zero tests")
            if total != len(all_names):
                raise CheckError("Original Jest executed %d; expected %d" % (total, len(all_names)))
            if original_test_process.returncode != 0 or failed != 0 or passed != total:
                raise CheckError("Original reference suite did not pass all tests")
            for title in INITIAL_TESTS + [HORIZONTAL_TEST]:
                if test_result_for(original_jest, title).get("status") != "passed":
                    raise CheckError("Original reference did not pass %s" % title)

            original_diagnostic = direct_result(
                root,
                original_copy,
                original_solution,
                DIAGNOSTIC_GRID,
                DIAGNOSTIC_WORD,
                environment,
                "original minimized diagnostic input",
                report["processes"],
            )
            if original_diagnostic != {DIAGNOSTIC_WORD: DIAGNOSTIC_EXPECTED[DIAGNOSTIC_WORD]}:
                raise CheckError("Original reference failed the minimized diagnostic input")
            original_test_input = direct_result(
                root,
                original_copy,
                original_solution,
                rejecting_grid,
                rejecting_word,
                environment,
                "original existing-test input",
                report["processes"],
            )
            if original_test_input != existing_expected:
                raise CheckError("Original reference did not produce the existing test's expected result")

            mutated_copy, _, mutated_names = prepare_copy(exercise, files, temporary, True)
            if mutated_names != all_names:
                raise CheckError("Original and mutant copies do not have identical enabled test inputs")
            mutated_solution = files["solution"][0][0]
            mutated_diagnostic = direct_result(
                root,
                mutated_copy,
                mutated_solution,
                DIAGNOSTIC_GRID,
                DIAGNOSTIC_WORD,
                environment,
                "mutant minimized diagnostic input",
                report["processes"],
            )
            if mutated_diagnostic == original_diagnostic:
                raise CheckError("Mutation produced no observable diagnostic behavior change")
            mutated_rejecting_input = direct_result(
                root,
                mutated_copy,
                mutated_solution,
                rejecting_grid,
                rejecting_word,
                environment,
                "mutant existing-test input",
                report["processes"],
            )
            mutant_test_process, mutant_jest = run_jest(
                root,
                mutated_copy,
                [relative for relative, _ in files["test"]],
                environment,
                report["processes"],
                "mutant rejecting test",
                title=HORIZONTAL_TEST,
            )
            if mutant_test_process.returncode == 0:
                raise CheckError("Mutant unexpectedly passed the existing rejecting test")
            if mutant_jest["numFailedTests"] != 1:
                raise CheckError("Mutant failed for a non-assertion or multiple-test reason")
            if mutant_jest["numTotalTests"] == 0:
                raise CheckError("Mutant Jest run executed zero tests")
            failing_assertion = test_result_for(mutant_jest, HORIZONTAL_TEST)
            failure_message = failing_assertion.get("failureMessages", [""])[0]
            if failing_assertion.get("status") != "failed" or "toEqual" not in failure_message:
                raise CheckError("Mutant failure was not the expected Jest equality assertion")
            if not (mutant_test_process.stderr.find("expect(received).toEqual(expected)") >= 0):
                raise CheckError("Mutant failure output did not identify an equality assertion")

            one_cell_mutant = direct_result(
                root,
                mutated_copy,
                mutated_solution,
                ["a"],
                "a",
                environment,
                "mutant one-cell minimality control",
                report["processes"],
            )
            one_cell_expected = {"a": {"start": [1, 1], "end": [1, 1]}}
            if one_cell_mutant != one_cell_expected:
                raise CheckError("Unexpected one-cell fallback result; re-evaluate minimal input")

            report["inputs"] = {
                "configuration": str((ASSIGNMENT / ".meta" / "config.json").as_posix()),
                "resolved_paths": {
                    kind: [relative.as_posix() for relative, _ in values]
                    for kind, values in files.items()
                },
                "initial_grid_and_target_case": {
                    "test_id": INITIAL_CASE_ID,
                    "test_names": INITIAL_TESTS,
                    "grid": ["jefblpepre"],
                    "target": "glasnost",
                    "assertions": [
                        "wordSearch instanceof WordSearch equals true",
                        "wordSearch.find(['glasnost']) equals { glasnost: undefined }",
                    ],
                },
                "existing_rejecting_case": {
                    "test_id": HORIZONTAL_CASE_ID,
                    "test_name": HORIZONTAL_TEST,
                    "grid": rejecting_grid,
                    "target": rejecting_word,
                    "expected": existing_expected,
                    "assertion": "expect(wordSearch.find(['clojure'])).toEqual(expectedResults)",
                },
                "minimal_diagnostic": {
                    "grid": DIAGNOSTIC_GRID,
                    "target": DIAGNOSTIC_WORD,
                    "expected": {DIAGNOSTIC_WORD: DIAGNOSTIC_EXPECTED[DIAGNOSTIC_WORD]},
                    "one_cell_control": {
                        "grid": ["a"],
                        "target": "a",
                        "mutant_result": one_cell_mutant,
                        "reason_not_sufficient": "diagonal fallback still locates a one-letter word",
                    },
                },
                "enabled_test_names": all_names,
            }
            report["original_reference"] = {
                "full_suite": {
                    "tests_executed": total,
                    "tests_passed": passed,
                    "tests_failed": failed,
                    "return_code": original_test_process.returncode,
                },
                "existing_test_input_actual": original_test_input,
                "minimal_input_actual": original_diagnostic,
                "named_test_statuses": {
                    title: test_result_for(original_jest, title).get("status")
                    for title in INITIAL_TESTS + [HORIZONTAL_TEST]
                },
            }
            report["mutated_reference"] = {
                "existing_test_input_actual": mutated_rejecting_input,
                "minimal_input_actual": mutated_diagnostic,
                "rejecting_test": {
                    "test_id": HORIZONTAL_CASE_ID,
                    "test_name": HORIZONTAL_TEST,
                    "status": failing_assertion.get("status"),
                    "assertion_failure": failure_message,
                    "return_code": mutant_test_process.returncode,
                },
                "jest_counts": {
                    "tests_reported": mutant_jest["numTotalTests"],
                    "passed": mutant_jest["numPassedTests"],
                    "failed": mutant_jest["numFailedTests"],
                    "skipped": mutant_jest.get("numPendingTests", 0),
                },
            }
            report["checks"] = {
                "config_paths_resolved": True,
                "full_hidden_exercise_copied": True,
                "all_enabled_cases_ran_against_original": total == len(all_names),
                "original_all_assertions_pass": passed == total and failed == 0,
                "targeted_existing_test_passes_original": True,
                "same_diagnostic_input_used_for_both": True,
                "mutation_applied_only_to_temporary_reference": True,
                "mutation_is_valid_javascript": True,
                "mutant_changes_diagnostic_output": mutated_diagnostic != original_diagnostic,
                "mutant_fails_named_assertion": failing_assertion.get("status") == "failed",
                "mutant_failure_is_behavioral_equality_assertion": "toEqual" in failure_message,
                "minimal_square_input_reproduces_failure": mutated_diagnostic
                == {DIAGNOSTIC_WORD: "__undefined__"},
            }

        learner_hash_after = sha256(learner_solution)
        example_hash_after = {relative.as_posix(): sha256(path) for relative, path in files["example"]}
        test_hash_after = {relative.as_posix(): sha256(path) for relative, path in files["test"]}
        if learner_hash_after != learner_hash_before:
            raise CheckError("Learner solution changed during the checker")
        if example_hash_after != example_hash_before:
            raise CheckError("Maintained reference implementation changed during the checker")
        if test_hash_after != test_hash_before:
            raise CheckError("Maintained generated/test file changed during the checker")
        report["checks"].update(
            {
                "learner_solution_unchanged": True,
                "working_tree_reference_unchanged": True,
                "working_tree_tests_unchanged": True,
            }
        )
        report["working_tree_hashes"] = {
            "learner_solution_before": learner_hash_before,
            "learner_solution_after": learner_hash_after,
            "reference_before": example_hash_before,
            "reference_after": example_hash_after,
            "test_before": test_hash_before,
            "test_after": test_hash_after,
        }
        report["tool_versions"] = versions
        if not all(report["checks"].values()):
            raise CheckError("One or more required checker assertions failed")
        report["success"] = True
    except Exception as exception:
        error = "%s: %s" % (type(exception).__name__, exception)
        report["error"] = error
    finally:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            evidence_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as write_error:
            report["success"] = False
            error = "Could not save evidence: %s" % write_error
        print("Word Search mutation verification")
        original = report.get("original_reference", {}).get("full_suite", {})
        print(
            "Original tests: %s executed, %s passed, %s failed"
            % (
                original.get("tests_executed", 0),
                original.get("tests_passed", 0),
                original.get("tests_failed", 0),
            )
        )
        for item in report.get("original_reference", {}).get("named_test_statuses", {}).items():
            print("%s: %s against original" % item)
        mutant = report.get("mutated_reference", {}).get("rejecting_test", {})
        if mutant:
            print(
                "Mutant assertion status: %s for %s (ID %s; process exit %s)"
                % (
                    mutant.get("status"),
                    mutant.get("test_name"),
                    mutant.get("test_id"),
                    mutant.get("return_code"),
                )
            )
        print("Evidence: %s" % evidence_path.relative_to(root) if root else evidence_path)
        if report["success"]:
            print("Result: PASS")
        else:
            print("Result: FAIL" + (" (%s)" % error if error else ""), file=sys.stderr)
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())