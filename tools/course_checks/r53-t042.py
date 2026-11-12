#!/usr/bin/env python3
"""Compare two fresh outputs from the JavaScript track's Meetup CI generator."""

import difflib
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
            "Python < 3.11 requires tomli; install work/R53-T042/requirements.txt"
        ) from error


ASSIGNMENT = "practice/meetup"
TESTS_RELATIVE = Path("meetup.spec.js")
TEST_DECLARATION = re.compile(r"\b(x?test|test|xit|it)\s*\(\s*(['\"])(.*?)\2", re.S)
ENABLE_OPTIONAL = (
    "import { prepare } from './scripts/helpers.mjs'; "
    "prepare('practice/meetup');"
)
REQUIRED_CASES = {
    "d7f8eadd-d4fc-46ee-8a20-e97bd3fd01c8": "monteenth of May 2013",
    "f78373d1-cd53-4a7f-9d37-e15bf8a456b4": "monteenth of August 2013",
    "8c78bea7-a116-425b-9c6b-c9898266d92a": "monteenth of September 2013",
}


class VerificationError(Exception):
    pass


def find_root():
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "scripts" / "helpers.mjs").is_file()
            and (candidate / "scripts" / "ci.mjs").is_file()
            and (candidate / "exercises" / ASSIGNMENT / ".meta" / "config.json").is_file()
        ):
            return candidate
    raise VerificationError("Could not locate repository root")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def declared_tests(source):
    return [
        {"name": match.group(3), "enabled": not match.group(1).startswith("x")}
        for match in TEST_DECLARATION.finditer(source)
    ]


def promote_optional_tests(source):
    source = re.sub(r"\bxtest(?=\s*\()", "test", source)
    source = re.sub(r"\bxit(?=\s*\()", "it", source)
    return re.sub(r"\bxdescribe(?=\s*\()", "describe", source)


def run(command, cwd, env, label, process_log):
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    process_log.append(
        {
            "label": label,
            "command": [str(item) for item in command],
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    if result.returncode != 0:
        raise VerificationError(
            "%s returned %d\n%s\n%s"
            % (label, result.returncode, result.stdout, result.stderr)
        )
    return result


def copy_generator_environment(root, target):
    for relative in (
        "package.json",
        "pnpm-lock.yaml",
        "config.json",
        ".npmrc",
        "babel.config.js",
        "jest.config.js",
        "scripts/helpers.mjs",
        "scripts/ci.mjs",
    ):
        source = root / relative
        destination = target / relative
        if not source.is_file():
            raise VerificationError("Generator dependency is missing: %s" % source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    exercise_destination = target / "exercises" / ASSIGNMENT
    exercise_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "exercises" / ASSIGNMENT, exercise_destination)
    (target / "node_modules").symlink_to(root / "node_modules", target_is_directory=True)


def compare_outputs(first, second, expected):
    differences = []
    if first != second:
        differences.append(
            "Generation 1 vs generation 2:\n"
            + "".join(
                difflib.unified_diff(
                    first.splitlines(keepends=True),
                    second.splitlines(keepends=True),
                    fromfile="generation-1/meetup.spec.js",
                    tofile="generation-2/meetup.spec.js",
                )
            )
        )
    if first != expected:
        differences.append(
            "Generation 1 vs expected prepared source:\n"
            + "".join(
                difflib.unified_diff(
                    expected.splitlines(keepends=True),
                    first.splitlines(keepends=True),
                    fromfile="expected/meetup.spec.js",
                    tofile="generation-1/meetup.spec.js",
                )
            )
        )
    if second != expected:
        differences.append(
            "Generation 2 vs expected prepared source:\n"
            + "".join(
                difflib.unified_diff(
                    expected.splitlines(keepends=True),
                    second.splitlines(keepends=True),
                    fromfile="expected/meetup.spec.js",
                    tofile="generation-2/meetup.spec.js",
                )
            )
        )
    return differences


def test_count_from_ci_output(output):
    match = re.search(r"Tests:\s+(\d+) passed,\s+\1 total", output)
    if not match:
        raise VerificationError("Could not extract a complete Jest test count from CI output")
    return int(match.group(1))


def main():
    root = None
    report = {
        "task": "R53-T042",
        "success": False,
        "inputs": {},
        "generations": [],
        "comparison": {},
        "ci_runs": [],
        "tool_versions": {},
        "timestamp_normalization": {
            "applied": False,
            "reason": "Neither generated spec contains a timestamp; outputs are compared byte-for-byte.",
            "rule": None,
        },
    }
    error = None
    evidence_directory = None
    try:
        root = find_root()
        exercise = root / "exercises" / ASSIGNMENT
        config_path = exercise / ".meta" / "config.json"
        metadata_path = exercise / ".meta" / "tests.toml"
        spec_path = exercise / TESTS_RELATIVE
        proof_path = exercise / ".meta" / "proof.ci.js"
        for path in (config_path, metadata_path, spec_path, proof_path):
            if not path.is_file():
                raise VerificationError("Required Meetup source is missing: %s" % path)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
        configured_tests = config.get("files", {}).get("test", [])
        if len(configured_tests) != 1 or configured_tests[0] != TESTS_RELATIVE.as_posix():
            raise VerificationError("Unexpected test path in Meetup config: %r" % configured_tests)

        source = spec_path.read_text(encoding="utf-8")
        canonical_tests = declared_tests(source)
        canonical_names = [test["name"] for test in canonical_tests]
        metadata_names = [entry.get("description") for entry in metadata.values()]
        if set(canonical_names) != set(metadata_names) or len(canonical_names) != len(metadata_names):
            missing = sorted(set(metadata_names) - set(canonical_names))
            extra = sorted(set(canonical_names) - set(metadata_names))
            raise VerificationError("TOML/spec case mapping mismatch; missing=%r extra=%r" % (missing, extra))
        for case_uuid, name in REQUIRED_CASES.items():
            if metadata.get(case_uuid, {}).get("description") != name:
                raise VerificationError("Unexpected canonical entry for UUID %s" % case_uuid)
            if name not in canonical_names:
                raise VerificationError("Required generated case is absent: %s" % name)

        root_package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        package_manager = root_package.get("packageManager", "")
        if not package_manager.startswith("pnpm@") or not (root / "pnpm-lock.yaml").is_file():
            raise VerificationError("Root pnpm lockfile/packageManager is required")
        env = os.environ.copy()
        env["PATH"] = str(root / "node_modules" / ".bin") + os.pathsep + env.get("PATH", "")
        env["NODE_PATH"] = str(root / "node_modules")
        env["CI"] = "1"
        process_log = []
        node_version = run(["node", "--version"], root, env, "Node version", process_log).stdout.strip()
        pnpm_version = run(["corepack", "pnpm", "--version"], root, env, "pnpm version", process_log).stdout.strip()
        if pnpm_version != package_manager.split("@", 1)[1]:
            raise VerificationError("pnpm %s does not match %s" % (pnpm_version, package_manager))

        work_directory = root / "work" / "R53-T042"
        work_directory.mkdir(parents=True, exist_ok=True)
        evidence_directory = work_directory
        source_hashes_before = {
            "meetup.spec.js": sha256_text(source),
            "proof.ci.js": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
            "meetup.js": hashlib.sha256((exercise / "meetup.js").read_bytes()).hexdigest(),
            "tests.toml": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        }
        generated = []
        ci_runs = []
        generator_command = [
            "corepack",
            "pnpm",
            "node",
            "--input-type=module",
            "-e",
            ENABLE_OPTIONAL,
        ]
        ci_command = ["corepack", "pnpm", "node", "scripts/ci.mjs"]
        expected = promote_optional_tests(source)

        with tempfile.TemporaryDirectory(prefix="meetup-r53-t042-roundtrip-") as temporary:
            temporary_parent = Path(temporary)
            for index in (1, 2):
                copy_root = temporary_parent / ("fresh-copy-%d" % index)
                copy_root.mkdir()
                copy_generator_environment(root, copy_root)
                copy_env = env.copy()
                copy_env["ASSIGNMENT"] = ASSIGNMENT
                run(
                    generator_command,
                    copy_root,
                    copy_env,
                    "generation %d: track prepare helper" % index,
                    process_log,
                )
                generated_path = copy_root / "tmp_exercises" / ASSIGNMENT / TESTS_RELATIVE
                if not generated_path.is_file():
                    raise VerificationError("Generation %d did not create meetup.spec.js" % index)
                generated_text = generated_path.read_text(encoding="utf-8")
                generated_tests = declared_tests(generated_text)
                generated_names = [test["name"] for test in generated_tests]
                if len(generated_tests) != len(canonical_tests):
                    raise VerificationError("Generation %d changed the test count" % index)
                if generated_names != canonical_names:
                    raise VerificationError("Generation %d dropped, reordered, or added test cases" % index)
                if any(not test["enabled"] for test in generated_tests):
                    raise VerificationError("Generation %d left skipped tests disabled" % index)
                generated.append(generated_text)
                output_path = work_directory / ("generation-%d.meetup.spec.js" % index)
                output_path.write_text(generated_text, encoding="utf-8")

                ci_env = copy_env.copy()
                ci_process = run(
                    ci_command,
                    copy_root,
                    ci_env,
                    "generation %d: actual track CI entry point" % index,
                    process_log,
                )
                combined = ci_process.stdout + "\n" + ci_process.stderr
                executed = test_count_from_ci_output(combined)
                if executed != len(canonical_tests):
                    raise VerificationError(
                        "CI generation %d executed %d tests; expected %d"
                        % (index, executed, len(canonical_tests))
                    )
                for case_name in REQUIRED_CASES.values():
                    if not re.search(r"✓\s+" + re.escape(case_name) + r"(?:\s|\()", combined):
                        raise VerificationError("CI generation %d did not pass %s" % (index, case_name))
                ci_runs.append(
                    {
                        "copy": index,
                        "command": ci_command,
                        "return_code": ci_process.returncode,
                        "tests_executed": executed,
                        "tests_passed": executed,
                        "tests_failed": 0,
                        "named_cases_passed": list(REQUIRED_CASES.values()),
                        "stdout": ci_process.stdout,
                        "stderr": ci_process.stderr,
                    }
                )

        differences = compare_outputs(generated[0], generated[1], expected)
        if differences:
            raise VerificationError("Unexpected generated-file differences:\n" + "\n".join(differences))
        source_hashes_after = {
            "meetup.spec.js": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            "proof.ci.js": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
            "meetup.js": hashlib.sha256((exercise / "meetup.js").read_bytes()).hexdigest(),
            "tests.toml": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        }
        if source_hashes_after != source_hashes_before:
            raise VerificationError("A maintained Meetup file changed during round-trip verification")

        inputs = {
            "canonical_metadata": str(metadata_path.relative_to(root)),
            "maintained_test_spec": str(spec_path.relative_to(root)),
            "reference_implementation": str(proof_path.relative_to(root)),
            "exercise_configuration": str(config_path.relative_to(root)),
            "configured_test_path": configured_tests[0],
            "test_case_count": len(canonical_tests),
            "test_names": canonical_names,
            "named_cases": [
                {
                    "uuid": case_uuid,
                    "canonical_name": name,
                    "spec_assertion": "meetup(2013, month, 'teenth', 'Monday') equals the Date in the test",
                }
                for case_uuid, name in REQUIRED_CASES.items()
            ],
        }
        report["inputs"] = inputs
        report["tool_versions"] = {
            "node": node_version,
            "pnpm": pnpm_version,
            "python": sys.version.split()[0],
            "tomli": getattr(tomllib, "__version__", "stdlib"),
        }
        report["generations"] = [
            {
                "copy": index,
                "generated_path": "tmp_exercises/practice/meetup/meetup.spec.js",
                "saved_output": "work/R53-T042/generation-%d.meetup.spec.js" % index,
                "sha256": sha256_text(text),
                "test_count": len(declared_tests(text)),
                "enabled_test_count": sum(test["enabled"] for test in declared_tests(text)),
                "disabled_test_count": sum(not test["enabled"] for test in declared_tests(text)),
            }
            for index, text in enumerate(generated, start=1)
        ]
        report["comparison"] = {
            "generation_1_equals_generation_2": generated[0] == generated[1],
            "generation_equals_expected_helper_output": generated[0] == expected,
            "normalization": "none; no generated timestamp is present",
            "unexpected_differences": [],
            "cases_preserved": generated_names == canonical_names,
        }
        report["ci_runs"] = ci_runs
        report["maintained_source_hashes_before"] = source_hashes_before
        report["maintained_source_hashes_after"] = source_hashes_after
        report["processes"] = process_log
        report["success"] = True

        (work_directory / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
        (work_directory / "generation-comparison.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    except Exception as exception:
        error = "%s: %s" % (type(exception).__name__, exception)
        report["error"] = error
        if root is not None:
            evidence_directory = root / "work" / "R53-T042"
            evidence_directory.mkdir(parents=True, exist_ok=True)
            report["processes"] = report.get("processes", [])
            (evidence_directory / "generation-comparison.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )

    print("Meetup test-generation round trip")
    for item in report.get("generations", []):
        print(
            "Generation %d: %d cases (%d enabled, %d excluded)"
            % (item["copy"], item["test_count"], item["enabled_test_count"], item["disabled_test_count"])
        )
    for item in report.get("ci_runs", []):
        print("CI copy %d: %d tests passed" % (item["copy"], item["tests_passed"]))
    if report.get("comparison"):
        print("Two generated specs match: %s" % report["comparison"].get("generation_1_equals_generation_2"))
        print("Timestamp normalization: %s" % report["comparison"].get("normalization"))
    print("Evidence: work/R53-T042/generation-comparison.json")
    if report["success"]:
        print("Result: PASS")
    else:
        print("Result: FAIL" + (" (%s)" % error if error else ""), file=sys.stderr)
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())