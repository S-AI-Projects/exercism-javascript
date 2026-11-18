/**
 * Calculate the sum of all unique multiples of particular factors up to,
 * but not including, the limit.
 *
 * Invariant:
 * Only positive factors (> 0) generate valid positive multiples in [1, limit).
 * A factor of 0 has no positive multiples and does not contribute to the sum.
 * Each candidate integer is accumulated at most once, satisfying set-union semantics.
 */
export const sum = (factors, limit) => {
  const isMultipleOfAny = (candidate) =>
    factors.some((factor) => factor > 0 && candidate % factor === 0);

  let totalSum = 0;
  for (let candidate = 1; candidate < limit; candidate += 1) {
    if (isMultipleOfAny(candidate)) {
      totalSum += candidate;
    }
  }

  return totalSum;
};
