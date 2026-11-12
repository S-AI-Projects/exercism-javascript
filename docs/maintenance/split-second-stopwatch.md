# Maintenance Documentation: `split-second-stopwatch`

## Maintained File-Role Map

All exercise file roles are declared explicitly in `exercises/practice/split-second-stopwatch/.meta/config.json` under the `files` key and must resolve strictly inside `exercises/practice/split-second-stopwatch/`:

| Metadata Role (`config.json`) | Declared Path | Resolved Repository Path | Purpose |
| :--- | :--- | :--- | :--- |
| `files.solution` | `split-second-stopwatch.js` | `exercises/practice/split-second-stopwatch/split-second-stopwatch.js` | Learner starter stub (must remain unsolved on `main`) |
| `files.test` | `split-second-stopwatch.spec.js` | `exercises/practice/split-second-stopwatch/split-second-stopwatch.spec.js` | Jest specification suite executed against the solution |
| `files.example` | `.meta/proof.ci.js` | `exercises/practice/split-second-stopwatch/.meta/proof.ci.js` | Maintained reference implementation used to verify the test suite in CI |
| `files.editor` | *(omitted; defaults to `files.solution`)* | `exercises/practice/split-second-stopwatch/split-second-stopwatch.js` | Files opened by default in the Exercism web/CLI editor |

## How the Runner Resolves Tests and Reference Code

1. **Test discovery (`split-second-stopwatch.spec.js`):** Running `corepack pnpm jest` (or the exercise `package.json` `test` script) loads `exercises/practice/split-second-stopwatch/jest.config.js`, which sets `projects: ['<rootDir>']` and matches `**/?(*.)+(spec|test).[jt]s?(x)`, discovering `split-second-stopwatch.spec.js` and transpiling ES module imports via `babel-jest`.
2. **Reference verification (`.meta/proof.ci.js`):** Maintenance and CI scripts parse `.meta/config.json`, read `files.example[0]` (`.meta/proof.ci.js`), copy the exercise directory into an isolated workspace, and overwrite `files.solution[0]` (`split-second-stopwatch.js`) in that copy so `import { SplitSecondStopwatch } from './split-second-stopwatch'` resolves to the reference implementation without modifying the tracked learner stub.

## Hand-Authored vs. Generated Artifacts

- **Hand-authored / track-maintained files:**
  - `exercises/practice/split-second-stopwatch/split-second-stopwatch.js` (learner stub)
  - `exercises/practice/split-second-stopwatch/split-second-stopwatch.spec.js` (Jest test suite)
  - `exercises/practice/split-second-stopwatch/.meta/proof.ci.js` (reference solution)
  - `exercises/practice/split-second-stopwatch/.meta/config.json` (exercise metadata and file-role declarations)
  - `exercises/practice/split-second-stopwatch/jest.config.js`, `babel.config.js`, `eslint.config.mjs`, `package.json`
- **Synced / generated artifacts (`configlet sync`):**
  - `exercises/practice/split-second-stopwatch/.meta/tests.toml` (regenerated from upstream `problem-specifications` canonical data; preserves custom keys but strips `#` comments)
  - `exercises/practice/split-second-stopwatch/.docs/instructions.md` and `.docs/introduction.md` (synced from `problem-specifications`)

## Reproducible Validation Commands

Validate metadata containment and negative fixtures (`missing-reference`, `missing-test`, `outside-exercise`):

```bash
python3 tools/course_checks/r53-t028.py
```

Run the full end-to-end exercise & metadata check:

```bash
python3 work/R53-T028/check.py
```
