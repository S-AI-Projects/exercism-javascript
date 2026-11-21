# Rail Fence Cipher `encode()` scaling

## What the algorithm does

Let `n` be the message length and `r` be the number of rails.
`cycleRails()` visits the message once and stores the rail number for each
character. `encode()` then visits those rail numbers once, appends each
character to its rail, and joins the rail strings.

The usual algorithmic analysis is expected **O(n + r) time** and
**O(n + r) extra space**: the message is processed twice, and initializing
and joining the rails adds work proportional to the number of rails. With a
fixed rail count such as 3, this is expected O(n) time and space. Each
character's rail is chosen in constant time; more rails add O(r) initialization
and join work. The code uses JavaScript string concatenation (`+=`), whose
copying and flattening behavior depends on the runtime, so the theoretical
model does not guarantee identical timings across JavaScript engines.

## Benchmark method

The benchmark ran inside a Jest test using Node.js `performance.now()` on
Node.js 26.13.1 and Jest 30.1.3. Jest startup and module compilation happen
before the timed section. Before timing, it checked the known three-rail
example and checked that decoding each generated message returned the original
message with the same length.

Each message contains the uppercase alphabet repeated and truncated to the
requested length. The rail count remained 3. For each size, the benchmark made
100 untimed warm-up calls, then took 7 timing samples. Each sample measured
100 calls to `encode()` and divided the elapsed time by 100. The table shows
the median per-call time calculated from those 7 samples.

| Message length | Rails | Repetitions | Median time per `encode()` |
| ---: | ---: | ---: | ---: |
| 100 | 3 | 7 | 0.001235 ms |
| 1,000 | 3 | 7 | 0.021979 ms |
| 5,000 | 3 | 7 | 0.042242 ms |

These are measurements from one run on the recorded Node.js environment, not
a comparison against another implementation. The results increased across
these sizes, but the samples varied and should not be treated as proof of an
exact scaling rate or a speedup. Runtime version, JIT compilation, garbage
collection, and timer resolution can affect such short measurements. Since
the rail count stayed fixed at 3, this benchmark does not measure how changing
the rail count affects runtime.

Run the reproducible correctness check and benchmark from the repository root:

```sh
python3 work/R53-T015/check.py
```

It reads the exercise file paths from `.meta/config.json`, runs all exercise
tests against the reference in a temporary copy, then runs the benchmark in
that same copy. Inputs, raw measurements, calculated medians, test results,
and tool versions are saved under `work/R53-T015/`.
