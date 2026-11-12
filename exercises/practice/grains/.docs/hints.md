# Hints

## JavaScript-Specific Guidance: `BigInt` Coercion and Arbitrary-Precision Arithmetic

### Why `BigInt` Is Required
JavaScript `Number` values use IEEE-754 64-bit floating-point representation and can only represent integers accurately up to `Number.MAX_SAFE_INTEGER` (`9007199254740991`, or $2^{53} - 1$). On a 64-square chessboard, square 64 holds $2^{63}$ grains and the total across all squares is $2^{64} - 1$, both of which exceed safe `Number` precision.

To avoid precision loss, `square` converts numeric operands using `BigInt(...)` so exponentiation (`**`) runs in arbitrary-precision `bigint` arithmetic and returns a `BigInt` (which the tests verify via `.toString()`).

### Micro-Example
Convert both the base and exponent to `BigInt` before exponentiation:

```js
const exact = (BigInt(2) ** BigInt(63)).toString();
// => '9223372036854775808'
```

### Common Pitfall: `Number` Precision Loss and Mixed-Type `TypeError`
1. **Silent rounding with `Number`:** Computing powers of two with standard `Number` values silently rounds integers above $2^{53} - 1$:
   ```js
   const imprecise = (2 ** 63).toString();
   // => '9223372036854776000' (inaccurate beyond Number.MAX_SAFE_INTEGER)
   ```
2. **Mixing `BigInt` and `Number`:** JavaScript does not implicitly coerce `Number` to `BigInt` in binary operators. Evaluating `BigInt(2) ** 63` throws `TypeError: Cannot mix BigInt and other types, use explicit conversions`.

### Language Reference
- [MDN: `BigInt`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/BigInt)
- [MDN: `Number.MAX_SAFE_INTEGER`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER)
