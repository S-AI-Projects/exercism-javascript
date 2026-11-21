# Running the Forth exercise safely

The Forth course checker runs the exercise tests against the reference
implementation without changing the learner's `forth.js`. It reads the
solution, test, and reference paths from `.meta/config.json`, copies the whole
exercise (including hidden files) to a temporary directory, and replaces the
solution only in that copy.

The checker needs Python 3, Node.js, npm, and the repository's installed
dependencies (`node_modules`). From the repository root, run:

```sh
python3 tools/course_checks/r53-t019.py
```

Tests run through the exercise's existing `package.json` test script, with
watch mode disabled. The checker reports the number of tests actually run and
returns a failure status if no tests run, a test fails, or the test process
returns an error. Temporary files are cleaned up when the run finishes or is
interrupted.

To run the full validation, including checks for a deliberately failing
reference and an empty test selection, use:

```sh
python3 work/R53-T019/check.py
```

This validation also records SHA256 hashes of the learner solution before and
after each run. Inputs, results, and tool versions are saved in
`work/R53-T019/`.
