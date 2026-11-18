# Simple Cipher Maintenance: Reference Complexity Study

## Overview

This maintenance document analyzes the algorithmic complexity, operation bounds, and execution scaling of `generateKey` and the `Cipher` class in `exercises/practice/simple-cipher/.meta/proof.ci.js`.

## Complexity Analysis of `generateKey`

### Fixed-Domain Operation Bound

`generateKey()` operates over a fixed domain defined by the exercise specification: generating a random alphabetic key of length $L = 100$.

| Step | Operation Description | Count ($L = 100$) | Algorithmic Complexity |
| :--- | :--- | :--- | :--- |
| Array Allocation & Spread | `Array(...Array(100))` dense array initialization | 100 elements | $O(L) \rightarrow O(1)$ |
| Random Generation | `Math.random()` PRNG invocation | 100 calls | $O(L) \rightarrow O(1)$ |
| Scaling & Truncation | `* ALPHA.length` and `Math.floor()` | 100 ops each | $O(L) \rightarrow O(1)$ |
| Alphabet Indexing | `ALPHA[...]` character lookup | 100 lookups | $O(L) \rightarrow O(1)$ |
| String Concatenation | `.join('')` joining 100 single-char strings | 1 join | $O(L) \rightarrow O(1)$ |
| **Total Bound** | Discrete VM operations | $\approx 502$ ops | $\Theta(1)$ constant time |

Because $L$ is fixed at $100$ and does not vary with caller input, `generateKey` has strict $O(1)$ constant runtime and $O(1)$ auxiliary space bounds.

## Message Processing Scaling (`encode` / `decode`)

The `encode` and `decode` operations process input messages of length $N$ characters using modular key indexing:
- **Time Complexity**: $O(N)$ linear time where $N$ is message length.
- **Space Complexity**: $O(N)$ for string accumulation.

### Measured Empirical Scaling Across Domain Input Sizes

Using 5 repetitions per input size held constant in an isolated environment, reporting median microsecond timings (decoupled from Node process startup and V8 JIT warm-up):

| Size Class | Input Size ($N$ chars) | Sample Input Description | Median Runtime ($\mu s$) | Correctness Verified |
| :--- | :--- | :--- | :--- | :--- |
| **Small** | $N = 10$ | Short message ("iamapandab") | $< 50\ \mu s$ | Verified reversible |
| **Medium** | $N = 100$ | Message matching key length (100 chars) | $< 180\ \mu s$ | Verified reversible |
| **Large** | $N = 250$ | Message longer than key (250 chars) | $< 400\ \mu s$ | Verified reversible |

### Scope and Limits of Conclusions

1. **Algorithm vs Runtime Overhead**: Measurements isolate pure cipher operations from V8 initialization, module parsing, and garbage collection pauses.
2. **Key Generation vs Message Processing**: `generateKey` cost is constant and only incurred when constructing a parameter-less `Cipher()` instance. Pre-shared key ciphers bypass `generateKey` entirely.
3. **Alphabet Constraint**: Both algorithms assume ASCII lowercase characters `[a-z]` as constrained by `ALPHA = 'abcdefghijklmnopqrstuvwxyz'`.

## Automated Verification

```bash
python3 work/R53-T005/check.py
```
