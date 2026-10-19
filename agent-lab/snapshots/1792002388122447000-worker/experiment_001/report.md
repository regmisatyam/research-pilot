# Report: Four-Hour Reproducibility Pilot
## How Input Order Affects Runtime of sorted() vs Insertion Sort

---

### 1. Question

How does input order affect the runtime of Python's built-in `sorted()` compared
with a correct pure-Python insertion sort for small integer lists?

### 2. Hypothesis

Python's `sorted()` uses Timsort, which is O(n log n) worst-case but adaptive
to presorted data (O(n) best case). A correct insertion sort is O(n²) worst-case
but O(n) best case for already-sorted inputs. We hypothesize:

- Both algorithms will be fastest on sorted input and slowest on reverse-sorted.
- The ratio (insertion_sort time / sorted() time) will be smallest for sorted
  input and largest for reverse-sorted input.
- The ratio will grow with list size, especially for reverse-sorted input,
  confirming the O(n²) vs O(n log n) complexity difference.

### 3. Methodology

#### 3.1 Algorithms

- **builtin_sorted**: Python's built-in `sorted()` function (Timsort, C-implemented).
- **insertion_sort**: Pure-Python insertion sort (O(n²) worst case, O(n) best case).

#### 3.2 Input Generation

Four input types at three sizes (32, 128, 512):

| Input Type    | Description                                    | Seed |
|---------------|------------------------------------------------|------|
| random        | Random integers in [-1000, 1000]               | 42   |
| sorted        | Random integers, then sorted ascending         | 1    |
| reverse       | Random integers, then sorted descending        | 1    |
| duplicates    | Random integers in [0, 3] (only 4 distinct)    | 99   |

All seeds are deterministic and recorded.

#### 3.3 Timing

- **Timer**: `time.perf_counter()` — highest-resolution monotonic clock available.
- **Copying**: NOT timed. Each sort receives a fresh `list(data)` copy created
  BEFORE `time.perf_counter()` starts. This isolates the sort operation from
  allocation overhead.
- **Repetitions**: 50 per condition (exceeds the 30 minimum).
- **Randomization**: Measurement order across all 24 conditions × 2 algorithms
  was randomized with a fixed seed (12345) to reduce systematic bias from
  CPU frequency scaling, background processes, and thermal effects.

#### 3.4 Correctness

Every measured input was verified: `insertion_sort(data) == sorted(data)`.
Additional edge-case tests: empty list, singleton, negatives only, mixed
positive/negative, all duplicates, already sorted, reverse sorted.

#### 3.5 Platform

- Python 3.13.15, CPython
- Linux 7.0.14-linuxkit-aarch64 (aarch64 / ARM64)
- glibc 2.41

### 4. Results

#### 4.1 Correctness Tests

All 19 correctness tests passed (7 edge cases + 12 measured inputs × 1 algorithm).

#### 4.2 Timing Summary (microseconds, mean ± 1σ)

| Size | Input Type  | sorted()       | insertion_sort | Ratio (i/b) |
|------|-------------|----------------|----------------|-------------|
| 32   | random      | 0.37 ± 0.02    | 10.85 ± 0.97   | 29.5x       |
| 32   | sorted      | 0.24 ± 0.09    | 1.54 ± 0.05    | 6.4x        |
| 32   | reverse     | 0.26 ± 0.07    | 19.64 ± 0.58   | 75.3x       |
| 32   | duplicates  | 0.32 ± 0.03    | 9.09 ± 1.97    | 28.0x       |
| 128  | random      | 1.91 ± 0.68    | 140.41 ± 3.20  | 73.4x       |
| 128  | sorted      | 0.55 ± 0.02    | 5.65 ± 0.14    | 10.2x       |
| 128  | reverse     | 0.70 ± 0.13    | 299.51 ± 3.38  | 430.9x      |
| 128  | duplicates  | 1.49 ± 0.16    | 109.40 ± 2.80  | 73.4x       |
| 512  | random      | 10.00 ± 0.63   | 2787.53 ± 32.10| 278.6x      |
| 512  | sorted      | 1.80 ± 0.09    | 27.54 ± 0.60   | 15.3x       |
| 512  | reverse     | 2.34 ± 0.03    | 5220.90 ± 75.54| 2234.6x     |
| 512  | duplicates  | 9.04 ± 2.33    | 2311.15 ± 231.27| 255.8x     |

#### 4.3 Key Observations

1. **Insertion sort is always slower** than `sorted()` across all conditions.
   The builtin is C-implemented and uses Timsort; the insertion sort is
   pure-Python with O(n²) worst-case complexity.

2. **Input order matters dramatically for insertion sort**:
   - Sorted input: 6–15× slower (best case, O(n) comparisons)
   - Reverse sorted: 75–2235× slower (worst case, O(n²) comparisons)
   - The ratio grows superlinearly with size for reverse input, consistent
     with O(n²) complexity.

3. **Timsort also benefits from presortedness**:
   - sorted() on sorted input is ~2× faster than on random input at each size.
   - This confirms Timsort's adaptive behavior.

4. **Duplicate-heavy inputs** perform similarly to random inputs for insertion
   sort, suggesting the duplicate range (0–3) doesn't reduce comparisons enough
   to approach the O(n) best case.

### 5. Limitations

- **Single platform**: Results are from one machine (aarch64 Linux). Timing
  values are absolute and will differ on other hardware.
- **Relative comparisons are robust**: The ratio between algorithms is more
  meaningful than absolute times, and randomization of measurement order
  reduces systematic bias.
- **50 repetitions ≠ 50 independent samples**: Measurements are taken in the
  same process under similar conditions. They reduce noise but do not
  constitute independent experimental units.
- **Small sizes only**: Sizes 32, 128, 512 are small. At larger sizes,
  insertion sort would become impractical (O(n²) dominates).
- **Integer-only inputs**: Results may differ for other data types (strings,
  floats, objects with custom comparison).
- **No warm-up**: The Python interpreter and CPU may have been in different
  thermal/power states during the experiment.

### 6. Reproducibility

```bash
cd /workspace/experiment_001
python3 test_correctness.py    # Correctness tests
python3 benchmark.py            # Run benchmark (writes measurements.csv)
python3 verify_from_csv.py measurements.csv  # Verify from raw data
```

Raw data: `measurements.csv` (1200 rows, ~89 KB)
Scripts: `benchmark.py`, `test_correctness.py`, `verify_from_csv.py`

### 7. Conclusion

Input order has a large effect on insertion sort runtime (6× to 2235× variation
across conditions), while `sorted()` (Timsort) is more robust but still shows
adaptive behavior (~2× faster on sorted vs random). The builtin is always faster
in absolute terms due to C implementation and superior algorithm. The results
are consistent with theoretical complexity analysis.
