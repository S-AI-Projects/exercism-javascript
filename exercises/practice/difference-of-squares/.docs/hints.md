# Hints

## General

- The `Squares` class calculates the square of the sum, the sum of the squares, and the difference between them for the first `N` natural numbers.
- In JavaScript, properties `squareOfSum`, `sumOfSquares`, and `difference` are accessed as getters (`get`), meaning they are evaluated like properties (e.g., `squares.squareOfSum`) rather than invoked as functions (`squares.squareOfSum()`).

## Language-Specific Guidance: Numeric Type Coercion in Accumulations

The `Squares` implementation relies fundamentally on JavaScript numeric addition and exponentiation.

### Construct: Numeric Addition and Exponentiation

When accumulating the series of numbers from `1` to `N`, JavaScript uses the `+` operator, which is overloaded for both numeric addition and string concatenation.

```javascript
// Valid Numeric Accumulation:
let numericSum = 0;
for (let x = 1; x <= 5; x += 1) {
  numericSum += x;
}
const squareOfSum = numericSum * numericSum;
console.log(squareOfSum); // Output: 225
```

### Exercise-Relevant Pitfall: Implicit String Coercion

If the initial accumulator is unintentionally initialized as a string (`""` or `"0"`) or if values are parsed without explicit conversion, JavaScript coerces the operation to string concatenation rather than numeric addition:

```javascript
// Coercion Pitfall:
let stringSum = "";
for (let x = 1; x <= 5; x += 1) {
  stringSum += x;
}
console.log(stringSum); // Output: "12345" (string concatenation, not 15)
const brokenSquare = stringSum * stringSum; // 152399025 instead of 225
```

### Reference Documentation
- [MDN Web Docs: Addition operator (+)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Addition)
- [MDN Web Docs: Getter syntax](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Functions/get)
