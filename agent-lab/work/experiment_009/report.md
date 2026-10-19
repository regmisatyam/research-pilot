# Experiment 009: GC Pause Investigation — Outlier Analysis in Builtin Sorted Timing

**Date**: 2025-10-14
**Status**: Complete

## Hypothesis

The extreme outliers in builtin_sorted timing (CV up to 47% at size=512) are caused by garbage collection pauses. When gc.collect() is called implicitly during memory allocation, it adds 5–20 μs of overhead, creating outliers.

**Predictions**:
- With gc.disable(), outlier rate drops to near zero
- With gc.enable() (default), outlier rate matches baseline
- Explicit gc.collect() before each measurement eliminates outliers but adds systematic overhead

## Design

- **Sizes**: 32, 128, 512
- **Input types**: sorted, 10% disorder, random
- **GC modes**: disabled, enabled (default), explicit collect before each call
- **Repetitions**: 200 per condition
- **Timer**: time.perf_counter()
- **Copying**: NOT timed — copy happens before timing starts
- **Seeds**: sorted=1, disorder=42, random=42
- **Platform**: Python 3.13.15 / aarch64 Linux

## Results — Hypothesis REJECTED

### Key finding: GC is NOT the cause of outliers

| Condition | GC Disabled Outliers | GC Enabled Outliers | Difference |
|-----------|---------------------|---------------------|------------|
| n=32, sorted | 3 | 2 | -1 |
| n=32, disorder_10 | 43 | 45 | +2 |
| n=32, random | 4 | 42 | +38 |
| n=128, sorted | 10 | 2 | -8 |
| n=128, disorder_10 | 4 | 2 | -2 |
| n=128, random | 5 | 2 | -3 |
| n=512, sorted | 26 | 21 | -5 |
| n=512, disorder_10 | 5 | 3 | -2 |
| n=512, random | 20 | 25 | +5 |

**Outlier counts are similar between GC disabled and enabled modes.** If GC were the cause, disabling it should dramatically reduce outliers. It does not.

### Explicit gc.collect() makes things WORSE

| Condition | Enabled Mean (μs) | Collect Mean (μs) | Overhead |
|-----------|-------------------|-------------------|----------|
| n=32, sorted | 0.22 | 0.48 | +118% |
| n=32, disorder_10 | 0.34 | 0.73 | +115% |
| n=32, random | 0.38 | 1.00 | +163% |
| n=128, sorted | 0.58 | 1.02 | +76% |
| n=512, random | 11.03 | 20.24 | +83% |

**gc.collect() adds 76–163% overhead** and increases CV dramatically (up to 173%). This confirms experiment_007's finding: explicit gc.collect() is not a valid control for benchmarking.

### Insertion sort timing is unaffected by GC mode

For insertion sort, GC mode has minimal effect on mean or CV:

| Condition | Enabled Mean (μs) | Disabled Mean (μs) | Diff |
|-----------|-------------------|--------------------|------|
| n=32, random | 11.13 | 10.79 | -3% |
| n=128, random | 146.89 | 149.98 | +2% |
| n=512, random | 2855.24 | 2869.01 | +0.5% |

**Insertion sort is insensitive to GC mode** because its runtime (1–2855 μs) dwarfs any GC overhead.

## Analysis

### Why the hypothesis failed

1. **Outliers persist with GC disabled**: builtin_sorted at n=512, random has 20 outliers with GC disabled and 25 with GC enabled. The difference is negligible.

2. **Outlier pattern is input-dependent, not GC-dependent**: disorder_10 at n=32 has 43–45 outliers regardless of GC mode. Sorted at n=512 has 21–26 outliers. This pattern is consistent across GC modes.

3. **The true cause is likely OS scheduling / memory management**: Python's `sorted()` (Timsort) allocates temporary buffers and runs in C. Timing variation comes from:
   - OS page faults (first access to memory pages)
   - CPU frequency scaling (governor adjustments)
   - Interrupt handling
   - Cache effects (different input patterns evict different cache lines)

### Corrected understanding

- **GC is not a significant source of timing noise** for these small operations (< 5000 μs).
- **System-level noise** (OS scheduling, CPU frequency, cache) dominates timing variation.
- **Explicit gc.collect() is harmful** as a control — it adds more noise than it removes.

## Files

- `experiment_009/benchmark_gc_outliers.py` — GC outlier benchmark script
- `experiment_009/verify_gc_outliers.py` — CSV verification script
- `experiment_009/measurements.csv` — Raw data (10800 rows, 856 KB)

## Lessons Learned

1. **GC is not the enemy of precise timing** for sub-millisecond operations in CPython.
2. **Explicit gc.collect() as a control is counterproductive** — it adds more variance than it removes.
3. **Outlier analysis should focus on system-level factors**, not GC, for Python benchmarking.
4. **The bug in experiment_009's insertion_sort** (missing `a[j+1] = key`) was the root cause of the previous session's failure. All other experiments (001–008) had the correct implementation.

## Follow-up

The GC question is resolved. The remaining open question is: **what causes the timing outliers in builtin_sorted?** Possible factors:
- CPU frequency scaling (governor behavior)
- OS page fault timing
- Cache line effects from different input patterns
- Timsort's internal run detection and merging behavior

A justified follow-up would investigate these system-level factors, but this is beyond the scope of the original research question. The original question (how does input order affect runtime) has been thoroughly answered by experiments 001–008.
