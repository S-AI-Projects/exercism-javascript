#!/usr/bin/env python3
"""Run leap-year reference cases and show a contract-breaking mutant fails."""

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


EXERCISE = Path("exercises/practice/leap")
BASE_CASES = 9
DIAGNOSTIC = "proposed minimum non-leap century year"
EXPECTED_BASELINES = {
    "year not divisible by 4 in common year": (2015, "false"),
    "year divisible by 2, not divisible by 4 in common year": (1970, "false"),
    "year divisible by 4, not divisible by 100 in leap year": (1996, "true"),
}
SMALLEST_CENTURY = (100, "false")


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared(exercise: Path, key: str) -> Path:
    config = json.loads((exercise / ".meta/config.json").read_text())
    files = config.get("files", {})
    values = files.get(key)
    if not isinstance(values, list) or len(values) != 1:
        fail(f"config.json must map files.{key} to one path")
    rel = Path(values[0])
    resolved = (exercise / rel).resolve()
    if rel.is_absolute() or not resolved.is_relative_to(exercise.resolve()) or not resolved.is_file():
        fail(f"files.{key} is missing or outside the exercise: {rel}")
    return resolved


def validate(exercise: Path) -> dict[str, object]:
    canonical = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    spec = declared(exercise, "test")
    solution = declared(exercise, "solution")
    example = declared(exercise, "example")
    content = spec.read_text()
    titles = re.findall(r"\b(?:x?test)\('([^']+)'", content)
    if len(canonical) != BASE_CASES or len(titles) != BASE_CASES:
        fail(f"expected {BASE_CASES} canonical and spec cases, found {len(canonical)} and {len(titles)}")
    values = {}
    for title, (year, expected) in EXPECTED_BASELINES.items():
        pattern = rf"(?:x?test)\('{re.escape(title)}',[\s\S]*?isLeap\(({year})\)\)\.toBe\(({expected})\)"
        if not re.search(pattern, content):
            fail(f"the baseline assertion does not match {year} -> {expected} ({title})")
        values[title] = {"input": year, "expected": expected}
    for title in titles:
        if not any(title.endswith(description["description"]) for description in canonical.values()):
            fail(f"spec case has no canonical description: {title}")
    return {
        "config_file_map": {
            key: str(path.relative_to(exercise.resolve()))
            for key, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_case_count": len(canonical),
        "spec_case_count": len(titles),
        "baseline_cases": values,
        "smallest_positive_century_diagnostic": {"input": SMALLEST_CENTURY[0], "expected": SMALLEST_CENTURY[1]},
    }


def prepare(source: Path, dest: Path, add_diagnostic: bool = True) -> tuple[Path, Path, Path]:
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("node_modules"))
    solution, spec, example = (declared(dest, key) for key in ("solution", "test", "example"))
    spec_text = spec.read_text().replace("xtest(", "test(")
    if add_diagnostic:
        marker = "\n});\n"
        before, found, after = spec_text.rpartition(marker)
        if not found:
            fail("could not locate the closing describe block for the diagnostic test")
        diagnostic = "\n  test('" + DIAGNOSTIC + "', () => {\n    expect(isLeap(100)).toBe(false);\n  });"
        spec_text = before + diagnostic + found + after
    spec.write_text(spec_text)
    shutil.copyfile(example, solution)
    return solution, spec, example


def run(root: Path, cwd: Path) -> dict[str, object]:
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--", "--watchAll=false", "--runInBand"]
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    match = re.search(r"Tests:\s+(?:(\d+) passed,\s*)?(?:(\d+) failed,\s*)?(\d+) total", result.stdout)
    if not match:
        fail("Jest did not report test counts\n" + result.stdout[-3000:])
    passed, failed, total = match.groups()
    counts = {"passed": int(passed or 0), "failed": int(failed or 0), "total": int(total)}
    return {"command": command, "returncode": result.returncode, "counts": counts, "output": result.stdout}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    root = parser.parse_args().root.resolve()
    exercise = root / EXERCISE
    metadata = validate(exercise)
    source_solution = declared(exercise, "solution")
    original_hash = digest(source_solution)
    with tempfile.TemporaryDirectory(prefix="R53-T033-") as temp:
        copied = Path(temp) / "run"
        solution, spec, example = prepare(exercise, copied)
        baseline = run(root, copied)
        if baseline["returncode"] != 0 or baseline["counts"] != {"passed": BASE_CASES + 1, "failed": 0, "total": BASE_CASES + 1}:
            fail("reference cases did not all pass, including the 100 diagnostic\n" + str(baseline["output"])[-3000:])

        reference = example.read_text()
        target = "year % 400 === 0 || (year % 4 === 0 && year % 100 !== 0)"
        if target not in reference:
            fail("could not locate the maintained leap-year rule to mutate")
        example.write_text(reference.replace(target, "year % 4 === 0", 1))
        shutil.copyfile(example, solution)
        mutant = run(root, copied)
        rejected = mutant["returncode"] != 0 and DIAGNOSTIC in str(mutant["output"])
        if not rejected:
            fail("the divisibility-by-four mutant was not rejected by the 100 diagnostic")

        evidence = {
            "exercise": str(EXERCISE),
            "python_version": sys.version,
            "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
            "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
            "metadata": metadata,
            "learner_sha256_before": original_hash,
            "learner_sha256_after": digest(source_solution),
            "baseline": baseline,
            "mutant": {"description": "every year divisible by four is accepted", "diagnostic_input": 100, "expected": False, "rejected": rejected, "run": mutant},
        }
    if evidence["learner_sha256_before"] != evidence["learner_sha256_after"]:
        fail("learner stub changed during the check")
    out = root / "work/R53-T033/evidence.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {BASE_CASES} canonical cases plus diagnostic; mutant rejected at year 100")
    print(f"Evidence: {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
