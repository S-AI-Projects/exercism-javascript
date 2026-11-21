# R53-T033: Leap-year mutation check

## Contract and diagnostic input

The Gregorian leap-year rule makes a year divisible by four a leap year, except
century years, which are common years unless also divisible by 400. The
maintained reference implements that contract. A deliberate mutant that accepts
every year divisible by four drops the century exception.

The current suite already rejects that mutant at 1800, its smallest century
input that is not divisible by 400. The smallest positive century input allowed
by the contract is 100, so the checker also appends a diagnostic test for
`isLeap(100) === false` to a temporary spec copy. This proposed case makes the
boundary explicit without changing canonical exercise tests or claiming that
the maintained reference is defective. The mutant returns `true` for 100 and
must fail this diagnostic assertion.

The three initial baseline cases are 2015 → false, 1970 → false, and 1996 →
true. The full maintained suite is also run in the isolated copy.

## Maintained files

- Learner stub: `exercises/practice/leap/leap.js`.
- Reference example: `exercises/practice/leap/.meta/proof.ci.js`.
- Test source: `exercises/practice/leap/leap.spec.js`.
- Canonical cases: `exercises/practice/leap/.meta/tests.toml`.
- File map: `exercises/practice/leap/.meta/config.json`.

## Reproduction

Run `python3 work/R53-T033/check.py .` from the repository root. The checker
copies the exercise including dotfiles, activates skipped cases in the copy,
substitutes the reference only there, adds the diagnostic test only to that
copy, and runs the package test script with watch mode disabled. It then swaps
in the mutant and verifies that the diagnostic assertion rejects it. Results
and tool versions are written to `evidence.json`.
