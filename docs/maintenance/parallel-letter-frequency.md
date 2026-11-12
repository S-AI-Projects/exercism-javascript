# Maintenance Documentation: `parallel-letter-frequency`

## Overview & Generator Architecture

The `exercism/javascript` track does **not** use a per-exercise Jinja or automated code-generation template to generate `.spec.js` files from canonical problem specifications. Instead, test maintenance follows a two-part workflow:

1. **Canonical Metadata Sync (`configlet sync`)**:
   - **Input**: Upstream `exercism/problem-specifications` canonical data (`canonical-data.json`) and local `exercises/practice/parallel-letter-frequency/.meta/tests.toml`.
   - **Command**:
     - `./bin/fetch-configlet`
     - `./bin/configlet sync --exercise parallel-letter-frequency`
   - **Generated Output**: `exercises/practice/parallel-letter-frequency/.meta/tests.toml` (auto-generated UUID registry and descriptions).
2. **Track Config Sync (`scripts/sync.mjs`)**:
   - **Input**: Root `exercise-package.json` and root configuration templates (`.npmrc`, `babel.config.js`, `eslint.config.mjs`, `jest.config.js`, `LICENSE`, `.gitignore`).
   - **Command**:
     - `ASSIGNMENT=practice/parallel-letter-frequency node scripts/sync.mjs`
   - **Generated Output**: Synchronized `exercises/practice/parallel-letter-frequency/package.json` and shared tooling configs.
3. **Hand-Maintained Test Suite (`parallel-letter-frequency.spec.js`)**:
   - `exercises/practice/parallel-letter-frequency/parallel-letter-frequency.spec.js` is maintained by hand to map each canonical UUID in `.meta/tests.toml` to a Jest `test()` / `xtest()` block using async/await (`await expect(actual).resolves.toEqual(expected)`).
   - Because `parallel-letter-frequency.spec.js` is hand-maintained rather than emitted with a timestamp header, two independent sync/regeneration runs produce byte-for-byte identical `.spec.js` outputs (0 diffs after timestamp normalization).

---

## File Maintenance Classification

| File Path | Maintenance Mode | Source / Command |
| :--- | :--- | :--- |
| `exercises/practice/parallel-letter-frequency/.meta/tests.toml` | Auto-generated | `./bin/configlet sync --exercise parallel-letter-frequency` |
| `exercises/practice/parallel-letter-frequency/package.json` | Auto-synced | `ASSIGNMENT=practice/parallel-letter-frequency node scripts/sync.mjs` |
| `exercises/practice/parallel-letter-frequency/parallel-letter-frequency.spec.js` | Hand-maintained | Mapped 1:1 from `.meta/tests.toml` canonical cases |
| `exercises/practice/parallel-letter-frequency/parallel-letter-frequency.js` | Hand-maintained | Learner starter stub (must remain unsolved) |
| `exercises/practice/parallel-letter-frequency/.meta/proof.ci.js` | Hand-maintained | Reference implementation using `node:worker_threads` |

---

## Canonical Case-to-Output Mapping

The table below documents the mapping from `.meta/tests.toml` canonical UUIDs to `parallel-letter-frequency.spec.js` test assertions, highlighting the three anchor cases:

| Canonical UUID | `tests.toml` Description | Spec Block | Input (`texts`) | Expected Output | Anchor Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `c054d642-c1fa-4234-8007-9339f2337886` | `no texts` | `test('no texts', ...)` | `[]` | `{}` | **Yes (Anchor 1)** |
| `818031be-49dc-4675-b2f9-c4047f638a2a` | `one text with one letter` | `xtest('one text with one letter', ...)` | `['a']` | `{ a: 1 }` | **Yes (Anchor 2)** |
| `c0b81d1b-940d-4cea-9f49-8445c69c17ae` | `one text with multiple letters` | `xtest('one text with multiple letters', ...)` | `['bbcccd']` | `{ b: 2, c: 3, d: 1 }` | **Yes (Anchor 3)** |
| `708ff1e0-f14a-43fd-adb5-e76750dcf108` | `two texts with one letter` | `xtest('two texts with one letter', ...)` | `['e', 'f']` | `{ e: 1, f: 1 }` | No |
| `1b5c28bb-4619-4c9d-8db9-a4bb9c3bdca0` | `two texts with multiple letters` | `xtest('two texts with multiple letters', ...)` | `['ggh', 'hhi']` | `{ g: 2, h: 3, i: 1 }` | No |
| `6366e2b8-b84c-4334-a047-03a00a656d63` | `ignore letter casing` | `xtest('ignore letter casing', ...)` | `['m', 'M']` | `{ m: 2 }` | No |
| `92ebcbb0-9181-4421-a784-f6f5aa79f75b` | `ignore whitespace` | `xtest('ignore whitespace', ...)` | `['   ', '\t', '\r\n']` | `{}` | No |
| `bc5f4203-00ce-4acc-a5fa-f7b865376fd9` | `ignore punctuation` | `xtest('ignore punctuation', ...)` | `['!', '?', ';', ',', '.']` | `{}` | No |
| `68032b8b-346b-4389-a380-e397618f6831` | `ignore numbers` | `xtest('ignore numbers', ...)` | `['1'..'0']` | `{}` | No |
| `aa9f97ac-3961-4af1-88e7-6efed1bfddfd` | `Unicode letters` | `xtest('Unicode letters', ...)` | `['本', 'φ', 'ほ', 'ø']` | `{ 本: 1, φ: 1, ほ: 1, ø: 1 }` | No |
| `7b1da046-701b-41fc-813e-dcfb5ee51813` | `combination of lower- and uppercase letters, punctuation and white space` | `xtest('combination of...', ...)` | Tolkien excerpt (1 string) | 22-letter frequency map | No |
| `4727f020-df62-4dcf-99b2-a6e58319cb4f` | `large texts` | `xtest('large texts', ...)` | Dostoevsky excerpts (4 strings) | 25-letter frequency map | No |
| `adf8e57b-8e54-4483-b6b8-8b32c115884c` | `many small texts` | `xtest('many small texts', ...)` | `Array(50).fill('abbccc')` | `{ a: 50, b: 100, c: 150 }` | No |

---

## Reproducing & Verifying the Test Suite

To reproduce the test execution locally without modifying the learner stub (`parallel-letter-frequency.js`):

- `python3 tools/course_checks/r53-t022.py`

And to generate task verification evidence in `work/R53-T022/`:

- `python3 work/R53-T022/check.py`
