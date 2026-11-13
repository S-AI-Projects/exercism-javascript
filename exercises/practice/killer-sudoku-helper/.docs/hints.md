# Hints

## Contract Walkthrough & Subtle Cases

### JavaScript Input/Output Representation
- **Input (`cage` object):** `{ sum, size, exclude }` where `sum` is the target cage total, `size` is the exact number of distinct digits (`1`–`9`) in the cage, and `exclude` is an array of disallowed digits.
- **Output (`number[][]`):** Always a 2D array of combinations, even for single-cell cages (`size: 1`) where only one digit fits (`[[1]]`, not `[1]` or `1`).
- **Ordering requirement:** Combinations are sorted—each inner array lists digits in ascending order and the outer array is ordered lexicographically.

### Walkthrough of Trivial 1-Digit Cages (`1`, `2`, `3`)
| Test Case | Input (`{ sum, size, exclude }`) | Candidate Digits | Required Output | Why |
| :--- | :--- | :--- | :--- | :--- |
| `'1'` | `{ sum: 1, size: 1, exclude: [] }` | `[1..9]` | `[[1]]` | Only `[1]` has length `1` and sums to `1`. |
| `'2'` | `{ sum: 2, size: 1, exclude: [] }` | `[1..9]` | `[[2]]` | Digits cannot repeat; `size: 1` requires a 1-element tuple `[2]`. |
| `'3'` | `{ sum: 3, size: 1, exclude: [] }` | `[1..9]` | `[[3]]` | `[1, 2]` sums to `3` but has `size: 2`, leaving only `[[3]]`. |

### Specified vs. Outside-Contract Behavior
- **Specified:** Distinct digits `1..9`, exact `size` and `sum`, filtering `exclude`, returning `[]` when none match, and sorted `number[][]` output.
- **Outside the contract (unspecified):** Custom errors, string-to-number coercion, or missing `exclude` defaults for malformed inputs outside valid Sudoku cages (`sum` `1..45`, `size` `1..9`).
