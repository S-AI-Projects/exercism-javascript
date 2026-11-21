#!/usr/bin/env python3
"""Validate Markdown exercise metadata and its maintained reference cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib


EXERCISE = Path("exercises/practice/markdown")
SPEC_CASES = 17
EXCLUDED_UUID = "6dca5d10-5c22-4e2a-ac2b-bd6f21e61939"
REPLACEMENT_UUID = "81c0c4db-435e-4d77-860d-45afacdad810"
BOUNDARY_CASE = "with h7 header level"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_declared(exercise: Path, relative: str, key: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        fail(f"files.{key} must be relative to the exercise")
    resolved = (exercise / path).resolve()
    if not resolved.is_relative_to(exercise.resolve()):
        fail(f"files.{key} escapes the exercise directory: {relative}")
    if not resolved.is_file():
        fail(f"files.{key} does not exist: {relative}")
    return resolved


def validate_metadata(exercise: Path) -> dict[str, object]:
    config_path = exercise / ".meta/config.json"
    config = json.loads(config_path.read_text())
    files = config.get("files")
    if not isinstance(files, dict):
        fail("config.json must contain a files object")
    resolved = {
        key: resolve_declared(exercise, rels[0], key)
        for key, rels in files.items()
        if key in {"solution", "test", "example"}
        and isinstance(rels, list)
        and len(rels) == 1
        and isinstance(rels[0], str)
    }
    if set(resolved) != {"solution", "test", "example"}:
        fail("solution, test, and example must each declare one file")

    raw_tests = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    if len(raw_tests) != 18:
        fail(f"expected 18 canonical entries, found {len(raw_tests)}")
    excluded = [uid for uid, item in raw_tests.items() if item.get("include") is False]
    if excluded != [EXCLUDED_UUID]:
        fail(f"expected only {EXCLUDED_UUID} to be excluded, found {excluded}")
    case = raw_tests[EXCLUDED_UUID]
    if case.get("description") != BOUNDARY_CASE:
        fail("excluded UUID is not the h7 header case")
    if "unsupported" not in case.get("comment", ""):
        fail("excluded case needs a rationale that names the unsupported contract")
    replacement = raw_tests.get(REPLACEMENT_UUID)
    if not replacement or replacement.get("reimplements") != EXCLUDED_UUID:
        fail("the h7 paragraph replacement must reimplement the excluded UUID")
    included_count = len(raw_tests) - len(excluded)
    if (included_count, len(excluded)) != (17, 1):
        fail(f"unexpected canonical counts: included={included_count}, excluded={len(excluded)}")

    spec = resolved["test"].read_text()
    named = re.findall(r"\b(?:x?test)\('([^']+)'", spec)
    if len(named) != SPEC_CASES:
        fail(f"expected {SPEC_CASES} spec cases, found {len(named)}")
    if BOUNDARY_CASE not in named:
        fail("the replacement behavior has no corresponding named spec case")
    for expected in (
        "parses normal text as a paragraph",
        "parsing italics",
        "parsing bold text",
    ):
        if expected not in named:
            fail(f"missing named baseline case: {expected}")

    return {
        "config_file_map": {
            key: str(path.relative_to(exercise.resolve())) for key, path in resolved.items()
        },
        "canonical_entries_before": len(raw_tests),
        "included_before": included_count,
        "excluded_before": len(excluded),
        "canonical_entries_after": len(raw_tests),
        "included_after": included_count,
        "excluded_after": len(excluded),
        "spec_case_count": len(named),
        "named_cases": named,
    }


def run_jest(root: Path, exercise_dir: Path) -> dict[str, object]:
    env = os.environ.copy()
    bins = [str(root / "node_modules/.bin"), str(root / "node_modules/.bin/.bin")]
    env["PATH"] = os.pathsep.join(bins + [env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--", "--watchAll=false", "--runInBand"]
    result = subprocess.run(
        command,
        cwd=exercise_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    match = re.search(r"Tests:\s+(?:(\d+) passed,\s*)?(?:(\d+) failed,\s*)?(\d+) total", result.stdout)
    if not match:
        fail("Jest did not report a parseable test count\n" + result.stdout[-3000:])
    passed, failed, total = match.groups()
    count = {"passed": int(passed or 0), "failed": int(failed or 0), "total": int(total)}
    return {
        "command": command,
        "returncode": result.returncode,
        "test_counts": count,
        "output": result.stdout,
    }


def prepare_copy(source: Path, destination: Path) -> tuple[Path, Path, Path]:
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("node_modules"))
    config = json.loads((destination / ".meta/config.json").read_text())
    files = config["files"]
    solution = destination / files["solution"][0]
    spec = destination / files["test"][0]
    example = destination / files["example"][0]
    spec.write_text(spec.read_text().replace("xtest(", "test("))
    shutil.copyfile(example, solution)
    return solution, spec, example


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    exercise = root / EXERCISE
    metadata = validate_metadata(exercise)

    original_solution = exercise / "markdown.js"
    before_hash = sha256(original_solution)
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running the Jest checks")
    evidence: dict[str, object] = {
        "exercise": str(EXERCISE),
        "python_version": sys.version,
        "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
        "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
        "metadata": metadata,
        "learner_solution_sha256_before": before_hash,
        "runs": {},
    }

    with tempfile.TemporaryDirectory(prefix="R53-T031-") as temp:
        temp_path = Path(temp)
        base_dir = temp_path / "reference"
        solution, spec, example = prepare_copy(exercise, base_dir)
        baseline = run_jest(root, base_dir)
        if baseline["returncode"] != 0:
            fail("maintained reference failed the baseline suite\n" + str(baseline["output"])[-3000:])
        if baseline["test_counts"] != {"passed": SPEC_CASES, "failed": 0, "total": SPEC_CASES}:
            fail(f"expected {SPEC_CASES} passing tests, got {baseline['test_counts']}")

        # Change only the h7 fallback in the temporary reference. The named
        # replacement case must reject this semantic mutant.
        example_text = example.read_text()
        old = "p1.length > 6 ? wrapInTag('p', match) : wrapInTag(`h${p1.length}`, p2)"
        mutant = "p1.length > 6 ? wrapInTag('h7', p2) : wrapInTag(`h${p1.length}`, p2)"
        if old not in example_text:
            fail("could not locate the reference's h7 fallback for mutation")
        example.write_text(example_text.replace(old, mutant, 1))
        shutil.copyfile(example, solution)
        mutated = run_jest(root, base_dir)
        mutation_rejected = (
            mutated["returncode"] != 0
            and mutated["test_counts"]["failed"] >= 1
            and BOUNDARY_CASE in str(mutated["output"])
        )
        if not mutation_rejected:
            fail("the deliberately incorrect h7 reference was not rejected by its named test")
        evidence["runs"] = {"reference": baseline, "mutated_h7_reference": mutated}
        evidence["mutation_rejected"] = mutation_rejected

    after_hash = sha256(original_solution)
    evidence["learner_solution_sha256_after"] = after_hash
    if before_hash != after_hash:
        fail("learner solution changed during the check")

    out = root / "work/R53-T031/evidence.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {SPEC_CASES} reference cases; h7 mutant rejected; learner SHA-256 unchanged")
    print(f"Evidence: {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
