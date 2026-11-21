# Luhn exercise file map

## What each file is for

- `luhn.js` is the learner's solution file. It is the file an Exercism student
  completes.
- `.meta/proof.ci.js` is the maintained reference implementation used to
  check that the exercise tests can pass. It is copied over the learner file
  only in a temporary test copy.
- `luhn.spec.js` is the JavaScript test source. Calls written as `test(...)`
  run normally; `xtest(...)` cases are skipped until a temporary checker
  enables them.
- `.meta/config.json` lists the solution, test, and example paths. The Luhn
  metadata checker verifies that each declared path stays inside this exercise
  and points to an existing file.
- `.meta/tests.toml` maps canonical test UUIDs to descriptions and inclusion
  information. Configlet can synchronize this metadata with canonical test
  data; it is not a JavaScript test generator, so it does not create
  `luhn.spec.js`.

The JavaScript spec is maintained alongside the canonical metadata. The
repository's `scripts/sync.mjs` prepares shared exercise setup files, including
the package and test-tool configuration. The metadata checker only validates
the paths listed in `.meta/config.json`; it does not edit generated or
maintained exercise files.

## Validation

From the repository root, run:

```sh
python3 tools/course_checks/r53-t018.py
python3 work/R53-T018/check.py
```

The first command validates the real Luhn metadata. The second also tries
temporary invalid metadata examples, then runs the full JavaScript test suite
against the reference implementation in a temporary copy. It leaves the
learner solution and maintained tests unchanged.
