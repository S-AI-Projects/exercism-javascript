# `say` canonical test cases

The 19 entries in `.meta/tests.toml` have no `include` keys, so all 19 are included by default and none are excluded. The selected JavaScript tests behave as follows:

| UUID | JavaScript test | Rationale |
| --- | --- | --- |
| `5d22a120-ba0c-428c-bd25-8682235d83e8` | `zero` | Checks the lower bound and the explicit `"zero"` result. It is an active `test(...)`. |
| `9b5eed77-dbf6-439d-b920-3f7eb58928f6` | `one` | Checks the smallest positive value using the direct small-number lookup. It is written as `xtest(...)`, so Jest skips it in the working test file; the canonical case is still included. |
| `7c499be1-612e-4096-a5e1-43b2f719406d` | `fourteen` | Checks a teen handled by the direct small-number lookup, rather than the tens-and-ones path. Jest skips its `xtest(...)` in the working test file; the canonical case is still included. |

`xtest(...)` is Jest's skipped-test form; it does not change canonical inclusion. The verifier enables those tests only in its temporary copy. The JavaScript spec has one extra local test, `one million two`, beyond the 19 canonical entries.
