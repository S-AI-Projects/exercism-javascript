#!/usr/bin/env python3
"""Verify the maintained Twelve Days test source and run its reference cases."""

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


EXERCISE = Path("exercises/practice/twelve-days")
CASE_COUNT = 15
ANCHORS = (
    "verse first day a partridge in a pear tree",
    "verse second day two turtle doves",
    "verse third day three french hens",
)


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_from_config(exercise: Path, key: str) -> Path:
    config = json.loads((exercise / ".meta/config.json").read_text())
    files = config.get("files")
    if not isinstance(files, dict) or not isinstance(files.get(key), list) or len(files[key]) != 1:
        fail(f"config.json must map files.{key} to one path")
    rel = Path(files[key][0])
    resolved = (exercise / rel).resolve()
    if rel.is_absolute() or not resolved.is_relative_to(exercise.resolve()) or not resolved.is_file():
        fail(f"files.{key} is missing or outside the exercise: {rel}")
    return resolved


def read_cases(exercise: Path) -> dict[str, object]:
    canonical = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    spec = file_from_config(exercise, "test")
    solution = file_from_config(exercise, "solution")
    example = file_from_config(exercise, "example")
    content = spec.read_text()
    titles = re.findall(r"\b(?:x?test)\('([^']+)'", content)
    descriptions = [entry["description"] for entry in canonical.values()]
    if len(canonical) != CASE_COUNT or len(titles) != CASE_COUNT:
        fail(f"expected {CASE_COUNT} canonical cases and spec cases; found {len(canonical)} and {len(titles)}")
    mappings = {}
    for description in descriptions:
        matches = [title for title in titles if title.endswith(description)]
        if len(matches) != 1:
            fail(f"canonical case {description!r} maps to {len(matches)} test names")
        mappings[description] = matches[0]
    for anchor in ANCHORS:
        if anchor not in titles:
            fail(f"missing required case: {anchor}")
    return {
        "config_file_map": {
            key: str(path.relative_to(exercise.resolve()))
            for key, path in {"solution": solution, "test": spec, "example": example}.items()
        },
        "canonical_count": len(canonical),
        "test_count": len(titles),
        "case_mappings": mappings,
        "test_titles": titles,
        "spec_path": spec,
    }


def copy_exercise(source: Path, dest: Path) -> tuple[Path, Path, Path]:
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("node_modules"))
    sol = file_from_config(dest, "solution")
    spec = file_from_config(dest, "test")
    example = file_from_config(dest, "example")
    spec.write_text(spec.read_text().replace("xtest(", "test("))
    shutil.copyfile(example, sol)
    return sol, spec, example


def run_cases(root: Path, exercise_dir: Path) -> dict[str, object]:
    dependency_link = exercise_dir / "node_modules"
    if (root / "node_modules").is_dir() and not dependency_link.exists() and not dependency_link.is_symlink():
        dependency_link.symlink_to(root / "node_modules", target_is_directory=True)
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--watchAll=false", "--runInBand"]
    result = subprocess.run(command, cwd=exercise_dir, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    match = re.search(r"Tests:\s+(?:(\d+) passed,\s*)?(?:(\d+) failed,\s*)?(\d+) total", result.stdout)
    if not match:
        fail("Jest did not report a test count\n" + result.stdout[-3000:])
    passed, failed, total = match.groups()
    counts = {"passed": int(passed or 0), "failed": int(failed or 0), "total": int(total)}
    return {"command": command, "returncode": result.returncode, "counts": counts, "output": result.stdout}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", type=Path)
    root = parser.parse_args().root.resolve()
    exercise = root / EXERCISE
    result = read_cases(exercise)
    spec = result.pop("spec_path")
    with tempfile.TemporaryDirectory(prefix="R53-T032-") as tmp:
        base = Path(tmp)
        first = base / "snapshot-one"
        second = base / "snapshot-two"
        shutil.copytree(exercise, first, ignore=shutil.ignore_patterns("node_modules"))
        shutil.copytree(exercise, second, ignore=shutil.ignore_patterns("node_modules"))
        one = file_from_config(first, "test")
        two = file_from_config(second, "test")
        first_hash, second_hash = digest(one), digest(two)
        if first_hash != second_hash:
            fail("fresh maintained-source snapshots differ")
        test_copy = base / "run"
        copy_exercise(exercise, test_copy)
        run = run_cases(root, test_copy)
        if run["returncode"] != 0 or run["counts"] != {"passed": CASE_COUNT, "failed": 0, "total": CASE_COUNT}:
            fail("reference suite failed or executed an unexpected number of cases\n" + str(run["output"])[-3000:])
        evidence = {
            "exercise": str(EXERCISE),
            "test_source": str(spec.relative_to(root)),
            "source_snapshot_hashes": {"one": first_hash, "two": second_hash},
            "source_snapshot_equal": True,
            "generation_note": "No per-exercise generator is present; snapshots compare the maintained spec source.",
            "python_version": sys.version,
            "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
            "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
            "metadata": result,
            "run": run,
        }
    out = root / "work/R53-T032/evidence.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {CASE_COUNT} canonical cases map to tests; two maintained-source snapshots match")
    print(f"Evidence: {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        fail(str(exc))
