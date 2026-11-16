# Hints

## General

- The flower field is represented as an array of strings (or a 2D array of characters).
- To count adjacent flowers, you need to check up to 8 surrounding neighbor positions for each empty square: horizontally, vertically, and diagonally.
- Edge and corner squares have fewer neighbors because some surrounding positions lie outside the grid.

## Array Bracket Notation and Out-of-Bounds Guards

When checking adjacent squares in a grid, you must avoid trying to access positions outside the board.

### The Language Construct: Bracket Notation (`array[index]`)

In JavaScript, array elements are accessed using [bracket notation property accessors](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Property_accessors).

Unlike many other programming languages, JavaScript does not throw an "index out of range" error when you access an array with an invalid index (such as `-1` or an index $\ge$ `array.length`). Instead, it evaluates to `undefined`.

In JavaScript, `undefined` is [falsy](https://developer.mozilla.org/en-US/docs/Glossary/Falsy), whereas existing array rows (objects) are [truthy](https://developer.mozilla.org/en-US/docs/Glossary/Truthy).

### Standalone Example

Consider a small 2D array:

```javascript
const grid = [
  ['A', 'B'],
  ['C', 'D'],
];

// Valid row index returns the row array (truthy):
Boolean(grid[0]);
// => true

// Out-of-bounds row index safely evaluates to undefined (falsy) without throwing:
Boolean(grid[-1]);
// => false
```

### Common Pitfall: Chaining Property Accessors

A common pitfall occurs when directly chaining row and column access on a 2D grid:

```javascript
// Valid in-bounds access:
grid[0][0];
// => "A"

// Out-of-bounds row chained access:
grid[-1][0];
// => Uncaught TypeError: Cannot read properties of undefined (reading '0')
```

### Why the Results Differ

- `grid[-1]` evaluates to `undefined`. Accessing an absent property on an object or array is valid JavaScript and safely returns `undefined`.
- `grid[-1][0]` attempts to evaluate `(undefined)[0]`. Because `undefined` is a primitive value with no properties, attempting to read a property from it immediately throws a `TypeError`.

### Relevance to Checking Adjacent Squares

When checking neighbor squares, row offsets like `-1` (above the top row) or `+1` (below the bottom row) can fall outside the board.

By checking whether the row `board[row]` exists first (as a truthy guard), you prevent JavaScript from attempting to read column properties from `undefined`, safely filtering out positions that lie off the board.

