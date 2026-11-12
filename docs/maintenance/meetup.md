# Meetup Test Generation and Verification

## Purpose

`exercises/practice/meetup/.meta/tests.toml` records canonical test UUIDs and descriptions. The maintained `meetup.spec.js` contains the executable inputs and expected JavaScript `Date` values. This repository does **not** generate `meetup.spec.js` from `tests.toml`: the canonical metadata does not contain those inputs or outputs, and the track's contribution guidance says to update the spec when syncing canonical data.

The track CI preparation helper generates a temporary runnable copy of the test suite. `scripts/helpers.mjs` `prepare()` copies the test and reference implementation to `tmp_exercises/practice/meetup/`, changes `xtest` to `test` in that copy, and leaves maintained files alone. `scripts/ci.mjs` is the CI entry point that calls the helper and runs Jest against the temporary copy.

## Maintained Inputs and Generated Output

| Path                                           | Role                                                                                                                                                                  |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exercises/practice/meetup/.meta/tests.toml`   | Canonical UUIDs and test descriptions; maintained metadata, not executable test data.                                                                                 |
| `exercises/practice/meetup/meetup.spec.js`     | Maintained assertions with the input arguments and expected `Date` values. Do not edit as generated output; update it when intentionally syncing canonical test data. |
| `exercises/practice/meetup/.meta/config.json`  | Maintained mapping of solution, test, and reference-example files.                                                                                                    |
| `exercises/practice/meetup/.meta/proof.ci.js`  | Maintained reference implementation copied to the temporary solution path for CI.                                                                                     |
| `tmp_exercises/practice/meetup/meetup.spec.js` | Generated CI copy with skipped `xtest` cases promoted. It is temporary and must not be hand-edited or committed.                                                      |

## Generator and CI Commands

Prerequisites: run from the repository root with Node.js, Corepack/pnpm matching root `package.json` and `pnpm-lock.yaml`, and dependencies installed with `corepack pnpm install --frozen-lockfile`.

The focused helper invocation used by the round-trip check is:

```sh
corepack pnpm node --input-type=module -e "import { prepare } from './scripts/helpers.mjs'; prepare('practice/meetup');"
```

It creates `tmp_exercises/practice/meetup/meetup.spec.js` and the reference-backed `meetup.js`. To run the repository's actual CI entry point (which prepares, tests, and cleans the temporary files):

```sh
ASSIGNMENT=practice/meetup corepack pnpm node scripts/ci.mjs
```

The actual generator code is `prepare()` in `scripts/helpers.mjs`; there is no per-exercise Jinja template or command that renders the maintained spec from TOML.

## Case Mapping

The displayed output dates below are derived from the exact zero-based month `Date` constructor arguments in the spec. The track CI run verifies each assertion against `.meta/proof.ci.js`.

| UUID                                   | Canonical `tests.toml` description | JavaScript assertion input            | Expected output and generated test                                                          |
| -------------------------------------- | ---------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------- |
| `d7f8eadd-d4fc-46ee-8a20-e97bd3fd01c8` | `monteenth of May 2013`            | `meetup(2013, 5, 'teenth', 'Monday')` | `new Date(2013, 4, 13)` = May 13, 2013; generated test `monteenth of May 2013`.             |
| `f78373d1-cd53-4a7f-9d37-e15bf8a456b4` | `monteenth of August 2013`         | `meetup(2013, 8, 'teenth', 'Monday')` | `new Date(2013, 7, 19)` = August 19, 2013; generated test `monteenth of August 2013`.       |
| `8c78bea7-a116-425b-9c6b-c9898266d92a` | `monteenth of September 2013`      | `meetup(2013, 9, 'teenth', 'Monday')` | `new Date(2013, 8, 16)` = September 16, 2013; generated test `monteenth of September 2013`. |

For all three, the reference scans days 13 through 19 for the requested weekday and returns `new Date(year, month - 1, meetupDay)`. The matching weekday dates are respectively 13, 19, and 16.

## Reproduction

Run the focused temporary-copy regeneration comparison:

```sh
python3 tools/course_checks/r53-t042.py
```

It creates two independent temporary repository copies, invokes the actual helper in each, saves both generated spec outputs under `work/R53-T042/`, compares them and the expected helper output, then runs the real `scripts/ci.mjs` entry point in each copy. No generated timestamp exists in `meetup.spec.js`, so no normalization is applied; comparison is byte-for-byte. The check fails for missing/extra cases, changed content, a failed child process, missing target output, or incomplete test execution.

Run the isolated package-script reference check:

```sh
python3 work/R53-T042/check.py
```

It resolves configured file paths from `.meta/config.json`, copies the complete exercise including hidden files, calls the track helper in a temporary repository, substitutes the reference only in the temporary exercise, and runs its configured `test` script with Jest watch mode disabled. It records test counts and named-case results and checks that the learner solution and maintained spec remain unchanged.

## Maintenance Notes

When canonical Meetup cases change, update UUID/description metadata with Configlet as appropriate and maintain the executable assertions in `meetup.spec.js` following the track's canonical-sync guidance. Do not infer input/output assertions from TOML descriptions alone, hand-edit the temporary generated copy, or change the learner stub to make reference tests pass. Re-run both checks after intentional updates.

`work/R53-T042/` is coursework evidence and must be excluded from any later upstream contribution branch.
