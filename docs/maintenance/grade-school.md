# Maintenance Documentation: `grade-school`

## Isolated Reference Test Runner

`tools/course_checks/r53-t029.py` runs the `grade-school` test suite against the maintained reference implementation (`.meta/proof.ci.js`) inside an isolated temporary directory so that `exercises/practice/grade-school/grade-school.js` remains unsolved in the working tree.

### How It Works
1. **Metadata Resolution:** Reads `exercises/practice/grade-school/.meta/config.json` to resolve `files.solution` (`grade-school.js`), `files.test` (`grade-school.spec.js`), and `files.example` (`.meta/proof.ci.js`).
2. **Hash Verification:** Computes SHA-256 hashes of every file under `exercises/practice/grade-school/` before execution and asserts identical hashes in a `finally` block after execution (even on failure or interruption).
3. **Temporary Workspace Execution:** Copies the exercise (including dotfiles) into a temporary directory, converts `xtest(` to `test(` in the temporary spec copy, substitutes `.meta/proof.ci.js` into the temporary `grade-school.js`, and runs Jest with `--watchAll=false --no-watchman --verbose`.
4. **Failure Propagation:** Exits non-zero if Jest exits non-zero, if zero tests execute (`passed === 0` or `total === 0`), or if any working-tree file hash changes.

### Prerequisites & Tool Requirements
- **Node.js & Package Manager:** Node matching the workspace version and `pnpm@9.15.2` (specified in `exercises/practice/grade-school/package.json`).
- **Python 3:** Python 3.10+ standard library (`subprocess`, `tempfile`, `hashlib`, `json`, `shutil`).

### Commands

Run the isolated runner directly:

```bash
python3 tools/course_checks/r53-t029.py
```

Run the full verification suite (including negative failing-reference and zero-test scenarios):

```bash
python3 work/R53-T029/check.py
```
