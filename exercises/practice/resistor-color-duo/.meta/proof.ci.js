// resistor-color solution START
const COLORS = [
  'black',
  'brown',
  'red',
  'orange',
  'yellow',
  'green',
  'blue',
  'violet',
  'grey',
  'white',
];

// Complexity & invariant: COLORS has a fixed domain of 10 resistor bands (indices 0..9).
// colorCode scans at most 10 entries (1..10 string comparisons, O(1) bounded).
// decodedValue destructures only the first two bands ([tens, ones]), executing colorCode
// exactly twice (2..20 total comparisons) regardless of extra trailing bands.
const colorCode = (color) => COLORS.indexOf(color);
// resistor-color solution END

export const decodedValue = ([tens, ones]) =>
  colorCode(tens) * 10 + colorCode(ones);
