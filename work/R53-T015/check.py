#!/usr/bin/env python3
"""Test and benchmark the Rail Fence Cipher reference implementation."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXERCISE = ROOT / "exercises" / "practice" / "rail-fence-cipher"
OUTPUT = Path(__file__).resolve().parent
TEST_CALL = re.compile(r"\b(?:x?test)\s*\(\s*(['\"])(.*?)\1")
SKIPPED_CALL = re.compile(r"\bxtest(?=\s*\()")
MESSAGE_LENGTHS = [100, 1000, 5000]
RAIL_COUNT = 3
REPETITIONS = 7
CALLS_PER_REPETITION = 100

BENCHMARK_TEST = """\
import { writeFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import { decode, encode } from './rail-fence-cipher';
import { test } from '@jest/globals';

const lengths = [100, 1000, 5000];
const rails = 3;
const repetitions = 7;
const callsPerRepetition = 100;

test('checks and measures encode', () => {
  const messages = lengths.map((length) => {
    let message = '';
    for (let index = 0; index < length; index += 1) {
      message += String.fromCharCode(65 + (index % 26));
    }
    return { length, message };
  });

  const knownMessage = 'WEAREDISCOVEREDFLEEATONCE';
  const knownOutput = 'WECRLTEERDSOEEFEAOCAIVDEN';
  const knownActual = encode(knownMessage, rails);
  if (knownActual !== knownOutput) {
    throw new Error('The known three-rail example did not encode correctly.');
  }

  const correctness = {
    knownExample: {
      expected: knownOutput,
      actual: knownActual,
      passed: knownActual === knownOutput,
    },
    generatedMessages: [],
  };
  for (const { length, message } of messages) {
    const encoded = encode(message, rails);
    const roundTripPassed = decode(encoded, rails) === message;
    if (encoded.length !== length || !roundTripPassed) {
      throw new Error(`Correctness check failed for ${length} characters.`);
    }
    correctness.generatedMessages.push({
      length,
      expectedOutputLength: length,
      actualOutputLength: encoded.length,
      roundTripPassed,
    });
  }

  const measurements = messages.map(({ length, message }) => {
    for (let warmup = 0; warmup < 100; warmup += 1) {
      encode(message, rails);
    }

    const samples = [];
    let result = '';
    for (let repetition = 0; repetition < repetitions; repetition += 1) {
      const start = performance.now();
      for (let call = 0; call < callsPerRepetition; call += 1) {
        result = encode(message, rails);
      }
      samples.push((performance.now() - start) / callsPerRepetition);
    }

    if (result.length !== length) {
      throw new Error(`Unexpected output length for ${length} characters.`);
    }
    return { length, rails, samplesMillisecondsPerEncode: samples };
  });

  writeFileSync(
    process.env.RAIL_BENCHMARK_OUTPUT,
    JSON.stringify({
      correctnessCheckedBeforeTiming: true,
      knownExamplePassed: true,
      correctness,
      messageGeneration: 'repeat A-Z in order and truncate to requested length',
      repetitions,
      callsPerRepetition,
      measurements,
    }),
  );
});
"""


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_version(command):
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not get version for {command[0]}.")
    return result.stdout.strip()


def run_jest(exercise, extra_args, report_path, extra_env=None):
    command = [
        "npm",
        "run",
        "test",
        "--",
        "--watch=false",
        "--runInBand",
        *extra_args,
        "--json",
        f"--outputFile={report_path}",
    ]
    environment = os.environ.copy()
    if extra_env:
        environment.update(extra_env)
    child = subprocess.run(
        command,
        cwd=exercise,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else None
    )
    counts = None
    cases = []
    if report is not None:
        counts = {
            "total": report.get("numTotalTests"),
            "passed": report.get("numPassedTests"),
            "failed": report.get("numFailedTests"),
            "pending": report.get("numPendingTests"),
        }
        for test_file in report.get("testResults", []):
            for assertion in test_file.get("assertionResults", []):
                cases.append(
                    {
                        "name": assertion.get("fullName"),
                        "status": assertion.get("status"),
                    }
                )
    return {
        "command": command,
        "return_code": child.returncode,
        "counts": counts,
        "cases": cases,
        "output_excerpt": (child.stdout + child.stderr)[-1000:],
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(
        (EXERCISE / ".meta" / "config.json").read_text(encoding="utf-8")
    )
    files = config["files"]
    solution_paths = files["solution"]
    test_paths = files["test"]
    example_paths = files["example"]
    if not solution_paths or len(solution_paths) != len(example_paths):
        raise ValueError("The solution and example paths do not match.")
    if not test_paths:
        raise ValueError("The exercise config does not list test files.")

    original_solutions = {
        path: (EXERCISE / path).read_bytes() for path in solution_paths
    }
    original_tests = {
        path: (EXERCISE / path).read_bytes() for path in test_paths
    }
    test_sources = {
        path: contents.decode("utf-8") for path, contents in original_tests.items()
    }
    expected_names = [
        match.group(2)
        for source in test_sources.values()
        for match in TEST_CALL.finditer(source)
    ]
    expected_test_count = len(expected_names)
    expected_skips = sum(
        len(SKIPPED_CALL.findall(source)) for source in test_sources.values()
    )
    versions = {
        "python": sys.version.split()[0],
        "node": run_version(["node", "--version"]),
        "npm": run_version(["npm", "--version"]),
        "pnpm": run_version(["corepack", "pnpm", "--version"]),
        "jest": run_version(["corepack", "pnpm", "exec", "jest", "--version"]),
    }
    save_json(OUTPUT / "tool-versions.json", versions)

    failures = []
    full_run = None
    benchmark_run = None
    benchmark_data = None
    skipped_enabled = 0

    with tempfile.TemporaryDirectory(prefix="rail-fence-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_exercise = temp_root / "rail-fence-cipher"
        shutil.copytree(
            EXERCISE,
            temp_exercise,
            ignore=shutil.ignore_patterns("node_modules"),
        )

        dependencies = ROOT / "node_modules"
        if dependencies.is_dir():
            (temp_exercise / "node_modules").symlink_to(
                dependencies, target_is_directory=True
            )
        else:
            failures.append("Repository node_modules are missing.")

        for solution_path, example_path in zip(solution_paths, example_paths):
            shutil.copyfile(
                temp_exercise / example_path,
                temp_exercise / solution_path,
            )

        for test_path in test_paths:
            copied_test = temp_exercise / test_path
            source = copied_test.read_text(encoding="utf-8")
            enabled, replacements = SKIPPED_CALL.subn("test", source)
            skipped_enabled += replacements
            copied_test.write_text(enabled, encoding="utf-8")
        if skipped_enabled != expected_skips:
            failures.append("Not all skipped tests were enabled in the copy.")

        package = json.loads(
            (temp_exercise / "package.json").read_text(encoding="utf-8")
        )
        if "test" not in package.get("scripts", {}):
            failures.append("The exercise package.json has no test command.")

        full_run = run_jest(
            temp_exercise, [], temp_root / "exercise-results.json"
        )
        (temp_exercise / "benchmark.spec.js").write_text(
            BENCHMARK_TEST, encoding="utf-8"
        )
        benchmark_output = temp_root / "benchmark-inputs-and-results.json"
        benchmark_run = run_jest(
            temp_exercise,
            ["--runTestsByPath", "benchmark.spec.js"],
            temp_root / "benchmark-jest-results.json",
            {"RAIL_BENCHMARK_OUTPUT": str(benchmark_output)},
        )
        if benchmark_output.is_file():
            benchmark_data = json.loads(
                benchmark_output.read_text(encoding="utf-8")
            )

    for name, run, expected_count in (
        ("exercise", full_run, expected_test_count),
        ("benchmark", benchmark_run, 1),
    ):
        if run["return_code"] != 0:
            failures.append(f"The {name} test command exited unsuccessfully.")
        if run["counts"] is None:
            failures.append(f"The {name} run did not produce Jest results.")
        elif run["counts"]["total"] == 0:
            failures.append(f"The {name} run executed zero tests.")
        elif run["counts"]["total"] != expected_count:
            failures.append(
                f"The {name} run executed {run['counts']['total']} tests; "
                f"expected {expected_count}."
            )
        elif (
            run["counts"]["failed"] != 0
            or run["counts"]["passed"] != expected_count
        ):
            failures.append(f"Not all {name} tests passed.")

    if any(case["status"] != "passed" for case in full_run["cases"]):
        failures.append("At least one exercise test did not pass.")
    named_encodings = [
        "encode with two rails",
        "encode with three rails",
        "encode with ending in the middle",
    ]
    for name in named_encodings:
        if not any(
            name in case["name"] and case["status"] == "passed"
            for case in full_run["cases"]
        ):
            failures.append(f"The named encoding test did not pass: {name}.")

    medians = []
    if benchmark_data is None:
        failures.append("The benchmark did not save its measurements.")
    else:
        if not benchmark_data.get("correctnessCheckedBeforeTiming"):
            failures.append("Benchmark correctness was not checked before timing.")
        if not benchmark_data.get("knownExamplePassed"):
            failures.append("The known three-rail example did not pass.")
        correctness = benchmark_data.get("correctness", {})
        known_example = correctness.get("knownExample", {})
        if (
            known_example.get("actual") != known_example.get("expected")
            or not known_example.get("passed")
        ):
            failures.append("The saved known-example output is incorrect.")
        generated_correctness = correctness.get("generatedMessages", [])
        if [item.get("length") for item in generated_correctness] != MESSAGE_LENGTHS:
            failures.append("Correctness results are missing for a benchmark input.")
        for item in generated_correctness:
            if (
                item.get("actualOutputLength") != item.get("expectedOutputLength")
                or not item.get("roundTripPassed")
            ):
                failures.append(
                    f"Correctness check failed for length {item.get('length')}."
                )
        repetitions = benchmark_data.get("repetitions", 0)
        if repetitions != REPETITIONS:
            failures.append("The benchmark repetition count changed.")
        if benchmark_data.get("callsPerRepetition") != CALLS_PER_REPETITION:
            failures.append("The number of calls per timing sample changed.")

        measurements = benchmark_data.get("measurements", [])
        if [item.get("length") for item in measurements] != MESSAGE_LENGTHS:
            failures.append("Benchmark message lengths do not match the requested sizes.")
        for item in measurements:
            samples = item.get("samplesMillisecondsPerEncode", [])
            if item.get("rails") != RAIL_COUNT:
                failures.append("The benchmark rail count changed.")
            if len(samples) != repetitions:
                failures.append(
                    f"Unexpected repetition count for length {item.get('length')}."
                )
            if not samples:
                failures.append(f"No timings were recorded for {item.get('length')}.")
                continue
            ordered = sorted(samples)
            middle = len(ordered) // 2
            if len(ordered) % 2:
                median = ordered[middle]
            else:
                median = (ordered[middle - 1] + ordered[middle]) / 2
            medians.append(
                {
                    "length": item["length"],
                    "rails": item["rails"],
                    "samples_milliseconds_per_encode": samples,
                    "median_milliseconds_per_encode": median,
                }
            )

    learner_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_solutions.items()
    )
    tests_unchanged = all(
        (EXERCISE / path).read_bytes() == contents
        for path, contents in original_tests.items()
    )
    if not learner_unchanged:
        failures.append("The original learner solution changed.")
    if not tests_unchanged:
        failures.append("The original tests changed.")

    inputs = {
        "config": config,
        "test_sources": test_sources,
        "expected_test_names": expected_names,
        "enabled_skipped_test_count": skipped_enabled,
        "benchmark_message_lengths": MESSAGE_LENGTHS,
        "benchmark_rails": RAIL_COUNT,
        "benchmark_repetitions": REPETITIONS,
        "benchmark_calls_per_repetition": CALLS_PER_REPETITION,
        "benchmark_message_generation": (
            "Repeat A-Z in order and truncate to the requested length."
        ),
        "known_correctness_example": {
            "input": "WEAREDISCOVEREDFLEEATONCE",
            "rails": 3,
            "expected": "WECRLTEERDSOEEFEAOCAIVDEN",
        },
    }
    results = {
        "success": not failures,
        "expected_exercise_test_count": expected_test_count,
        "exercise_run": full_run,
        "benchmark_test_run": benchmark_run,
        "benchmark_correctness_checked_before_timing": (
            benchmark_data.get("correctnessCheckedBeforeTiming")
            if benchmark_data
            else False
        ),
        "benchmark_correctness": (
            benchmark_data.get("correctness") if benchmark_data else None
        ),
        "benchmark_measurements": medians,
        "learner_solution_unchanged": learner_unchanged,
        "tests_unchanged": tests_unchanged,
        "failure_reasons": failures,
    }
    save_json(OUTPUT / "inputs.json", inputs)
    save_json(OUTPUT / "results.json", results)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"Details saved in {OUTPUT}", file=sys.stderr)
        return 1

    print(
        f"PASS: all {expected_test_count} exercise tests passed; "
        "benchmark recorded 7 measurements for each message length."
    )
    for item in medians:
        print(
            f"{item['length']} characters, {item['rails']} rails: "
            f"median {item['median_milliseconds_per_encode']:.6f} ms/encode"
        )
    print(f"Results saved in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
