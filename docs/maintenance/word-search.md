# Word Search Mutation Regression

## Contract and Test Mapping

The exercise asks for each requested word's first and last coordinates, including words written left to right. A horizontal candidate can begin in the first column; reported coordinates are one-based.

| Canonical test ID                      | Canonical description                                       | JavaScript test                                                         | Assertion                                                                                                                                    |
| -------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `b4057815-0d01-41f0-9119-6a91f54b2a0a` | Should accept an initial game grid and a target search word | `Should accept an initial game grid`; `Can accept a target search word` | Constructs `WordSearch(['jefblpepre'])`, then checks `instanceof`; separately checks `find(['glasnost'])` returns `{ glasnost: undefined }`. |
| `6b22bcc5-6cbf-4674-931b-d2edbff73132` | Should locate one word written left to right                | `Should locate a word written left to right`                            | On `['clojurermt']`, `find(['clojure'])` must equal `{ clojure: { start: [1, 1], end: [1, 7] } }`.                                           |

The first canonical description combines the initial-grid and target-word setup represented by two JavaScript spec cases; the test IDs above are from `.meta/tests.toml`, not inferred identifiers.

## Mutation Experiment

The maintained reference implementation in `exercises/practice/word-search/.meta/proof.ci.js` was not changed. In a temporary copy only, the first forward-search condition was mutated from:

```js
if (startCol) {
```

to:

```js
if (startCol > 1) {
```

`getStartCol()` converts a string index to one-based coordinates, so a word at column 1 has `startCol === 1`. The mutant wrongly rejects that valid candidate.

The existing rejecting case is ID `6b22bcc5-6cbf-4674-931b-d2edbff73132`, JavaScript test `Should locate a word written left to right`:

| Result                       | Input or output                                                 |
| ---------------------------- | --------------------------------------------------------------- |
| Input grid                   | `['clojurermt']`                                                |
| Target                       | `clojure`                                                       |
| Expected and original output | `{ clojure: { start: [1, 1], end: [1, 7] } }`                   |
| Mutated output               | `{ clojure: undefined }`                                        |
| Failed assertion             | `expect(wordSearch.find(['clojure'])).toEqual(expectedResults)` |

The minimized diagnostic is the valid 2×2 grid `['ab', 'cd']` with target `ab`. The original returns `{ ab: { start: [1, 1], end: [1, 2] } }`; the mutant returns `{ ab: undefined }`. A 1×1 puzzle with target `a` does not expose the mutation end-to-end because the later diagonal search can find that single letter. The 2×2 case is the smallest square grid with a multi-letter horizontal-only match, avoiding that fallback. Both original and mutant are run with identical diagnostic inputs. The original implementation passes; the deliberate mutant fails the named existing assertion. This is a regression experiment, not a claim that the maintained implementation is buggy.

## Reproduction

From the repository root, with the locked pnpm dependencies installed:

```sh
ASSIGNMENT=practice/word-search corepack pnpm node scripts/ci.mjs
python3 work/R53-T043/check.py
```

The first command is the actual track CI entry point; it enables `xtest` cases and runs the maintained reference in its temporary copy. The coursework checker independently copies the complete exercise, runs the test package script against the temporary reference, and runs the temporary mutant against the existing rejecting test and minimized diagnostic. It records commands, captured outputs, test counts, test ID, and tool versions in `work/R53-T043/evidence.json`.

The debugging hint is in `exercises/practice/word-search/.docs/hints.md`. It points learners to the first-column boundary and one-based coordinates without disclosing the reference algorithm.

`work/R53-T043/` is coursework evidence and must be excluded from any later upstream contribution branch.
