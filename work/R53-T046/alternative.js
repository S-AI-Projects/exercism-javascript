/**
 * Alternative Implementation for 'Eliud's Eggs'.
 *
 * Approach: Direct 32-bit Integer Bitwise Manipulation & Iterative Shift
 * Data Representation: Primitive numeric 32-bit unsigned integer (no heap allocation).
 * Control Flow: Imperative while-loop testing least-significant bit and logical right-shifting.
 */
export const eggCount = (displayValue) => {
  let count = 0;
  let remaining = displayValue;

  while (remaining > 0) {
    count += remaining & 1;
    remaining >>>= 1;
  }

  return count;
};

