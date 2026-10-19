# Experiment 008: Partially Sorted Inputs — Disorder Scaling Analysis

**Date**: 2025-10-14
**Status**: Complete

## Hypothesis

For partially sorted inputs (where k% of elements are out of order), insertion
sort will perform proportionally better than on random input, and the performance
gap with `sorted()` will be smaller than on random input but larger than on fully
sorted input. The gap should scale roughly linearly with the disorder percentage.

## Design

- **Sizes**: 32, 128, 512 (same as experiment_001)
- **Disorder levels**: 0% (sorted), 10%, 25%, 50%, 75%, 100% (random)
- **Disorder method**: Fisher-Yates shuffle of k% of elements in a sorted list
  (swap k random pairs in a sorted array)
- **Repetitions**: 50 per condition
- **Timer**: time.perf_counter()
- **Copying**: NOT timed — copy happens before timing starts
- **Randomization**: measurement order randomized (seed 12345)
- **Seeds**: disorder=42, sorted=1, random=42
- **Correctness**: verified on every measured input before timing
- **Python**: 3.13.15 / aarch64 Linux

## Total measurements

- Conditions: 3 sizes × 6 disorder levels × 2 algorithms = 36
- Total rows: 36 × 50 = 1800

## Results

### Summary Statistics (microseconds)

| Size | Disorder | Builtin (μs) | Insertion (μs) | Ratio | B-CV | I-CV |
|------|----------|-------------|----------------|-------|------|------|
| 32   | 0%       | 0.22        | 1.55           | 7.1x  | 9.3% | 9.1% |
| 32   | 10%      | 0.51        | 3.79           | 7.4x  | 140.8% | 1.3% |
| 32   | 25%      | 0.35        | 4.06           | 11.6x | 8.6% | 0.9% |
| 32   | 50%      | 0.37        | 6.26           | 17.1x | 22.4% | 1.6% |
| 32   | 75%      | 0.36        | 8.27           | 22.7x | 8.5% | 7.1% |
| 32   | 100%     | 0.36        | 10.58          | 29.6x | 8.5% | 0.7% |
| 128  | 0%       | 0.56        | 5.70           | 10.2x | 8.3% | 10.9% |
| 128  | 10%      | 2.39        | 52.92          | 22.1x | 113.4% | 4.2% |
| 128  | 25%      | 1.89        | 88.40          | 46.9x | 2.9% | 2.9% |
| 128  | 50%      | 1.68        | 103.70         | 61.5x | 4.5% | 1.8% |
| 128  | 75%      | 2.53        | 177.19         | 70.0x | 4.1% | 2.2% |
| 128  | 100%     | 2.29        | 170.34         | 74.2x | 2.4% | 3.1% |
| 512  | 0%       | 2.09        | 32.05          | 15.3x | 33.6% | 4.3% |
| 512  | 10%      | 7.04        | 615.02         | 87.3x | 8.9% | 0.7% |
| 512  | 25%      | 9.09        | 1278.81        | 140.7x | 6.8% | 1.9% |
| 512  | 50%      | 9.37        | 2053.19        | 219.1x | 7.0% | 1.0% |
| 512  | 75%      | 10.94       | 2426.10        | 221.8x | 10.3% | 2.1% |
| 512  | 100%     | 11.36       | 2788.45        | 245.5x | 33.6% | 1.6% |

### Insertion Sort Scaling with Disorder

For insertion sort, mean time increases approximately linearly with disorder:

| Size | 0% → 100% | 0% → 50% | 50% → 100% |
|------|-----------|----------|------------|
| 32   | 1.55 → 10.58 (6.8×) | 1.55 → 6.26 (4.0×) | 6.26 → 10.58 (1.7×) |
| 128  | 5.70 → 170.34 (29.9×) | 5.70 → 103.70 (18.2×) | 103.70 → 170.34 (1.6×) |
| 512  | 32.05 → 2788.45 (87.0×) | 32.05 → 2053.19 (64.1×) | 2053.19 → 2788.45 (1.4×) |

The scaling is **super-linear** (more than proportional to disorder), consistent
with insertion sort's O(n·d) behavior where d is the number of inversions.

### Builtin Sorted (Timsort) Behavior

Timsort times are relatively stable across disorder levels, with some notable
anomalies:

- **Size 32**: 0.22–0.51 μs (no clear trend)
- **Size 128**: 0.56–2.53 μs (10% disorder is an outlier at 2.39 μs)
- **Size 512**: 2.09–11.36 μs (relatively smooth increase)

### Critical Finding: Extreme Outliers in Builtin Sorted Timing

At low disorder levels (10%), builtin_sorted shows **extreme timing outliers**:

- **Size 32, 10%**: 50 reps, min=0.33 μs, max=5.50 μs, CV=140.8%
  - 48 of 50 reps cluster at 0.33–0.50 μs
  - 1 rep at 1.17 μs, 1 rep at 5.50 μs (outliers)
- **Size 128, 10%**: 50 reps, min=1.92 μs, max=21.38 μs, CV=113.4%
  - 48 of 50 reps cluster at 1.92–2.33 μs
  - 1 rep at 21.38 μs (outlier)

These outliers inflate the mean and CV, making the mean an unreliable statistic
for these conditions. The median would be more robust.

### Hypothesis Validation

**Hypothesis: "The gap should scale roughly linearly with the disorder percentage."**

**PARTIALLY CONFIRMED, with caveats.**

For insertion sort, the scaling is **super-linear**, not linear:
- At size=32: 0%→100% gives 6.8× slowdown, but 0%→50% gives 4.0× (not 3.4×)
- At size=128: 0%→100% gives 29.9× slowdown, but 0%→50% gives 18.2× (not 15.0×)

This is because the number of inversions grows faster than linearly with disorder
percentage (swapping elements creates multiple inversions).

The ratio (insertion / builtin) increases with disorder:
- Size 32: 7.1x (0%) → 29.6x (100%) — 4.2× increase
- Size 128: 10.2x (0%) → 74.2x (100%) — 7.3× increase
- Size 512: 15.3x (0%) → 245.5x (100%) — 16.0× increase

The ratio grows **super-linearly** with disorder, consistent with insertion sort's
O(n·d) worst case vs Timsort's O(n) best case.

## Methodological Issues

### 1. Outlier sensitivity of mean statistics

The CV for builtin_sorted at 10% disorder is 140.8% (size=32) and 113.4% (size=128),
driven by 1–2 extreme outliers per condition. This makes the mean unreliable.

**Recommendation**: Report both mean and median, or use trimmed means, for
conditions with high outlier rates.

### 2. Disorder generation method

The disorder method (swap k random pairs) does not produce exactly k% disorder.
The actual number of inversions depends on which pairs are swapped and their
positions. A more precise method would count inversions and adjust.

### 3. GC-induced outliers

The extreme outliers in builtin_sorted timing (5.5× and 21.4× the cluster) are
consistent with GC pauses. This should be investigated in a follow-up experiment.

## Files

- `experiment_008/benchmark_partially_sorted.py` — Benchmark script
- `experiment_008/verify_partially_sorted.py` — CSV verification
- `experiment_008/measurements.csv` — Raw data (1800 rows, ~119 KB)

## Limitations

- Single platform (aarch64 Linux, Python 3.13.15).
- Integer-only inputs.
- Disorder method approximates k% but does not guarantee exact inversion count.
- 50 repetitions per condition.
- Repeated measurements on same input ≠ independent samples.
- Outlier analysis suggests GC interference; not controlled.

## Reproducibility

```bash
cd /workspace
python3 experiment_008/benchmark_partially_sorted.py
python3 experiment_008/verify_partially_sorted.py experiment_008/measurements.csv
```
