# Maintenance: react

## Isolated Test Runner

The `react` exercise has an isolated test runner that validates the reference
implementation without modifying the learner's starter files.

### Command

```bash
python3 tools/course_checks/r53-t010.py
```

### What It Does

1. **Copies** the exercise directory to an isolated temporary location inside the repository.
2. **Substitutes** the reference implementation (`.meta/proof.ci.js`) for the
   learner stub (`react.js`) — only in the temporary copy.
3. **Enables** all test cases by replacing `xtest(` with `test(`.
4. **Runs** Jest with `--no-cache --ci` flags.
5. **Reports** the number of passed/total test cases (13 tests total).
6. **Verifies** that learner files in the working tree were not modified
   (SHA-256 hash comparison before and after).
7. **Cleans up** the temporary directory.

### Additional Modes

| Flag            | Purpose                                           | Expected Exit |
|-----------------|---------------------------------------------------|---------------|
| *(none)*        | Run all tests with the real reference             | 0 (all pass)  |
| `--fail-ref`    | Inject a deliberately failing reference           | 1 (failure)   |
| `--empty-tests` | Run with an empty test file (zero-test guard)     | 2 (zero tests)|

### Prerequisites

- **Node.js** ≥ 20 (matching `package.json` requirements)
- **pnpm** (selected by the lockfile)
- **Python 3** ≥ 3.10
- Dependencies installed: `pnpm install` in repo root
