# R53-T035: Book Store `groupCost` cost

## Cost model

The exercise domain has five distinct book titles. A discount group can contain
one through five distinct titles, so the valid input domain for `groupCost` is
fixed and bounded. For this function, elapsed-time benchmarks would mostly
measure process startup and JIT warm-up rather than meaningful growth. The
source operation table below is the useful cost measurement instead.

`groupCost(size)` evaluates `size * BOOK_PRICE * DISCOUNTS[size - 1]`: one array
lookup and two numeric multiplications. That operation count is constant for
every valid group size; only the selected values and price change.

| Valid group size | Discount | Calculation | Cost in cents | Lookup / multiplies |
| ---: | ---: | --- | ---: | --- |
| 1 | 0% | `1 × 800 × 1` | 800 | 1 / 2 |
| 3 | 10% | `3 × 800 × 0.9` | 2160 | 1 / 2 |
| 5 | 25% | `5 × 800 × 0.75` | 3000 | 1 / 2 |

The exercise accepts arbitrary basket lengths, but `groupCost` receives the
size of one distinct-title group, always between one and five. Its cost is
therefore O(1) over this fixed domain. This statement describes `groupCost`,
not the recursive work of the full `cost` calculation.

## Maintained files

- Learner stub: `exercises/practice/book-store/book-store.js`.
- Reference: `exercises/practice/book-store/.meta/proof.ci.js`.
- Tests: `exercises/practice/book-store/book-store.spec.js`.
- Canonical cases: `exercises/practice/book-store/.meta/tests.toml`.
- File map: `exercises/practice/book-store/.meta/config.json`.

## Reproduction

Run `python3 work/R53-T035/check.py .`. It checks the fixed domain and cost
table, copies the exercise including dotfiles, runs every case against the
reference, and records the actual test count, hashes, and tool versions in
`evidence.json`. It does not benchmark `cost()` or make a speedup claim.
