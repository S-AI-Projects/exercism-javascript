# Maintenance Documentation: `resistor-color-duo`

## Reference Complexity & Scaling Study

### Domain Definition & Fixed Bound
- **Color Palette Domain ($C = 10$):** `COLORS` is fixed to the 10 standard IEC resistor colors (`black` = 0 through `white` = 9).
- **Input Band List ($N \ge 2$):** `decodedValue([tens, ones])` destructures only the first two elements (`tens` and `ones`) and ignores any additional trailing colors ($N > 2$).
- **Complexity Bound:** `colorCode(color)` performs a linear search (`COLORS.indexOf(color)`) bounded between **1** and **10** string comparisons ($O(1)$). Because `decodedValue` invokes `colorCode` strictly **twice**, total `indexOf` comparisons are fixed within **[2, 20]** ($O(1)$ time and $O(1)$ auxiliary space), independent of input array length $N$.

### Operation & Branch Table Across Supported Input Sizes

| Input Size (Band Count) | Canonical / Domain Input | Expected Output | `colorCode(tens)` Comparisons | `colorCode(ones)` Comparisons | Total `indexOf` Comparisons | Ignored Elements |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 2 bands (named baseline) | `['brown', 'black']` | `10` | 2 (`brown` @ 1) | 1 (`black` @ 0) | **3** | 0 |
| 2 bands (named upper-index) | `['blue', 'grey']` | `68` | 7 (`blue` @ 6) | 9 (`grey` @ 8) | **16** | 0 |
| 2 bands (named mid-index) | `['yellow', 'violet']` | `47` | 5 (`yellow` @ 4) | 8 (`violet` @ 7) | **13** | 0 |
| 3 bands (extra color ignored) | `['green', 'brown', 'orange']` | `51` | 6 (`green` @ 5) | 2 (`brown` @ 1) | **8** | 1 (`'orange'`) |
| 2 bands (theoretical worst case) | `['white', 'white']` | `99` | 10 (`white` @ 9) | 10 (`white` @ 9) | **20** | 0 |

### Algorithm Cost vs. Runtime Overhead & Conclusion Limits
- **Algorithm work vs. process startup:** Executing 2 to 20 string comparisons in V8 takes sub-microsecond CPU time, whereas running Jest on the exercise suite takes hundreds of milliseconds due to Node.js process startup, Babel/ESM transpilation, and Jest test-runner initialization.
- **Limit of conclusion:** This $O(1)$ bound ($\le 20$ comparisons) holds strictly because the resistor color palette is fixed at 10 entries and `decodedValue` reads only the first 2 bands. Replacing `COLORS.indexOf` with a `Map` or object lookup would reduce per-lookup work from $\le 10$ comparisons to a single hash lookup, yielding no measurable user-visible speedup inside a single-process Jest run.

## Verification

Run the automated check script:

```bash
python3 work/R53-T025/check.py
```
