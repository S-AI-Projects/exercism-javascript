const ALPHA = 'abcdefghijklmnopqrstuvwxyz';

/**
 * Generates a pseudo-random substitution cipher key of fixed length 100.
 *
 * Complexity and Invariant:
 * - Domain Bound: Fixed-length key generation (L = 100 characters from [a-z]).
 * - Time Complexity: O(1) constant time with respect to message inputs; O(L) with fixed L = 100.
 *   Consists of exactly:
 *     - 100 array element allocations and spreads
 *     - 100 Math.random() PRNG invocations
 *     - 100 floating-point multiplications and Math.floor() operations
 *     - 100 character lookups and 1 join() string concatenation.
 * - Space Complexity: O(1) auxiliary space (O(L) with L = 100, exactly 100 bytes + string metadata).
 * - Algorithmic Work: Decoupled from process startup / compilation time.
 */
function generateKey() {
  return Array(...Array(100))
    .map(() => ALPHA[Math.floor(Math.random() * ALPHA.length)])
    .join('');
}

const mod = (n, m) => ((n % m) + m) % m;

function xCode(key, inText, sign) {
  return [...inText].reduce((outText, letter, ii) => {
    const offset = sign * ALPHA.indexOf(key[mod(ii, key.length)]);
    return outText + ALPHA[mod(ALPHA.indexOf(letter) + offset, ALPHA.length)];
  }, '');
}

export class Cipher {
  constructor(key) {
    if (typeof key === 'undefined') {
      this.key = generateKey();
    } else if (key.length === 0 || key.match(/[^a-z]/, 'g')) {
      throw new Error('Bad key');
    } else {
      this.key = key;
    }
  }

  encode(plainText) {
    return xCode(this.key, plainText, 1);
  }

  decode(encodedText) {
    return xCode(this.key, encodedText, -1);
  }
}
