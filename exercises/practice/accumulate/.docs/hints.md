# Hints

## What the examples require

The exercise asks for a new collection containing the result of applying the
given operation to each input element. These examples show what that means:

| Input | Operation | Expected result |
| --- | --- | --- |
| `[]` | `x => x * x` | `[]` |
| `[1, 2, 3]` | `number => number * number` | `[1, 4, 9]` |
| `['hello', 'world']` | `word => word.toUpperCase()` | `['HELLO', 'WORLD']` |

An empty input has no elements to transform, so the result is empty. Squaring
the numbers applies the operation to each number: `1 * 1`, `2 * 2`, and
`3 * 3`. Uppercasing applies the operation to each word, changing `hello` to
`HELLO` and `world` to `WORLD`.

The instructions and tests specify these results and the operation on
collection elements. They do not specify extra rules for invalid inputs,
conversion between types, or errors from an operation, so do not assume
additional behavior for those cases.
