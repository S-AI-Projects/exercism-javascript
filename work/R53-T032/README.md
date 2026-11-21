# R53-T032: Twelve Days test source and reproduction

## Maintained source

This track has no per-exercise Jinja template for Twelve Days, and its exercise
package does not expose a test-generation command. The maintained test source is
`exercises/practice/twelve-days/twelve-days.spec.js`; canonical case metadata is
in `.meta/tests.toml`. The committed Jest file is the source of the executable
cases, rather than an artifact that can be regenerated from a local template.
The repository-level `scripts/test.mjs` and `scripts/ci.mjs` run tests; they do
not generate this spec file.

The checker takes two fresh copies of the exercise and compares their spec
sources byte for byte. This records the reproducible source snapshot without
pretending a generator exists. It also verifies that each canonical description
is represented by exactly one test name, activates skipped cases only in a
temporary copy, substitutes the maintained reference only there, and runs all
cases through the package's Jest script.

## Case route

The first three canonical cases route to these maintained tests:

| `tests.toml` description | Jest case |
| --- | --- |
| `first day a partridge in a pear tree` | `verse first day a partridge in a pear tree` |
| `second day two turtle doves` | `verse second day two turtle doves` |
| `third day three french hens` | `verse third day three french hens` |

The remaining verse cases and three range cases are checked by the same
description-to-title matching in `check.py`. The spec contains 15 cases total.

## Reproduction

From the repository root, run `python3 work/R53-T032/check.py .`. The check
records both source snapshot hashes, all case-name mappings, the executed test
count, and tool versions in `evidence.json`.
