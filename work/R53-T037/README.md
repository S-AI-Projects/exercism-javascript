# R53-T037: JavaScript Unicode guidance for Micro-blog

## Chosen construct

The maintained `truncate` reference uses `Intl.Segmenter` to divide the
coerced input into grapheme clusters before taking five. This is the Unicode
string behavior that matters to the exercise: JavaScript string length and
`Array.from` do not count user-perceived graphemes. The new exercise hint
explains the distinction with a combining-accent example and a contrasting
code-point result.

For `e\u0301bcdef`, grapheme truncation returns `e\u0301bcde` (five visible
characters). Code-point truncation returns `e\u0301bcd`; the first five code
points represent only four graphemes. The standalone example asserts both
outputs. It does not implement the whole exercise.

## Maintained files

- Learner stub: `exercises/practice/micro-blog/micro-blog.js`.
- Reference: `exercises/practice/micro-blog/.meta/proof.ci.js`.
- Tests: `exercises/practice/micro-blog/micro-blog.spec.js`.
- Canonical cases: `exercises/practice/micro-blog/.meta/tests.toml`.
- File map: `exercises/practice/micro-blog/.meta/config.json`.
- JavaScript-specific hint: `exercises/practice/micro-blog/.docs/instructions.md`.

## Reproduction

Run `python3 work/R53-T037/check.py .`. It asserts both example outputs,
activates all exercise cases in a temporary copy, substitutes the reference
only there, runs the package test script with watch mode disabled, and records
the test count, tool versions, and unchanged learner hash in `evidence.json`.
