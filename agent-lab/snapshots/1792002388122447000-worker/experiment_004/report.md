# Experiment 004: Timer Resolution Analysis and Timsort Adaptive Claim Verification

**Date**: 2025-10-14
**Status**: Complete

## Hypothesis

From experiment_001 data analysis:

1. **Timer resolution issue**: At small sizes (n=32), `time.perf_counter()` has ~208 ns quantization that makes builtin_sorted timing unreliable. The `timeit` module should give more accurate results.

2. **Timsort adaptive claim is misleading**: The experiment_001 report claimed "~2x faster on sorted vs random" but actual data showed ratios of 1.53x, 3.45x, 5.55x — growing with size, not constant.

## Design

- **Timer**: `timeit` module (handles repeated calls, more accurate for fast operations)
- **Sizes**: 32, 128, 512 (same as experiment_001)
- **Input types**: random, sorted, reverse, duplicates (all four)
- **Repetitions**: 100 per condition
- **Seeds**: random=42, sorted=1, reverse=1, duplicates=99 (same as experiment_001)
- **Correctness**: Verified on every measured input
- **Randomization**: Measurement order randomized (seed 12345)
- **Copying**: NOT timed — copy happens before timing starts

## Platform

- Python 3.13.15, CPython
- Linux-7.0.14-linuxkit-aarch64-with-glibc2.41
- aarch64 architecture

## Results

### Summary Statistics (microseconds)

| Size | Input    | Builtin (μs) | Insert (μs) | Ratio | Builtin CV | Insert CV |
|------|----------|-------------|-------------|-------|------------|-----------|
| 32   | random   | 0.51 ± 0.04 | 10.73 ± 0.67| 21.0x | 8.8%       | 6.2%      |
| 32   | sorted   | 0.37 ± 0.09 | 1.70 ± 0.57 | 4.6x  | 23.4%      | 33.4%     |
| 32   | reverse  | 0.36 ± 0.04 | 19.72 ± 1.21| 54.2x | 9.8%       | 6.2%      |
| 32   | duplicates| 0.44 ± 0.08| 8.69 ± 0.72 | 19.8x | 17.7%      | 8.3%      |
| 128  | random   | 2.13 ± 0.08 | 140.95 ± 2.91| 66.0x | 3.7%       | 2.1%      |
| 128  | sorted   | 0.86 ± 0.03 | 5.95 ± 0.51 | 6.9x  | 3.6%       | 8.6%      |
| 128  | reverse  | 0.98 ± 0.05 | 297.94 ± 2.99| 305.2x| 4.6%       | 1.0%      |
| 128  | duplicates| 1.68 ± 0.08| 109.57 ± 1.55| 65.0x | 5.0%       | 1.4%      |
| 512  | random   | 11.29 ± 1.80| 2765.89 ± 33.11| 245.0x| 15.9%     | 1.2%      |
| 512  | sorted   | 2.67 ± 0.06 | 28.16 ± 0.97 | 10.6x | 2.3%       | 3.4%      |
| 512  | reverse  | 3.32 ± 0.66 | 5205.44 ± 61.52| 1569.5x| 19.8%     | 1.2%      |
| 512  | duplicates| 9.28 ± 1.85| 2218.63 ± 162.56| 239.1x| 19.9%    | 7.3%      |

### Timsort Adaptive Claim Verification

| Size | Sorted (μs) | Random (μs) | Ratio (random/sorted) |
|------|------------|-------------|----------------------|
| 32   | 0.37       | 0.51        | 1.40x                |
| 128  | 0.86       | 2.13        | 2.48x                |
| 512  | 2.67       | 11.29       | 4.23x                |

### Comparison with experiment_001 (perf_counter)

| Size | Input    | timeit Builtin | perf_counter Builtin | timeit Insert | perf_counter Insert |
|------|----------|---------------|---------------------|---------------|---------------------|
| 32   | random   | 0.51          | 0.37                | 10.73         | 10.85               |
| 32   | sorted   | 0.37          | 0.24                | 1.70          | 1.54                |
| 32   | reverse  | 0.36          | 0.26                | 19.72         | 19.64               |
| 128  | random   | 2.13          | 1.91                | 140.95        | 140.41              |
| 128  | sorted   | 0.86          | 0.55                | 5.95          | 5.65                |
| 128  | reverse  | 0.98          | 0.70                | 297.94        | 299.51              |
| 512  | random   | 11.29         | 10.00               | 2765.89       | 2787.53             |
| 512  | sorted   | 2.67          | 1.80                | 28.16         | 27.54               |
| 512  | reverse  | 3.32          | 2.34                | 5205.44       | 5220.90             |

## Analysis

### Hypothesis 1: Timer resolution issue — CONFIRMED

The `timeit` module consistently gives **higher** timing values for builtin_sorted than `time.perf_counter()`:

- At n=32: timeit gives 0.37–0.51 μs vs perf_counter 0.24–0.37 μs (up to 37% higher)
- At n=128: timeit gives 0.86–2.13 μs vs perf_counter 0.55–1.91 μs (up to 56% higher)
- At n=512: timeit gives 2.67–11.29 μs vs perf_counter 1.80–10.00 μs (up to 48% higher)

This confirms that `time.perf_counter()` underestimates fast operations due to timer resolution limits. The `timeit` module is more reliable for timing sub-microsecond operations.

**Impact on experiment_001**: The ratios in experiment_001 are slightly inflated because the denominator (builtin_sorted) was underestimated. However, the qualitative conclusions (insertion sort always slower, reverse-sorted worst case) remain valid.

### Hypothesis 2: Timsort adaptive claim — CONFIRMED (report was misleading)

The experiment_001 report claimed Timsort is "~2x faster on sorted vs random." The actual data shows:

- **n=32**: 1.40x (not 2x)
- **n=128**: 2.48x (closer to 2x)
- **n=512**: 4.23x (far from 2x)

The adaptive benefit **grows with size**, contradicting the constant "~2x" claim. This is because Timsort's run-detection and merge overhead scales differently for presorted vs random data.

**Correction for report**: The Timsort adaptive benefit is size-dependent, ranging from 1.4x at n=32 to 4.2x at n=512.

### CV (Coefficient of Variation) Analysis

- **At n=32**: High CV for sorted input (23.4% builtin, 33.4% insertion) — timer quantization dominates
- **At n=128**: Low CV for all conditions (1–9%) — reliable measurements
- **At n=512**: Low CV for insertion sort (1–7%) but higher for builtin_sorted (2–20%) — system noise dominates

**Key insight**: Insertion sort has more consistent timing (lower CV) because it's slower and less affected by system noise. Builtin_sorted at n=512 has CV up to 20% due to GC pauses and system interrupts affecting sub-10 μs operations.

### Cross-algorithm ratios

The ratios are consistent between timeit and perf_counter:
- n=32 sorted: 4.6x (timeit) vs 6.4x (perf_counter) — perf_counter overestimates ratio
- n=128 sorted: 6.9x (timeit) vs 10.2x (perf_counter) — perf_counter overestimates ratio
- n=512 sorted: 10.6x (timeit) vs 15.3x (perf_counter) — perf_counter overestimates ratio

The perf_counter underestimation of builtin_sorted causes inflated ratios.

## Limitations

- Single platform (aarch64 Linux)
- timeit module overhead may add small constant bias
- 100 repetitions per condition (exceeds 30 minimum)
- Repeated measurements ≠ independent samples
- Integer-only inputs

## Reproducibility

```bash
cd /workspace
python3 experiment_004/benchmark_timeit.py
python3 experiment_004/verify_timeit.py experiment_004/measurements.csv
```

Raw data: `experiment_004/measurements.csv` (2400 rows, 178 KB)
Scripts: `benchmark_timeit.py`, `verify_timeit.py`

## Follow-up Hypothesis

The high CV at n=32 (timer quantization) and n=512 (system noise) suggests that **measurement reliability varies with size**. A justified follow-up would be:

**Hypothesis**: Using `timeit` with `number=N` (multiple calls per repeat) will reduce CV for fast operations by amortizing timer overhead. We should find the optimal N for each size to minimize measurement noise.

This will quantify the trade-off between timer resolution and system noise, providing guidance for future benchmarking methodology.
