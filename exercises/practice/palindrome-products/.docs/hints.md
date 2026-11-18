# Hints

## General

- The Palindrome Products exercise requires finding the smallest and largest palindromic products within a factor range `[minFactor, maxFactor]`, along with all valid factor pairs `[p, q]` (where `p <= q`) that produce them.
- Be sure to validate that `minFactor <= maxFactor`, throwing an Error with message `'min must be <= max'` if violated.

## Approach Selection: Product-Space Search vs. Factor-Pair Generation

Two distinct algorithmic paradigms can be used to solve this problem:

### Approach 1: Outer Product-Space Search with Factorization (Reference Approach)
- **Mechanism**: Iterates through possible numerical values from the extremities (from `maxFactor^2` downwards for largest, and `minFactor^2` upwards for smallest). For each candidate number that is a palindrome, tests if it can be factored into two integers within `[minFactor, maxFactor]`.
- **Advantages**: Terminates as soon as the first valid palindrome product is encountered; extremely fast when palindromes are near the boundaries.
- **Trade-offs**: Requires trial division factorization for every palindromic candidate and examines non-product integers.

### Approach 2: Factor-Pair Iteration with Extreme-Value Tracking (Alternative Approach)
- **Mechanism**: Iterates over all valid factor pairs `(i, j)` where `minFactor <= i <= maxFactor` and `i <= j <= maxFactor`. For each pair, calculates product `val = i * j`. If `val` is a palindrome, updates tracked `smallest` and `largest` records.
- **Advantages**: Evaluates only genuinely reachable products; factor pairs are known directly without trial division.
- **Trade-offs**: Evaluates $O(F^2)$ factor combinations where $F = \text{maxFactor} - \text{minFactor} + 1$, which can be slower for very wide factor ranges.

### Worked Example (Single-Digit Factors: min = 1, max = 9)

1. **Smallest Palindrome**:
   - Smallest product: $1 \times 1 = 1$.
   - $1$ is a single-digit palindrome.
   - Result: `{ value: 1, factors: [[1, 1]] }`.
2. **Largest Palindrome**:
   - Product $9 \times 9 = 81$ (not palindrome).
   - Evaluating pairs $(9, 9), (9, 8)=72, \dots, (9, 1)=9$.
   - The largest palindromic product formed is $9$, achieved by factor pairs `[[1, 9], [3, 3]]`.
   - Result: `{ value: 9, factors: [[1, 9], [3, 3]] }`.
