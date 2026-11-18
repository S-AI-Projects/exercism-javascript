# Gigasecond Maintenance: Test Generation & Reproducibility Route

## Overview

This maintenance document details the test route and generation provenance for `exercises/practice/gigasecond`.
It connects the canonical case tracking in `exercises/practice/gigasecond/.meta/tests.toml` to the Jest test suite in `exercises/practice/gigasecond/gigasecond.spec.js`.

## Provenance and Maintenance Status

| File | Status | Provenance & Role |
| :--- | :--- | :--- |
| `gigasecond.js` | Hand-maintained | Learner skeleton stub; remains unsolved. |
| `gigasecond.spec.js` | Test Specification | Jest test suite derived from canonical problem specifications and `tests.toml`. |
| `.meta/config.json` | Metadata | Declares solution, test, and reference implementation paths. |
| `.meta/proof.ci.js` | Hand-maintained | CI reference solution implementing `gigasecond(date)`. |
| `.meta/tests.toml` | Tracked Metadata | Canonical UUID mappings; synced from `problem-specifications`. |

## Canonical Case to Test Output Mapping

Every test case in `gigasecond.spec.js` traces directly to a canonical case in `tests.toml`:

| Canonical UUID | Canonical Description | Spec Test Name | Input Date (UTC) | Expected Output Date |
| :--- | :--- | :--- | :--- | :--- |
| `92fbe71c-ea52-4fac-bd77-be38023cacf7` | date only specification of time | `tells a gigasecond anniversary since midnight` | `2011-04-25T00:00:00Z` | `2043-01-01T01:46:40Z` |
| `6d86dd16-6f7a-47be-9e58-bb9fb2ae1433` | second test for date only specification of time | `tells another gigasecond anniversary since midnight` | `1977-06-13T00:00:00Z` | `2009-02-19T01:46:40Z` |
| `77eb8502-2bca-4d92-89d9-7b39ace28dd5` | third test for date only specification of time | `tells gigasecond anniversary since midnight, from before UNIX epoch` | `1959-07-19T00:00:00Z` | `1991-03-27T01:46:40Z` |
| `c9d89a7d-06f8-4e28-a305-64f1b2abc693` | full time specified | `tells the anniversary, including a time` | `2015-01-24T22:00:00Z` | `2046-10-02T23:46:40Z` |
| `09d4e30e-728a-4b52-9005-be44a58d9eba` | full time with day roll-over | `tells the anniversary is next day when you are born at night` | `2015-01-24T23:59:59Z` | `2046-10-03T01:46:39Z` |
| `fcec307c-7529-49ab-b0fe-20309197618a` | does not mutate the input | `does not mutate the input` | `2015-02-24T23:59:59Z` | Unchanged input date |

## Exact Generation & Verification Commands

1. **Focused Coursework Regeneration Check**:
   ```bash
   python3 tools/course_checks/r53-t002.py
   ```
   Validates reproducible generation across two clean scratch environments, normalizes timestamps, verifies that no test cases are dropped, and checks exact parity.

2. **Automated End-to-End Coursework Verification**:
   ```bash
   python3 work/R53-T002/check.py
   ```
