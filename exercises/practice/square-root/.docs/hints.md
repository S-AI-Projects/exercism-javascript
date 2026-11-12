# Hints

## Choosing an Implementation Approach

Because every test input is a positive integer with an exact whole-number square root, two distinct algorithmic representations work well without calling `Math.sqrt`:

1. **Binary Search over Candidate Roots (Interval Representation)**
   - **Representation:** Maintain a closed search interval `[low, high]` initialized to `[1, radicand]` representing possible integer roots.
   - **Control flow:** On each step, test the midpoint `mid = Math.floor((low + high) / 2)` by comparing `mid * mid` against `radicand`, narrowing either `low = mid + 1` or `high = mid - 1` until `mid * mid === radicand`.
   - **Worked example (`radicand = 25`):**
     - Start `[1, 25]` -> `mid = 13` (`13 * 13 = 169 > 25` -> narrow to `[1, 12]`)
     - `[1, 12]` -> `mid = 6` (`6 * 6 = 36 > 25` -> narrow to `[1, 5]`)
     - `[1, 5]` -> `mid = 3` (`3 * 3 = 9 < 25` -> narrow to `[4, 5]`)
     - `[4, 5]` -> `mid = 4` (`4 * 4 = 16 < 25` -> narrow to `[5, 5]`)
     - `[5, 5]` -> `mid = 5` (`5 * 5 = 25 === 25` -> return `5`)

2. **Digit-by-Digit Base-2 Bitwise Method (Remainder & Bit-Mask Representation)**
   - **Representation:** Track the unconsumed remainder `n`, an accumulating root `result`, and a power-of-four bit mask `bit` aligned to the highest bit pair of `radicand`.
   - **Control flow:** Subtract `result + bit` whenever `n >= result + bit` and shift `bit >>= 2` each step.

### Trade-Offs
- **Clarity & range:** Interval binary search is easier to read and works across large integers without hardcoding an initial bit-shift ceiling (such as `1 << 14`, which caps inputs at `65535`).
- **Arithmetic work & overflow:** Binary search performs a multiplication (`mid * mid`) on every step (which can overflow `Number.MAX_SAFE_INTEGER` for very large inputs unless written as `mid <= Math.floor(radicand / mid)`), whereas the bitwise method uses only addition, subtraction, and bit shifts. Both use $O(1)$ extra memory and $O(\log N)$ steps.
