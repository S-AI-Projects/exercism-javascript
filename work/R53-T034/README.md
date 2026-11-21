# R53-T034: Clarify Series window construction

## Readability change

`slices` previously maintained a result array and a second mutable array, then
reset that second array after each window. The reference now names the number
of windows (`sliceCount`) and uses each start position to take one contiguous
range from the digits. The range length and order are visible in one expression,
so there is no separate push/reset state to trace.

For the named cases, the windows are:

| Input | Length | Output |
| --- | ---: | --- |
| `1` | 1 | `[[1]]` |
| `12` | 1 | `[[1], [2]]` |
| `35` | 2 | `[[3, 5]]` |

The alternate representation allocates one output array per window with
`slice()`. Those arrays are required in the returned result either way; the
change removes mutable bookkeeping without changing the public interface,
ordering, validation, or error messages.

## Maintained files

- Learner stub: `exercises/practice/series/series.js`.
- Reference: `exercises/practice/series/.meta/proof.ci.js`.
- Tests: `exercises/practice/series/series.spec.js`.
- Canonical case metadata: `exercises/practice/series/.meta/tests.toml`.
- File map: `exercises/practice/series/.meta/config.json`.

## Reproduction

Run `python3 work/R53-T034/check.py .`. It validates the three named input and
output assertions, installs the reference in isolated copies, activates all
skipped tests there, and runs the exercise test script with watch mode disabled.
It records the executed case count and hashes of the learner stub before and
after.
