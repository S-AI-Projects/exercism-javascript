# Hints

## General

This exercise implements a **reactive spreadsheet model** with three building blocks:

| Class | Role |
|---|---|
| `InputCell` | A settable leaf node. Its `value` property holds the current value. |
| `ComputeCell` | A derived node. Its value is recomputed whenever any upstream input changes. |
| `CallbackCell` | A listener attached to a `ComputeCell` that records every new stable value. |

---

## Selected Contract Cases — Input/Output Walkthrough

### Case 1 — `accepts input` (input cells have a value)

**What the spec tests:**
```js
const inputCell = new InputCell(10);
expect(inputCell.value).toEqual(10);
```

**Contract:** Constructing an `InputCell` with an initial value must expose that value
immediately through the `.value` property. No computation is required.

**Unspecified:** The spec does not test negative numbers, `0`, `NaN`, or non-numeric
values as the seed — behaviour for those inputs is outside the exercise contract.

---

### Case 2 — `allows input cell value to be set` (an input cell's value can be set)

**What the spec tests:**
```js
const inputCell = new InputCell(4);
inputCell.setValue(20);
expect(inputCell.value).toEqual(20);
```

**Contract:** Calling `setValue(newValue)` on an `InputCell` must update `.value`
synchronously before the call returns.

**Decision table:**

| Condition | Required outcome |
|---|---|
| `newValue !== currentValue` | `.value` becomes `newValue`; propagation fires |
| `newValue === currentValue` | No propagation (callbacks must not fire) — _see the reference_ |

**Unspecified:** The spec does not define what happens if `setValue` is called with
the _same_ value. The reference implementation silently skips propagation, but this
is an implementation choice, not a contractual requirement of this particular test.

---

### Case 3 — `allows setting compute cells` (compute cells calculate initial value)

**What the spec tests:**
```js
const inputCell = new InputCell(1);
const fn = (inputCells) => inputCells[0].value + 1;
const computeCell = new ComputeCell([inputCell], fn);
expect(computeCell.value).toEqual(2);
```

**Contract:** A `ComputeCell` must evaluate its function **at construction time**
using the initial values of its input cells and expose the result as `.value`.

**Decision table:**

| Condition | Required outcome |
|---|---|
| Input cell value is `1`, function is `cells[0].value + 1` | `computeCell.value === 2` immediately after construction |
| Inputs not yet changed | No callbacks have been registered; none should fire |

**Unspecified:** The spec does not test construction with zero input cells or with a
function that throws — behaviour in those cases is outside the exercise contract.

---

## Why These Three Cases Matter

These three cases form the **foundation** of the reactive graph:

1. `InputCell` stores the graph's _leaves_ — without reliable initial values, nothing
   computes correctly.
2. `setValue` is the _only way to trigger propagation_ — correctness here determines
   whether the entire update cascade works.
3. `ComputeCell` construction is where the _initial stable state_ is established —
   any lazy evaluation at this point breaks every downstream assertion.

A correct implementation of these three cases alone is enough to make the first three
spec tests pass with the reference solution.
