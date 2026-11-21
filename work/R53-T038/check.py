#!/usr/bin/env python3
"""Validate Pangram file metadata and run all cases against its reference."""

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


EXERCISE = Path("exercises/practice/pangram")
REQUIRED_ROLES = {"solution", "test", "example"}
INVALID_FIXTURES = {
    "missing-reference": ("example", ".meta/missing-proof.ci.js", "does not exist"),
    "missing-test": ("test", "missing.spec.js", "does not exist"),
    "outside-exercise": ("solution", "../README.md", "escapes the exercise"),
}


class ConfigError(ValueError):
    pass


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(exercise: Path) -> dict[str, str]:
    config_path = exercise / ".meta/config.json"
    config = json.loads(config_path.read_text())
    files = config.get("files")
    if not isinstance(files, dict):
        raise ConfigError("files must be an object")
    if not REQUIRED_ROLES.issubset(files):
        raise ConfigError("solution, test, and example roles are required")
    resolved: dict[str, str] = {}
    for role, paths in files.items():
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
            raise ConfigError(f"files.{role} must be a non-empty list of paths")
        for relative in paths:
            candidate = Path(relative)
            if candidate.is_absolute():
                raise ConfigError(f"files.{role} absolute path is outside the exercise: {relative}")
            path = (exercise / candidate).resolve()
            if not path.is_relative_to(exercise.resolve()):
                raise ConfigError(f"files.{role} path escapes the exercise: {relative}")
            if not path.is_file():
                raise ConfigError(f"files.{role} path does not exist: {relative}")
            resolved[f"{role}:{relative}"] = str(path.relative_to(exercise.resolve()))
    return resolved


def verify_bad_fixtures(exercise: Path, temp: Path) -> dict[str, str]:
    outcomes = {}
    real_config = json.loads((exercise / ".meta/config.json").read_text())
    for name, (role, invalid_path, expected_reason) in INVALID_FIXTURES.items():
        fixture = temp / name / "exercise"
        shutil.copytree(exercise, fixture, ignore=shutil.ignore_patterns("node_modules"))
        config = json.loads(json.dumps(real_config))
        config["files"][role] = [invalid_path]
        (fixture / ".meta/config.json").write_text(json.dumps(config, indent=2) + "\n")
        try:
            validate(fixture)
        except ConfigError as error:
            if expected_reason not in str(error):
                fail(f"{name} failed for the wrong reason: {error}")
            outcomes[name] = str(error)
        else:
            fail(f"invalid fixture {name} was accepted")
    return outcomes


def run_reference(root: Path, source: Path, dest: Path) -> dict[str, object]:
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("node_modules"))
    solution_path = validate(dest)
    config = json.loads((dest / ".meta/config.json").read_text())
    solution = dest / config["files"]["solution"][0]
    spec = dest / config["files"]["test"][0]
    example = dest / config["files"]["example"][0]
    spec.write_text(spec.read_text().replace("xtest(", "test("))
    shutil.copyfile(example, solution)
    dependency_link = dest / "node_modules"
    if (root / "node_modules").is_dir():
        dependency_link.symlink_to(root / "node_modules", target_is_directory=True)
    if shutil.which("corepack") is None:
        fail("corepack is not installed; install the repository's pnpm package manager before running Jest")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(root / "node_modules/.bin"), env.get("PATH", "")])
    command = ["corepack", "pnpm", "run", "test", "--watchAll=false", "--runInBand"]
    result = subprocess.run(command, cwd=dest, env=env, text=True, stdout=subprocess.PIPE,
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
    real_map = validate(exercise)
    canonical = tomllib.loads((exercise / ".meta/tests.toml").read_text())
    config = json.loads((exercise / ".meta/config.json").read_text())
    spec = exercise / config["files"]["test"][0]
    case_names = re.findall(r"\b(?:x?test)\(([\"'])(.*?)\1", spec.read_text())
    titles = [title for _quote, title in case_names]
    anchors = ("empty sentence", "perfect lower case", "only lower case")
    if any(anchor not in titles for anchor in anchors):
        fail("a required named case is missing from the test source")
    if len(canonical) != 11 or len(titles) != 10:
        fail(f"unexpected case counts: {len(canonical)} canonical, {len(titles)} spec")
    solution = exercise / config["files"]["solution"][0]
    before = sha(solution)
    with tempfile.TemporaryDirectory(prefix="R53-T038-") as temp_dir:
        temp = Path(temp_dir)
        invalid = verify_bad_fixtures(exercise, temp)
        run = run_reference(root, exercise, temp / "reference")
    after = sha(solution)
    if before != after:
        fail("learner stub changed during the reference check")
    if run["returncode"] or run["counts"] != {"passed": len(titles), "failed": 0, "total": len(titles)}:
        fail("reference suite failed or test count was unexpected\n" + str(run["output"])[-2500:])
    evidence = {
        "exercise": str(EXERCISE), "python_version": sys.version,
        "node_version": subprocess.run(["node", "--version"], text=True, capture_output=True, check=False).stdout.strip(),
        "pnpm_version": subprocess.run(["corepack", "pnpm", "--version"], cwd=root, text=True, capture_output=True, check=False).stdout.strip(),
        "real_file_map": real_map, "editor_role_declared": "editor" in config["files"],
        "canonical_count": len(canonical), "spec_count": len(titles),
        "invalid_fixture_results": invalid, "learner_sha256_before": before,
        "learner_sha256_after": after, "reference_run": run,
    }
    output = root / "work/R53-T038/evidence.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: real map valid; 3 invalid fixtures rejected; {len(titles)} reference cases pass")
    print(f"Evidence: {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, ConfigError, KeyError, TypeError) as exc:
        fail(str(exc))
