# R53-T040: Binary place-value cases

## Decision table

| Input condition | Place values | Required result |
| --- | --- | ---: |
| `0` | `0 × 2⁰` | 0 |
| `1` | `1 × 2⁰` | 1 |
| `10` | `1 × 2¹ + 0 × 2⁰` | 2 |

The exercise specifies conversion of binary digit strings using powers of two.
Its listed invalid digit examples return `null`. Inputs outside the stated
contract are left unspecified here; no additional coercion, validation, or
ordering rule is inferred.

## Maintained files

- Learner stub: `exercises/practice/binary/binary.js`.
- Reference: `exercises/practice/binary/.meta/proof.ci.js`.
- Tests: `exercises/practice/binary/binary.spec.js`.
- Canonical cases: `exercises/practice/binary/.meta/tests.toml`.
- File map: `exercises/practice/binary/.meta/config.json`.

## Reproduction

Run `python3 work/R53-T040/check.py .`. The check validates the named input and
expected-result assertions, copies the exercise including dotfiles, substitutes
the reference in the copy, enables skipped tests there, and runs the package
test script with watch mode disabled. It reports the executed Jest case count
and records tool versions and the unchanged learner hash in `evidence.json`.
