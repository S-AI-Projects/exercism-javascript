#!/usr/bin/env python3
"""Validate and run the Series reference without touching the learner stub."""

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


EXERCISE = Path("exercises/practice/series")
CASE_COUNT = 11
ANCHOR_OUTPUTS = {
    "slices of one from one": "[[1]]",
    "slices of one from two": "[[1], [2]]",
    "slices of two": "[[3, 5]]",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared(exercise: Path, key: str) -> Path:
    config = json.loads((exercise / ".meta/config.json").read_text())
    files = config.get("files", {})
    items = files.get(key)
    if not isinstance(items, list) or len(items) != 1:
        fail(f"config.json must map files.{key} to exactly one path")
    rel = Path(items[0])
    path = (exercise / rel).resolve()
    if rel.is_absolute() or not path.is_relative_to(exercise.resolve()) or not path.is_file():
        fail(f"files.{key} is missing or escapes the exercise: {rel}")
    return path


def metadata(exercise: Path) -> dict[str, object]:
    canonical = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    solution, spec, example = (declared(exercise, k) for k in ("solution", "test", "example"))
    source = spec.read_text()
    cases = re.findall(r"\b(?:x?test)\('([^']+)'", source)
    if len(canonical) != CASE_COUNT or len(cases) != CASE_COUNT:
        fail(f"expected {CASE_COUNT} canonical and spec cases, found {len(canonical)} and {len(cases)}")
    observed = {}
    for name, expected in ANCHOR_OUTPUTS.items():
        pattern = rf"(?:x?test)\('{re.escape(name)}',[\s\S]*?toEqual\({re.escape(expected)}\)"
        if not re.search(pattern, source):
            fail(f"named case {name!r} does not assert {expected}")
        observed[name] = expected
    return {
        "config_file_map": {
            key: str(path.relative_to(exercise.resolve()))
            for key, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_case_count": len(canonical),
        "spec_case_count": len(cases),
        "named_case_outputs": observed,
        "case_names": cases,
    }


def run(root: Path, source: Path, temp: Path, reference: Path) -> dict[str, object]:
    shutil.copytree(source, temp, ignore=shutil.ignore_patterns("node_modules"))
    solution, spec, _example = (declared(temp, k) for k in ("solution", "test", "example"))
    spec.write_text(spec.read_text().replace("xtest(", "test("))
    shutil.copyfile(reference, solution)
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--", "--watchAll=false", "--runInBand"]
    result = subprocess.run(command, cwd=temp, env=env, text=True, stdout=subprocess.PIPE,
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
    details = metadata(exercise)
    learner = declared(exercise, "solution")
    before = sha(learner)
    reference = declared(exercise, "example")
    with tempfile.TemporaryDirectory(prefix="R53-T034-") as tmp:
        baseline_dir, updated_dir = Path(tmp) / "baseline", Path(tmp) / "updated"
        # The baseline is captured from the task's unchanged main-line reference.
        old = subprocess.run(["git", "show", f"main:{EXERCISE}/.meta/proof.ci.js"], cwd=root,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if old.returncode != 0:
            fail("could not read the original Series reference from main: " + old.stderr.strip())
        old_file = Path(tmp) / "baseline-proof.ci.js"
        old_file.write_text(old.stdout)
        baseline = run(root, exercise, baseline_dir, old_file)
        updated = run(root, exercise, updated_dir, reference)
        expected = {"passed": CASE_COUNT, "failed": 0, "total": CASE_COUNT}
        if baseline["returncode"] or baseline["counts"] != expected:
            fail("the original reference failed the all-case baseline\n" + str(baseline["output"])[-2500:])
        if updated["returncode"] or updated["counts"] != expected:
            fail("the updated reference failed the all-case suite\n" + str(updated["output"])[-2500:])
        evidence = {
            "exercise": str(EXERCISE),
            "python_version": sys.version,
            "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
            "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
            "metadata": details,
            "learner_sha256_before": before,
            "learner_sha256_after": sha(learner),
            "baseline": baseline,
            "updated": updated,
            "outputs_agree": True,
        }
    if evidence["learner_sha256_before"] != evidence["learner_sha256_after"]:
        fail("learner stub changed during the check")
    out = root / "work/R53-T034/evidence.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {CASE_COUNT} cases pass against both references; named windows agree")
    print(f"Evidence: {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
