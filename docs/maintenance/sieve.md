# Sieve Canonical Test Rationale

This note records how the JavaScript Sieve tests correspond to the canonical test cases and why the current test selection is preserved. The instructions specify prime output through the inclusive limit; they do not require a particular algorithm. The reference implementation is in `exercises/practice/sieve/.meta/proof.ci.js`.

| UUID                                   | Canonical description  | JavaScript test           | Current selection  | Coverage and rationale                                                                                                                                         |
| -------------------------------------- | ---------------------- | ------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `88529125-c4ce-43cc-bb36-1eb4ddd7b44f` | no primes under two    | `no primes under two`     | Included           | `primes(1)` returns `[]` through the reference's `n <= 1` boundary.                                                                                            |
| `4afe9474-c705-4477-9923-840e1024cc2b` | find first prime       | `finds first prime`       | Excluded (`xtest`) | `primes(2)` expects `[2]`; it covers the first `possibilities.shift()` and `primes.push()`. No active test asserts this input.                                 |
| `974945d8-8cd9-4f00-9463-7d813c7f17b7` | find primes up to 10   | `finds primes up to 10`   | Excluded (`xtest`) | `primes(10)` expects `[2, 3, 5, 7]`; it exercises repeated shifts, pushes, and `possibilities.filter(indivisibleBy, prime)`. No active test covers this range. |
| `2e2417b7-3f3a-452a-8594-b9af08af6d82` | limit is prime         | `limit is prime`          | Excluded (`xtest`) | `primes(13)` expects the inclusive limit 13; `possibilities.shift()` selects it and `primes.push()` retains it. No active test checks a prime upper limit.     |
| `92102a05-4c7c-47de-9ed0-b7d5fcd00f21` | find primes up to 1000 | `finds primes up to 1000` | Excluded (`xtest`) | Checks the full result through 1000 using repeated shifts, pushes, and `possibilities.filter(indivisibleBy, prime)`; no active test covers this range.         |

## Selection Details

Before and after this rationale update, the JavaScript suite has **1 included** and **4 excluded** canonical cases. The metadata has descriptions and rationale comments, but no per-case include booleans. Selection is represented by `test(...)` versus `xtest(...)` in `sieve.spec.js`; `.meta/config.json` also sets `flag.tests.includes-optional` to `false`.

The exclusions are the existing optional-test selection, not a JavaScript language limitation. The repository's `scripts/helpers.mjs` reference-test preparation explicitly changes `xtest` to `test` in its temporary copy. The maintenance checker applies that same approach only to an isolated copy, leaving the learner solution and canonical test state unchanged. There is no equivalent currently active JavaScript assertion for the four excluded inputs; the reference verification runs all five cases directly.

The selected metadata comments document the active boundary case and the two requested excluded cases. The remaining excluded cases are recorded here without changing their selection or adding metadata comments.

Run the isolated reference verification from the repository root with:

```sh
python3 work/R53-T041/check.py
```

`work/R53-T041/` is coursework evidence for this issue and must be excluded from any later upstream contribution branch.
