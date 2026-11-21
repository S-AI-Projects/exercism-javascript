# Hints

## JavaScript: lowercase text

JavaScript's `String.prototype.toLowerCase()` converts letters using
Unicode-aware lowercase rules:

```js
'HELLO'.toLowerCase() // 'hello'
'İ'.toLowerCase() === 'i' // false
```

The second result is `false` because the lowercase form of `İ` contains an
additional combining dot character: `i` followed by U+0307. This exercise's
input is ASCII-only, so that Unicode case-mapping difference is outside the
input you need to handle.

See the
[MDN documentation for `toLowerCase()`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/toLowerCase).
