# Exercise Maintenance: Poker

## Overview

The `poker` practice exercise teaches ranking and comparison of 5-card poker hands according to standard poker rules. The objective is to pick the best hand(s) from a list of poker hands represented as whitespace-delimited strings of 5 cards (e.g., `'4S 5S 7H 8D JC'`). When there is a tie, all winning hands must be returned in their original input order.

This maintenance document defines the exercise file-role architecture, metadata validation rules, test runner execution model, and reproducible verification procedures for the JavaScript track.

---

## Exercise File-Role Map

The following table maps each file associated with the Poker exercise to its role in the Exercism JavaScript track repository:

| Repository File Path                             | Role                                | Source vs. Generated | Description                                                                                                                                                                                                                                                                                           |
| :----------------------------------------------- | :---------------------------------- | :------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exercises/practice/poker/poker.js`              | Learner solution stub               | Source               | The initial skeleton file provided to learners. Exports `bestHands(hands)` which throws `new Error('Remove this statement and implement this function');`. Must remain unsolved in the repository.                                                                                                    |
| `exercises/practice/poker/.meta/proof.ci.js`     | Maintained reference implementation | Source               | Maintained reference solution implementing complete hand ranking logic (straight flush, four of a kind, full house, flush, straight, three of a kind, two pair, one pair, high card) and tie-breaking. Used by CI and verification scripts to prove exercise solvability.                             |
| `exercises/practice/poker/poker.spec.js`         | Test specification                  | Source               | Jest test specification containing 37 test cases validating all poker hand categories, kickers, ace-low straights (A-2-3-4-5), ace-high straights (10-J-Q-K-A), multiple decks, and ties. The first test is active (`test`), while tests 2–37 are skipped (`xtest`) for step-by-step TDD progression. |
| `exercises/practice/poker/.meta/tests.toml`      | Canonical test definitions          | Source               | Exercise metadata tracking canonical problem-specifications test cases by UUID, indicating which canonical cases are included or excluded.                                                                                                                                                            |
| `exercises/practice/poker/.meta/config.json`     | Exercise metadata configuration     | Source               | Track configuration declaring authors, contributors, blurb, source, and file associations (`solution`, `test`, `example`).                                                                                                                                                                            |
| `exercises/practice/poker/package.json`          | Exercise package manifest           | Source               | Package configuration declaring dependencies (`@jest/globals`, Babel), ES module support (`"type": "module"`), and test execution script (`"test": "corepack pnpm jest"`).                                                                                                                            |
| `exercises/practice/poker/.docs/instructions.md` | Problem instructions                | Source               | General problem description shared across Exercism tracks.                                                                                                                                                                                                                                            |
| `exercises/practice/poker/.docs/introduction.md` | Problem introduction                | Source               | Contextual background and rules for poker hand evaluation.                                                                                                                                                                                                                                            |
| `tools/course_checks/r53-t048.py`                | Exercise metadata checker           | Source               | Coursework validation tool that parses `.meta/config.json`, resolves all file paths, enforces security guards against directory traversal, and validates negative fixtures.                                                                                                                           |
| `work/R53-T048/check.py`                         | Coursework validation runner        | Source               | Isolated automated runner that verifies metadata, clones the exercise into a temporary directory, runs Jest against the reference implementation, validates all 37 test cases, checks immutability of learner stubs, and emits audit evidence.                                                        |
| `work/R53-T048/inputs.json`                      | Validation input record             | Generated            | Structured JSON capturing metadata config, invalid fixture inputs, and all 37 exercise test case inputs.                                                                                                                                                                                              |
| `work/R53-T048/results.json`                     | Validation results record           | Generated            | Structured JSON capturing metadata validation results, fixture rejection records, Jest test counts, and case-by-case outputs.                                                                                                                                                                         |
| `work/R53-T048/evidence.json`                    | Comprehensive audit evidence        | Generated            | Reproducible audit log recording tool versions, file SHA-256 hashes, test counts, required named case outputs, and guard self-test results.                                                                                                                                                           |
| `tmp_exercises/practice/poker/`                  | Temporary CI directory              | Generated            | Transient working directory created during CI execution (`scripts/helpers.mjs`) to test the reference implementation in isolation without mutating the repository working tree.                                                                                                                       |

### Note on Example and Editor Files

- **Example Files (`files.example`)**: Declared in `exercises/practice/poker/.meta/config.json` as `[".meta/proof.ci.js"]`. For practice exercises, `example` points to the track's reference implementation. (In concept exercises, this category is named `exemplar`).
- **Editor Files (`files.editor`)**: Not declared or required for Poker. In the Exercism track specification, `files.editor` is reserved for concept exercises requiring editor-specific configuration (such as read-only web editor assets or instructions).

---

## Metadata Configuration and Path Resolution

The metadata file `exercises/practice/poker/.meta/config.json` contains:

```json
{
  "authors": ["kytrinyx"],
  "contributors": [
    "ankor",
    "matthewmorgan",
    "rchavarria",
    "SleeplessByte",
    "tejasbubane"
  ],
  "files": {
    "solution": ["poker.js"],
    "test": ["poker.spec.js"],
    "example": [".meta/proof.ci.js"]
  },
  "blurb": "Pick the best hand(s) from a list of poker hands.",
  "source": "Inspired by the training course from UTD, funded by AT&T.",
  "source_url": "https://web.archive.org/web/20210509015949/http://www.utdallas.edu/~cda/cs6301_summer2008/index.html"
}
```

### Path Resolution Rules

Every path declared under `files` must resolve inside the exercise root directory (`exercises/practice/poker/`):

1. **`files.solution` (`poker.js`)**:
   Resolves to: `exercises/practice/poker/poker.js`
   Role: Initial learner skeleton stub.
2. **`files.test` (`poker.spec.js`)**:
   Resolves to: `exercises/practice/poker/poker.spec.js`
   Role: Exercise Jest test suite.
3. **`files.example` (`.meta/proof.ci.js`)**:
   Resolves to: `exercises/practice/poker/.meta/proof.ci.js`
   Role: Exercise reference implementation.

### Automated Path Validation (`tools/course_checks/r53-t048.py`)

The validation tool enforces strict integrity checks:

- **Object verification**: Ensures `files` is a dictionary with non-empty list values.
- **Traversal rejection**: Rejects any path containing `..` or attempting parent-directory traversal.
- **Escape rejection**: Ensures the resolved absolute path starts with the exercise directory path.
- **File presence**: Ensures that every declared file exists on disk.
- **Negative fixture testing**: Verifies that invalid metadata (missing reference file, missing test file, and parent directory traversal) is properly detected and rejected with clear error messages.

---

## Test Runner Explanation

The repository uses Jest as its JavaScript test runner, configured with Babel for ES module transpilation. Two distinct test runner workflows exist in the repository:

### 1. Learner-Facing Test Suite

When a student works on the exercise locally:

1. **Execution**: The learner runs `corepack pnpm test` (or `pnpm test`) inside `exercises/practice/poker/`.
2. **Script Resolution**: `exercises/practice/poker/package.json` defines `"scripts": { "test": "corepack pnpm jest" }`.
3. **Discovery**: Jest searches the working directory using its default test file matching pattern:
   `**/?(*.)+(spec|test).[jt]s?(x)`
   This discovers `exercises/practice/poker/poker.spec.js`.
4. **Target Import**: `poker.spec.js` executes:
   ```javascript
   import { bestHands } from './poker';
   ```
   Node.js module resolution resolves `./poker` to `exercises/practice/poker/poker.js`, which is the learner's solution file.
5. **Skipped Tests (`xtest`)**: By default, only the first test case (`single hand always wins`) is marked `test(...)`. The remaining 36 cases are marked `xtest(...)` (skipped). Learners incrementally change `xtest` to `test` as they develop their solution.

### 2. CI Proof Checker and Coursework Validation Runner

In CI and during maintenance verification, the test runner must prove that the exercise is solvable by running all 37 test cases against the maintained reference implementation without modifying the working tree:

1. **Isolation**: A temporary directory is created (e.g., `tmp_exercises/practice/poker/` in `scripts/helpers.mjs` or a temporary directory via Python `tempfile.TemporaryDirectory`).
2. **File Synchronization**: The entire exercise directory, including hidden directories (`.meta`, `.docs`), is copied to the temporary directory.
3. **Reference Substitution**: The reference implementation (`.meta/proof.ci.js`) is copied over `poker.js` **only** inside the temporary directory:
   ```text
   temp_dir/.meta/proof.ci.js  --->  temp_dir/poker.js
   ```
   The original learner stub `exercises/practice/poker/poker.js` in the repository working tree is untouched.
4. **Unskipping Tests**: All `xtest(...)` occurrences in `temp_dir/poker.spec.js` are replaced with `test(...)` so that all 37 test cases execute.
5. **Headless Execution**: Jest is invoked with `--runInBand --watch=false --runTestsByPath poker.spec.js --json`.
   - `--runInBand`: Runs tests sequentially in the current process, avoiding worker spawn overhead.
   - `--watch=false`: Disables interactive terminal watch mode.
   - `--runTestsByPath`: Explicitly targets the copied specification file.
   - `--json`: Emits machine-readable execution counts (`numTotalTests`, `numPassedTests`, `numFailedTests`).
6. **Result Verification**: The runner asserts that:
   - `numTotalTests === 37`
   - `numPassedTests === 37`
   - `numFailedTests === 0`
7. **Clean Up**: The temporary directory is deleted automatically upon completion.

---

## Validation Instructions

All validation commands must be run from the repository root:

```bash
cd /Users/anuradhagaur/exercism_javascript/exercism-javascript/exercism-javascript
```

### 1. Validate Exercise Metadata Configuration

Execute the metadata checker script:

```bash
python3 tools/course_checks/r53-t048.py
```

**Expected output:**

```text
=== Validating Exercise Metadata for Poker ===
Repository Root:    /path/to/exercism-javascript
Exercise Directory: /path/to/exercism-javascript/exercises/practice/poker
Config File:        /path/to/exercism-javascript/exercises/practice/poker/.meta/config.json

[PASS] Real config.json validated successfully:
  - files.solution: poker.js -> /path/to/.../exercises/practice/poker/poker.js
  - files.test: poker.spec.js -> /path/to/.../exercises/practice/poker/poker.spec.js
  - files.example: .meta/proof.ci.js -> /path/to/.../exercises/practice/poker/.meta/proof.ci.js

=== Testing Invalid Metadata Fixtures ===
[PASS] Fixture 'missing_reference_path': A missing-reference path ('files.example')
[PASS] Fixture 'missing_test_path': A missing-test path ('files.test')
[PASS] Fixture 'outside_exercise_path': An outside-exercise path attempting parent directory traversal

All metadata validations and fixture rejection checks succeeded.
```

### 2. Run Coursework Validation Runner & Audit Evidence Generation

Execute the automated test runner:

```bash
python3 work/R53-T048/check.py
```

**Expected output:**

- Validates real `config.json` and all 3 invalid fixtures.
- Clones exercise to isolated temporary directory.
- Runs Jest against reference implementation: **37/37 passed, 0 failed**.
- Runs Node probe verifying outputs for all 37 cases.
- Confirms the three required named test cases:
  1. `single hand always wins`
  2. `highest card out of all hands wins`
  3. `a tie has multiple winners`
- Confirms original learner stub `poker.js` remains unsolved and strictly unchanged.
- Writes structured evidence files:
  - `work/R53-T048/inputs.json`
  - `work/R53-T048/results.json`
  - `work/R53-T048/evidence.json`

### 3. Run Track CI Scripts

To verify repository-level CI compatibility for the Poker exercise:

```bash
# Run CI proof test runner
ASSIGNMENT=practice/poker corepack pnpm node scripts/ci.mjs

# Run CI checksum, stub, and linting checks
ASSIGNMENT=practice/poker corepack pnpm node scripts/ci-check.mjs
```

Both commands must exit with status `0`.
