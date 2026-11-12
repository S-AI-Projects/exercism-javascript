import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORK_DIR = os.path.abspath(os.path.dirname(__file__))
EXERCISE_REL = os.path.join("exercises", "practice", "resistor-color-duo")
EXERCISE_DIR = os.path.join(REPO_ROOT, EXERCISE_REL)

NAMED_CASES = [
    "Brown and black",
    "Blue and grey",
    "Yellow and violet",
]


def run_jest_in_copy(solution_source: str, test_file: str, solution_file: str):
    with tempfile.TemporaryDirectory() as tmp_dir:
        dest_exercise = os.path.join(tmp_dir, "exercise")
        shutil.copytree(EXERCISE_DIR, dest_exercise, symlinks=True)

        temp_spec = os.path.join(dest_exercise, test_file)
        with open(temp_spec, "r", encoding="utf-8") as f:
            spec_text = f.read().replace("xtest(", "test(")
        with open(temp_spec, "w", encoding="utf-8") as f:
            f.write(spec_text)

        with open(os.path.join(dest_exercise, solution_file), "w", encoding="utf-8") as f:
            f.write(solution_source)

        root_nm = os.path.join(REPO_ROOT, "node_modules")
        dest_nm = os.path.join(dest_exercise, "node_modules")
        if os.path.exists(root_nm) and not os.path.exists(dest_nm):
            os.symlink(root_nm, dest_nm)

        env = os.environ.copy()
        env["CI"] = "true"
        local_jest = os.path.join(REPO_ROOT, "node_modules", ".bin", "jest")

        res = subprocess.run(
            [local_jest, "--watchAll=false", "--no-watchman", "--verbose"],
            cwd=dest_exercise,
            env=env,
            capture_output=True,
            text=True,
        )
        combined = res.stdout + "\n" + res.stderr
        passed_match = re.search(r"Tests:\s+(\d+)\s+passed", combined)
        passed_count = int(passed_match.group(1)) if passed_match else 0
        return res.returncode, combined, passed_count


def measure_operations_and_medians(ref_source: str):
    common_js_ref = ref_source.replace("export const decodedValue", "const decodedValue")
    node_script = f"""
{common_js_ref}

const cases = [
  {{ label: "2-bands-low", input: ["brown", "black"], expected: 10 }},
  {{ label: "2-bands-high", input: ["blue", "grey"], expected: 68 }},
  {{ label: "3-bands-ignored-extra", input: ["green", "brown", "orange"], expected: 51 }},
  {{ label: "2-bands-worst-case", input: ["white", "white"], expected: 99 }}
];

const REPS = 7;
const INNER_ITERS = 10000;
const results = [];

for (const c of cases) {{
  const actual = decodedValue(c.input);
  if (actual !== c.expected) {{
    throw new Error(`Correctness assertion failed for ${{c.label}}: expected ${{c.expected}}, got ${{actual}}`);
  }}
  const tensChecks = COLORS.indexOf(c.input[0]) + 1;
  const onesChecks = COLORS.indexOf(c.input[1]) + 1;
  const totalChecks = tensChecks + onesChecks;

  const samplesNsPerCall = [];
  for (let r = 0; r < REPS; r++) {{
    const t0 = performance.now();
    let acc = 0;
    for (let i = 0; i < INNER_ITERS; i++) {{
      acc += decodedValue(c.input);
    }}
    const t1 = performance.now();
    if (acc < 0) console.log(acc);
    samplesNsPerCall.push(((t1 - t0) * 1e6) / INNER_ITERS);
  }}

  results.push({{
    label: c.label,
    input: c.input,
    input_length: c.input.length,
    expected: c.expected,
    actual: actual,
    tens_comparisons: tensChecks,
    ones_comparisons: onesChecks,
    total_indexOf_comparisons: totalChecks,
    ignored_elements: Math.max(0, c.input.length - 2),
    repetitions: REPS,
    samples_ns_per_call: samplesNsPerCall
  }});
}}

console.log(JSON.stringify(results));
"""
    res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"Node operation/timing verification failed:\n{res.stderr}")
    parsed = json.loads(res.stdout.strip())
    for item in parsed:
        item["median_ns_per_call"] = round(statistics.median(item["samples_ns_per_call"]), 2)
        del item["samples_ns_per_call"]
    return parsed


def main():
    config_path = os.path.join(EXERCISE_DIR, ".meta", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    solution_file = config["files"]["solution"][0]
    test_file = config["files"]["test"][0]
    example_file = config["files"]["example"][0]

    with open(os.path.join(EXERCISE_DIR, solution_file), "r", encoding="utf-8") as f:
        stub_content = f.read()
    if "Remove this line and implement the function" not in stub_content:
        raise AssertionError("Learner stub has been modified or solved in the working tree!")

    with open(os.path.join(EXERCISE_DIR, ".meta", "tests.toml"), "r", encoding="utf-8") as f:
        toml_content = f.read()
    canonical_uuids = re.findall(r"^\[([0-9a-f-]+)\]", toml_content, flags=re.MULTILINE)
    if len(canonical_uuids) == 0:
        raise AssertionError("No canonical UUIDs found in .meta/tests.toml")

    with open(os.path.join(EXERCISE_DIR, test_file), "r", encoding="utf-8") as f:
        spec_content = f.read()
    for case_name in NAMED_CASES:
        if case_name not in toml_content or case_name not in spec_content:
            raise AssertionError(f"Missing required named case: {case_name}")

    with open(os.path.join(EXERCISE_DIR, "package.json"), "r", encoding="utf-8") as f:
        ex_pkg = json.load(f)
    pkg_test_script = ex_pkg.get("scripts", {}).get("test", "corepack pnpm jest")

    with open(os.path.join(EXERCISE_DIR, example_file), "r", encoding="utf-8") as f:
        ref_source = f.read()

    if "Complexity & invariant" not in ref_source:
        raise AssertionError("Complexity/invariant comment missing adjacent to colorCode in proof.ci.js")

    jest_code, jest_out, jest_passed = run_jest_in_copy(ref_source, test_file, solution_file)
    if jest_code != 0 or jest_passed == 0:
        raise AssertionError(f"Reference failed or ran zero tests:\n{jest_out}")
    if jest_passed != len(canonical_uuids):
        raise AssertionError(f"Expected {len(canonical_uuids)} passed tests, got {jest_passed}")
    for case_name in NAMED_CASES:
        if case_name not in jest_out:
            raise AssertionError(f"Named case {case_name!r} missing from Jest verbose output")

    measurements = measure_operations_and_medians(ref_source)
    for m in measurements:
        if not (2 <= m["total_indexOf_comparisons"] <= 20):
            raise AssertionError(f"Comparison count {m['total_indexOf_comparisons']} outside fixed bound [2, 20]")

    node_v = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    npm_v = subprocess.run(["npm", "-v"], capture_output=True, text=True).stdout.strip()

    report = {
        "task_id": "R53-T025",
        "exercise": "resistor-color-duo",
        "package_json_test_script": pkg_test_script,
        "named_cases_verified": NAMED_CASES,
        "canonical_case_count": len(canonical_uuids),
        "jest_suite": {
            "exit_code": jest_code,
            "executed_passed_tests": jest_passed,
            "status": "PASSED",
        },
        "complexity_bound": {
            "palette_size": 10,
            "colorCode_comparisons_range": [1, 10],
            "decodedValue_comparisons_range": [2, 20],
            "asymptotic_time": "O(1)",
            "asymptotic_space": "O(1)",
        },
        "domain_measurements": measurements,
        "learner_stub_status": "UNSOLVED",
        "tool_versions": {
            "node": node_v,
            "npm": npm_v,
            "python": sys.version.split()[0],
        },
        "status": "PASSED",
    }

    log_text = (
        "=== JEST SUITE RUN ===\n"
        + jest_out
        + "\n=== OPERATION & MEDIAN TIMING MEASUREMENTS ===\n"
        + json.dumps(measurements, indent=2)
    )

    with open(os.path.join(WORK_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(os.path.join(WORK_DIR, "results.log"), "w", encoding="utf-8") as f:
        f.write(log_text)

    print("=== R53-T025 Reference Complexity Study Check Passed ===")
    print(f"Named cases verified: {NAMED_CASES}")
    print(f"Jest suite: PASSED ({jest_passed}/{len(canonical_uuids)} tests)")
    for m in measurements:
        print(
            f"  - {m['label']} ({m['input']}): output={m['actual']}, "
            f"indexOf_comparisons={m['total_indexOf_comparisons']}, median={m['median_ns_per_call']} ns/call"
        )
    print("Evidence saved in work/R53-T025/results.json and work/R53-T025/results.log")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
