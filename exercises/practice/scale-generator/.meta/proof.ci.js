/**
 * Algorithmic Complexity and Domain Invariants:
 *
 * 1. Algorithmic Work:
 *    - Constructor:
 *      * Normalizes tonic capitalization via `toTitleCase` (string length <= 2).
 *      * Determines accidental collection ('sharp' vs 'flat') by checking membership
 *        in `this.sharpStart` (array of 14 elements, at most 14 string comparisons).
 *      * Locates starting pitch index via `indexOf` in the 12-element pitch collection
 *        (at most 12 string comparisons).
 *      * Total constructor work is strictly bounded by a small constant (<= 30 operations).
 *    - Scale Generation (`generateScale`):
 *      * Given an interval pattern of length `m`, splits the string into `m` characters.
 *      * Iterates `m` times across interval characters:
 *        - Dictionary lookup in `this.steps` ({ m: 1, M: 2, A: 3 }).
 *        - Cumulative integer addition: `this.index += step`.
 *        - Modular reduction modulo 12: `(this.index) % 12`.
 *        - Array element access in `this.accidental` array.
 *      * Concatenates the initial tonic note with the `m` mapped pitches into an array
 *        of `m + 1` note strings.
 *    - Chromatic Scale (`chromatic`):
 *      * Delegates to `generateScale('mmmmmmmmmmm')` with fixed `m = 11`.
 *
 * 2. Invariants:
 *    - Modular Pitch-Space Invariant:
 *      Western 12-tone equal temperament (12-TET) forms the cyclic group Z_12.
 *      For any tonic index k_0 in [0, 11] and step sequence i_0, ..., i_{m-1}, the pitch
 *      index after step t is given by `(k_0 + \sum_{j=0}^t steps[i_j]) mod 12`.
 *      The modulo 12 operation guarantees that every computed pitch index is strictly
 *      in the range [0, 11], corresponding to a valid note in the selected 12-pitch array.
 *    - Scale Length Invariant:
 *      An interval sequence containing `m` interval steps produces an ordered array
 *      containing exactly `m + 1` notes starting with the canonical tonic note.
 *
 * 3. Complexity:
 *    - Parameterized Complexity (by interval sequence length `m`):
 *      * Time Complexity: O(m). For an interval string of length `m`, the algorithm
 *        performs O(1) initialization and exactly `m` iterations of constant-time step
 *        mappings, modular additions, and array indexing operations.
 *      * Auxiliary Space Complexity: O(m) to store the split character array and the
 *        resulting array of `m + 1` pitch names.
 *    - Fixed-Domain Complexity:
 *      * Under Western music theory and the exercise specification, valid scales span an
 *        octave (summing to 12 semitones). Supported interval sequences in the specification
 *        have lengths m in {5, 6, 7, 8, 11} (pentatonic m=5, hexatonic m=6, heptatonic/diatonic
 *        m=7, octatonic m=8, chromatic m=11).
 *      * Because `m <= 11` and the tonic is drawn from a finite set of 26 valid representations,
 *        the total operation count is strictly bounded by a defensible upper bound of <= 90
 *        elementary operations.
 *      * Therefore, over the valid exercise domain, the algorithmic time complexity is O(1)
 *        and auxiliary space complexity is O(1).
 *
 * 4. Fixed-Domain Limitations:
 *    - The implementation assumes standard Western 12-TET musical scales.
 *    - Supported tonics are restricted to canonical keys (26 distinct representations).
 *    - Interval characters are restricted to 'm' (half step = 1), 'M' (whole step = 2),
 *      and 'A' (augmented second = 3). Non-octave, microtonal, or arbitrary inputs fall
 *      outside the exercise domain.
 *    - No arbitrary micro-optimization or engine-specific speedup is claimed; efficiency
 *      derives entirely from domain boundedness and constant-time modular arithmetic.
 */
export class Scale {
  constructor(tonic) {
    this.tonic = tonic;
    this.notes = {
      sharp: ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#'],
      flat: ['A', 'Bb', 'B', 'C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab'],
    };
    this.sharpStart = [
      'G',
      'D',
      'A',
      'E',
      'B',
      'F#',
      'e',
      'b',
      'f#',
      'c#',
      'g#',
      'd#',
      'C',
      'a',
    ];
    this.accidental =
      this.notes[this.sharpStart.includes(this.tonic) ? 'sharp' : 'flat'];
    this.index = this.accidental.indexOf(this.toTitleCase(this.tonic));
    this.steps = { m: 1, M: 2, A: 3 };
  }

  toTitleCase(str) {
    return str.charAt(0).toUpperCase() + str.substring(1);
  }

  generateScale(intervals) {
    return [this.accidental[this.index]].concat(
      intervals
        .split('')
        .map((i) => this.accidental[(this.index += this.steps[i]) % 12]),
    );
  }

  chromatic() {
    return this.generateScale('mmmmmmmmmmm');
  }

  interval(intervals) {
    return this.generateScale(intervals);
  }
}
