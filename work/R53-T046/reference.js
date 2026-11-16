/**
 * Maintained Reference Implementation for 'Eliud's Eggs'.
 *
 * Approach: Binary String Conversion & Array Reduction
 * Data Representation: Text string of binary digits ('0' and '1') spread into an Array.
 * Control Flow: Declarative functional higher-order reduction.
 */
export const eggCount = (displayValue) =>
  [...displayValue.toString(2)].reduce(
    (acc, curr) => (curr === '1' ? (acc += 1) : acc),
    0,
  );

