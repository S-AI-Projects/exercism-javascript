#!/usr/bin/env python3
"""Compare the maintained and on-demand Kindergarten Garden references."""

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


EXERCISE = Path("exercises/practice/kindergarten-garden")
ANCHORS = {
    "garden with single student": "RC\\nGG",
    "different garden with single student": "VC\\nRC",
    "garden with two students": "VVCG\\nVVRC",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared(exercise: Path, key: str) -> Path:
    config = json.loads((exercise / ".meta/config.json").read_text())
    values = config.get("files", {}).get(key)
    if not isinstance(values, list) or len(values) != 1:
        fail(f"config.json must map files.{key} to exactly one path")
    rel = Path(values[0])
    path = (exercise / rel).resolve()
    if rel.is_absolute() or not path.is_relative_to(exercise.resolve()) or not path.is_file():
        fail(f"files.{key} is missing or escapes the exercise: {rel}")
    return path


def inspect(exercise: Path) -> dict[str, object]:
    canonical = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    solution, spec, example = (declared(exercise, key) for key in ("solution", "test", "example"))
    content = spec.read_text()
    cases = [title for _quote, title in re.findall(r"\b(?:x?test)\(([\"'])(.*?)\1", content)]
    if len(canonical) != 17 or not cases:
        fail(f"unexpected metadata/spec counts: {len(canonical)} canonical, {len(cases)} spec cases")
    missing = [title for title in ANCHORS if title not in cases]
    if missing:
        fail(f"missing named cases: {missing}")
    # Confirm each anchor's actual garden input appears in the associated case.
    for title, garden_literal in ANCHORS.items():
        match = re.search(rf"(?:x?test)\([\"']{re.escape(title)}[\"'],[\s\S]*?new Garden\('([^']*)'", content)
        if not match or match.group(1) != garden_literal:
            fail(f"unexpected input for named case: {title}")
    return {
        "config_file_map": {
            key: str(path.relative_to(exercise.resolve()))
            for key, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_case_count": len(canonical),
        "spec_case_count": len(cases),
        "named_inputs": ANCHORS,
        "case_names": cases,
    }


def run(root: Path, source: Path, target: Path, implementation: Path) -> dict[str, object]:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("node_modules"))
    solution, spec, _example = (declared(target, key) for key in ("solution", "test", "example"))
    spec.write_text(spec.read_text().replace("xtest(", "test("))
    shutil.copyfile(implementation, solution)
    dependency_link = target / "node_modules"
    if (root / "node_modules").is_dir():
        dependency_link.symlink_to(root / "node_modules", target_is_directory=True)
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--watchAll=false", "--runInBand"]
    result = subprocess.run(command, cwd=target, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    match = re.search(r"Tests:\s+(?:(\d+) passed,\s*)?(?:(\d+) failed,\s*)?(\d+) total", result.stdout)
    if not match:
        fail("Jest did not report test counts\n" + result.stdout[-2500:])
    passed, failed, total = match.groups()
    counts = {"passed": int(passed or 0), "failed": int(failed or 0), "total": int(total)}
    return {"command": command, "returncode": result.returncode, "counts": counts, "output": result.stdout}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    root = parser.parse_args().root.resolve()
    exercise = root / EXERCISE
    details = inspect(exercise)
    learner = declared(exercise, "solution")
    before = sha(learner)
    maintained = declared(exercise, "example")
    alternative = root / "work/R53-T036/alternative.ci.js"
    with tempfile.TemporaryDirectory(prefix="R53-T036-") as temp:
        original_run = run(root, exercise, Path(temp) / "maintained", maintained)
        alternative_run = run(root, exercise, Path(temp) / "alternative", alternative)
    after = sha(learner)
    if before != after:
        fail("learner stub changed during the reference comparisons")
    case_count = details["spec_case_count"]
    expected = {"passed": case_count, "failed": 0, "total": case_count}
    if original_run["returncode"] or original_run["counts"] != expected:
        fail("maintained reference failed the enabled cases\n" + str(original_run["output"])[-2500:])
    if alternative_run["returncode"] or alternative_run["counts"] != expected:
        fail("scratch alternative disagrees with the tests\n" + str(alternative_run["output"])[-2500:])
    evidence = {
        "exercise": str(EXERCISE), "python_version": sys.version,
        "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
        "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
        "metadata": details, "learner_sha256_before": before, "learner_sha256_after": after,
        "maintained_run": original_run, "alternative_run": alternative_run, "outputs_agree_on_asserted_cases": True,
    }
    output = root / "work/R53-T036/evidence.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: both implementations pass {case_count} cases; learner SHA-256 unchanged")
    print(f"Evidence: {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
