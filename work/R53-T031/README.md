# R53-T031: Markdown canonical case rationale

## Contract and selected cases

Markdown headings in this exercise use one through six leading `#` characters. The
canonical case `6dca5d10-5c22-4e2a-ac2b-bd6f21e61939` is named “with h7 header
level”, so it asks for behavior outside that contract and remains excluded. Its
replacement, `81c0c4db-435e-4d77-860d-45afacdad810` (“h7 header level is a
paragraph”), records the supported fallback for the same boundary input. No
canonical include value is changed.

In the JavaScript reference, the heading expression recognizes one to seven
hashes, but the callback emits a heading only through level six. Seven hashes
therefore take the paragraph fallback and preserve the original hashes. This
implementation detail explains the replacement case; it does not expand the
exercise contract to require an h7 heading.

The diagnostic input is `####### Boundary`. Its expected output is
`<p>####### Boundary</p>`. A deliberately incorrect h7-emitting reference should
fail that assertion, demonstrating that the existing replacement test protects
the boundary.

## Maintained files

- Learner stub: `exercises/practice/markdown/markdown.js`.
- Reference example: `exercises/practice/markdown/.meta/proof.ci.js`.
- Test source: `exercises/practice/markdown/markdown.spec.js`.
- Canonical case metadata: `exercises/practice/markdown/.meta/tests.toml`.
- Metadata file map: `exercises/practice/markdown/.meta/config.json`.

`config.json` maps `solution` to `markdown.js`, `test` to `markdown.spec.js`,
and `example` to `.meta/proof.ci.js`; all three resolve beneath the exercise
directory. The maintenance checker copies this exercise, activates skipped
cases only in that temporary copy, substitutes the reference there, and runs
the exercise's `test` package script with Jest watch mode disabled.

## Reproduction

From the repository root, run:

```sh
python3 work/R53-T031/check.py .
```

The checker validates the metadata and rationale, runs all exercise cases with
the maintained reference, and verifies that a targeted incorrect reference is
rejected. It records command output, executed test counts, and tool versions in
`evidence.json`.
