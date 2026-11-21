# Perfect-numbers divisor-boundary regression

## Mutation

The reference implementation's `getDivisors()` loop includes candidates through half of the input:

```js
i <= number / 2
```

The deliberate mutation changes that condition to `i < number / 2`. For an even input, this skips the proper divisor equal to half the input.

## Existing test that detects it

| Test UUID | Test name | Input | Expected result |
| --- | --- | ---: | --- |
| `163e8e86-7bfd-4ee2-bd68-d083dc3381a3` | `Smallest perfect number is classified correctly` | `6` | `perfect` |

For `6`, the proper divisors are `1`, `2`, and `3`, whose sum is `6`. The mutation omits `3`, leaving a sum of `3`, so it classifies `6` as `deficient` instead. This contradicts the instructions' definition: a perfect number equals the sum of its proper divisors.

Inputs `1` through `5` have the same classifications with and without this mutation. Therefore, `6` is the smallest positive input that exposes the classification error. The verification script checks this by comparing both implementations on the same inputs.

The mutation is applied only to a temporary copy of the reference. The learner solution, maintained reference, and test file are not changed.
