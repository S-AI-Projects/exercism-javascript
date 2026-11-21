# R53-T039: Safe Satellite reference runner

## Safety and run modes

`check.py` resolves the learner solution, test source, and reference from the
exercise's `files` map. Each mode copies the whole exercise with dotfiles into
a temporary directory, substitutes the reference only in that copy, disables
watch mode, and uses Jest's JSON report to count executed tests. Temporary
directories are removed by the context manager, including on failure.

The checker runs three modes:

1. The real reference must pass all enabled spec cases.
2. A deliberately throwing reference must produce a failing assertion and a
   nonzero Jest exit.
3. A spec with all tests skipped must be rejected as a zero-executed-test run,
   even if Jest itself regards the all-skipped suite as a successful process.

Before and after every mode, the original learner file's SHA-256 is compared.
The final evidence records all three pairs of hashes and the observed child
exit codes and test counts.

## Maintained files

- Learner stub: `exercises/practice/satellite/satellite.js`.
- Reference: `exercises/practice/satellite/.meta/proof.ci.js`.
- Tests: `exercises/practice/satellite/satellite.spec.js`.
- Canonical cases: `exercises/practice/satellite/.meta/tests.toml`.
- File map: `exercises/practice/satellite/.meta/config.json`.

## Reproduction

Run `python3 work/R53-T039/check.py .` from the repository root. The check
reports the executed count for each scenario and fails if the real reference
does not pass, the failing reference is accepted, or the empty selection is
treated as success.
