# Complex Numbers Maintenance: Canonical Case Decisions

## Overview

This maintenance document records the canonical case rationale for `exercises/practice/complex-numbers`.
All 40 canonical test cases from `problem-specifications` are reviewed and included in `exercises/practice/complex-numbers/.meta/tests.toml` (0 exclusions).

## Target Canonical Cases Mapping Table

The following table connects the canonical test cases specified in Task R53-T001 to their canonical UUIDs, test names, JavaScript operations, inclusion status, and maintenance rationales:

| UUID | Test Name | JavaScript Expression | Status | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `9f98e133-eb7f-45b0-9676-cce001cd6f7a` | Real part of a purely real number | `new ComplexNumber(1, 0).real` | Included | Validates direct property/getter access on the real component when the imaginary part is `0`. Ensures that purely real numbers retain their exact numerical value without unintended coercion. |
| `07988e20-f287-4bb7-90cf-b32c4bffe0f3` | Real part of a purely imaginary number | `new ComplexNumber(0, 1).real` | Included | Validates property/getter access when the real component is `0`. Ensures JavaScript's falsy `0` is properly preserved as a distinct numeric value and not converted to `undefined` or `null`. |
| `4a370e86-939e-43de-a895-a00ca32da60a` | Real part of a number with real and imaginary part | `new ComplexNumber(1, 2).real` | Included | Validates independent field retrieval from a complex number instance where both real and imaginary components are non-zero (`1` and `2`), confirming correct property storage. |

## Canonical Case Review Summary

- **Total Canonical Cases in `tests.toml`**: 40
- **Total Excluded Cases**: 0
- **Total Included Cases**: 40
- **Learner Stub**: `exercises/practice/complex-numbers/complex-numbers.js` remains unsolved and unchanged.
- **Reference Implementation**: `exercises/practice/complex-numbers/.meta/proof.ci.js` provides `ComplexNumber` with `.real` and `.imag` properties set in the constructor.

## Verification

The canonical case decisions and reference implementation can be verified using the automated check:

```bash
python3 work/R53-T001/check.py
```
