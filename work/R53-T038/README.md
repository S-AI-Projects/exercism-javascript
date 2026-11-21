# R53-T038: Pangram maintained file map

## File map and maintenance status

`exercises/practice/pangram/.meta/config.json` declares three file roles:

| Role | Declared path | Purpose |
| --- | --- | --- |
| `solution` | `pangram.js` | Learner stub |
| `test` | `pangram.spec.js` | Jest cases, including the three selected cases |
| `example` | `.meta/proof.ci.js` | Maintained reference implementation |

There is no `editor` key in the current `files` object. The exercise's Babel,
Jest, and ESLint configuration files are local to the exercise directory; they
are not solution/test/example file roles in Exercism's map. The checker validates
every path that is actually declared and does not guess extra roles.

The runner reads `files.test` and executes `pangram.spec.js`; it reads
`files.example` and substitutes `proof.ci.js` for `files.solution` in a
temporary copy. The working learner stub is never overwritten. The spec is the
maintained Jest source. `.meta/tests.toml` is generated canonical metadata (its
header documents `configlet sync`), and it is not the source from which this
track creates the JavaScript spec.

The metadata checker also uses three temporary invalid fixtures: missing
reference, missing test, and a `../` path that escapes the exercise. Each must
be rejected for the corresponding path reason.

## Reproduction

Run `python3 work/R53-T038/check.py .` from the repository root. It validates
the real map and all invalid fixtures, then runs the complete reference suite
with watch mode disabled and records test counts and tool versions in
`evidence.json`.
