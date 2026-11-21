# R53-T036: Two Kindergarten Garden approaches

## Approaches and trade-off

The maintained reference parses each row, then eagerly builds a `plots` object
with four decoded plants per student. Its lookup is direct after construction.
The scratch alternative keeps the two encoded rows and sorted student names,
finds the requested student's alphabetical position in `plants(student)`, and
decodes only that student's four cups.

Both approaches return the same four plants in row order. For a partial garden
with one student, `RC\nGG` gives Alice radishes, clover, grass, grass. With the
different one-student garden `VC\nRC`, Alice gets violets, clover, radishes,
clover. For a two-student garden `VVCG\nVVRC`, Bob gets clover, grass,
radishes, clover.

The alternative stores the rows and student names rather than a per-student
`plots` map, so construction does less work and uses less derived storage when
only a few students are queried. Each query pays for a linear name lookup. The
maintained reference is clearer when many lookups are expected; the alternative
fits occasional lookups over a fixed small class. The alternative is isolated
in this task's scratch folder and does not replace the learner stub or
maintained reference.

## Maintained files

- Learner stub: `exercises/practice/kindergarten-garden/kindergarten-garden.js`.
- Maintained reference: `exercises/practice/kindergarten-garden/.meta/proof.ci.js`.
- Tests: `exercises/practice/kindergarten-garden/kindergarten-garden.spec.js`.
- Canonical cases: `exercises/practice/kindergarten-garden/.meta/tests.toml`.
- File map: `exercises/practice/kindergarten-garden/.meta/config.json`.

## Reproduction

Run `python3 work/R53-T036/check.py .`. It activates all test cases only in
temporary copies and runs the suite against both implementations. It reports
the number of cases and verifies that the learner file hash is unchanged.
