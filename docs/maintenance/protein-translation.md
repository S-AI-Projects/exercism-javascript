# Exercise Maintenance: Protein Translation Isolated Test Runner

## Overview

The `protein-translation` practice exercise teaches decoding RNA strands into polypeptide chains (proteins) composed of amino acids. The implementation must map nucleotide triplets (codons) to amino acids, stop processing upon encountering any of the three STOP codons (`UAA`, `UAG`, `UGA`), and throw an `Invalid codon` error when encountering non-translatable or incomplete codons.

This maintenance document specifies the operation, requirements, and verification model of the isolated test runner implemented in `tools/course_checks/r53-t049.py`.

---

## What the Isolated Runner Does

`tools/course_checks/r53-t049.py` executes the entire exercise test suite against the track's maintained reference implementation in an isolated environment. Specifically, the runner:

1. **Resolves Exercise Paths**: Reads `exercises/practice/protein-translation/.meta/config.json` to resolve the solution (`protein-translation.js`), test (`protein-translation.spec.js`), and reference (`.meta/proof.ci.js`) files without heuristic guessing.
2. **Clones into an Isolated Directory**: Creates a transient temporary directory via Python's `tempfile.mkdtemp` and copies the full exercise directory into it (including hidden metadata and configuration directories).
3. **Substitutes the Reference Implementation**: Copies `.meta/proof.ci.js` over `protein-translation.js` **only** inside the temporary copy.
4. **Enables All Test Cases**: Rewrites skipped tests (`xtest` and `xit` to `test` and `it`, and `xdescribe` to `describe`) inside the isolated copy of `protein-translation.spec.js` so that all 29 test cases run.
5. **Executes the Official Test Script**: Discovers and runs the package test command declared in `exercises/practice/protein-translation/package.json` (`corepack pnpm jest`) with `--runInBand`, `--watch=false`, and `--json`.
6. **Validates Test Counts and Assertions**: Dynamically extracts the executed test counts from Jest's JSON report, verifies that zero-test runs are rejected, verifies that all assertions pass, and inspects specifically required named cases.
7. **Guarantees Immediate Cleanup**: Automatically removes all temporary directories upon completion, failure, or process interruption (`SIGINT`, `SIGTERM`).
8. **Protects Working Tree Immutability**: Confirms that original learner files in the repository working tree remain unchanged.

---

## Why an Isolated Temporary Copy is Necessary

Executing tests against the reference implementation in an isolated temporary directory is critical for several reasons:

- **Preserving Learner Working Files**: In a student environment, the learner's solution file (`protein-translation.js`) represents their active work. Overwriting this file in the working tree would destroy the learner's progress or leave an unsolved skeleton in a corrupted state.
- **Concurrency Safety**: Multiple CI checks or parallel test tasks can run concurrently without clashing over file locks or race conditions in the exercise directory.
- **Clean Git Status**: Zero unstaged changes, temporary build artifacts, or modified timestamps are introduced into the repository working tree.
- **Fail-Safe Testing**: If a test run fails, crashes, or is forcibly killed, the isolated directory is removed cleanly without leaving remnants in the repository.

---

## How the Maintained Reference is Substituted

The exercise configuration (`.meta/config.json`) defines:

```json
{
  "files": {
    "solution": ["protein-translation.js"],
    "test": ["protein-translation.spec.js"],
    "example": [".meta/proof.ci.js"]
  }
}
```

During execution:

1. The original repository working tree is untouched.
2. The isolated runner copies `temp_dir/exercise/.meta/proof.ci.js` to `temp_dir/exercise/protein-translation.js`.
3. Because `protein-translation.spec.js` executes `import { translate } from './protein-translation';`, Node.js resolves `./protein-translation` to the substituted reference file in the temporary directory.

---

## How Learner Files Are Protected

1. **Zero Working-Tree Writes**: The runner performs zero write or edit operations inside `exercises/practice/protein-translation/`.
2. **Cryptographic Hash Verification**: The runner computes the SHA-256 digest of the learner solution file (`protein-translation.js`) before running any child processes and asserts that the digest is identical after execution finishes.
3. **Signal Trapping**: Interruption signals (`SIGINT`, `SIGTERM`) and normal process exit handlers (`atexit`) purge any active temporary directories without affecting the repository files.

---

## Runtime and Tool Requirements

- **Python**: Python 3.9 or newer (standard library only; uses `subprocess`, `tempfile`, `hashlib`, `json`, `signal`, `pathlib`).
- **Node.js**: Node.js v20.x or v24.x.
- **Package Manager**: `pnpm@9.15.2` managed via Corepack, determined by the presence of `pnpm-lock.yaml` in the repository root.

---

## Exact Command to Execute the Runner

From the repository root:

```bash
python3 tools/course_checks/r53-t049.py
```

### CLI Options

The runner supports optional CLI flags for automated testing harnesses:

- `--reference-path <path>`: Substitute an alternate reference implementation (used to test failure detection).
- `--spec-path <path>`: Substitute an alternate test specification.
- `--empty-tests`: Simulate a test run where zero tests execute.
- `--test-name-pattern <pattern>`: Filter tests matching a regular expression via Jest.
- `--json-output <path>`: Write structured execution metrics to a JSON file.

---

## How Test Counts and Failures Are Reported

1. **Dynamic Count Extraction**: The runner passes `--json --outputFile=<path>` to Jest. From the resulting JSON output, the runner extracts:
   - `numTotalTests`: Total tests defined in the suite (29).
   - `numPassedTests`: Number of passing assertions (29).
   - `numFailedTests`: Number of failing assertions (0).
   - `numPendingTests`: Number of skipped assertions (0).
   - **Executed Tests**: Computed dynamically as `numPassedTests + numFailedTests`.
2. **Zero-Test Rejection Guard**: If `executed_tests == 0`, the runner raises `ZeroTestsExecutedError`, prints a diagnostic message, and exits with status `2`.
3. **Failure Propagation**: If any assertion fails (`numFailedTests > 0`) or if the child process exits with non-zero status, the runner prints the failure details, cleans up temporary directories, and exits with status `1`.
4. **Named Case Verification**: The runner verifies that the following key cases passed:
   - `Empty RNA sequence results in no proteins`
   - `Methionine RNA sequence`
   - `Phenylalanine RNA sequence 1`
