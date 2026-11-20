# Zebra-puzzle test preparation

## Canonical cases and JavaScript tests

The canonical data is maintained in [problem-specifications](https://github.com/exercism/problem-specifications/blob/main/exercises/zebra-puzzle/canonical-data.json). It identifies the cases by UUID and gives each a property, input, and expected result. The JavaScript track records the UUIDs in `exercises/practice/zebra-puzzle/.meta/tests.toml`.

| UUID | Canonical case/property | JavaScript test | JavaScript method | Expected output |
| --- | --- | --- | --- | --- |
| `16efb4e4-8ad7-4d5e-ba96-e5537b66fd42` | Resident who drinks water / `drinksWater` | `resident who drinks water` | `waterDrinker()` | `Norwegian` |
| `084d5b8b-24e2-40e6-b008-c800da8cd257` | Resident who owns zebra / `ownsZebra` | `resident who owns zebra` | `zebraOwner()` | `Japanese` |

Both metadata entries are included by default. In the maintained spec, the water test is an active `test(...)`, while the zebra test is an `xtest(...)` that Jest skips in a direct run.

## Source files and preparation

- The canonical JSON in `problem-specifications` defines the UUIDs, canonical properties, empty inputs, and expected results.
- `.meta/tests.toml` records which canonical UUIDs this exercise implements. Configlet sync updates this metadata; it does not generate JavaScript tests.
- `.meta/config.json` tells repository tooling which files are the learner solution, test, and reference example.
- `zebra-puzzle.spec.js` is the maintained JavaScript test source. There is no per-exercise Jinja template or JavaScript test generator in this track.
- `.meta/proof.ci.js` is the maintained reference implementation used for repository checks. `zebra-puzzle.js` remains the learner's starter file.
- `scripts/helpers.mjs` prepares a temporary `tmp_exercises/practice/zebra-puzzle` copy: it copies the maintained spec, changes `xtest(...)` to `test(...)`, and copies the reference example to the configured solution path. `scripts/pr.mjs` invokes that helper and runs Jest. The prepared copy is temporary; it does not replace the maintained spec.

## Commands

Run these from the repository root:

```sh
# Fetch configlet once if bin/configlet is not already present.
./bin/fetch-configlet

# Synchronize canonical metadata in .meta/tests.toml.
./bin/configlet sync

# Install the repository's locked JavaScript dependencies.
corepack pnpm install --frozen-lockfile

# Run the repository's pull-request preparation and test path for this exercise.
corepack pnpm node scripts/pr.mjs exercises/practice/zebra-puzzle/zebra-puzzle.spec.js

# Run the focused reproducibility and reference-solution checks.
python3 work/R53-T012/check.py
```

Configlet sync and JavaScript test preparation are separate operations: the first updates canonical metadata; the second prepares and tests a temporary copy from the maintained JavaScript spec. The focused check prepares that copy twice and compares the test files byte-for-byte. The current prepared tests contain no generated timestamps, so no timestamp normalization is needed.
