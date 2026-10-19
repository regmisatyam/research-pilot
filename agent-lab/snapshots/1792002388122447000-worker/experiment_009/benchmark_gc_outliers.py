"""
Experiment 009: GC Pause Investigation — Outlier Analysis in Builtin Sorted Timing

Hypothesis:
  The extreme outliers in builtin_sorted timing (CV=140% at size=32, 10% disorder)
  are caused by garbage collection pauses. When gc.collect() is called implicitly
  during memory allocation, it adds 5–20 μs of overhead, creating outliers.

  Prediction:
  - With gc.disable(), outlier rate drops to near zero
  - With gc.enable() (default), outlier rate matches experiment_008
  - Explicit gc.collect() before each measurement eliminates outliers but adds
    systematic overhead (~14–31 μs per call, per experiment_007)

Design:
  - Sizes: 32, 128, 512
  - Input types: sorted, 10% disorder, random (the three most interesting)
  - GC modes: disabled, enabled (default), explicit collect before each call
  - Repetitions: 200 per condition (high count to detect rare outliers)
  - Timer: time.perf_counter()
  - Copying: NOT timed
  - Seeds: sorted=1, disorder=42, random=42
  - Python: 3.13.15 / aarch64 Linux
"""
import csv
import gc
import os
import platform
import random
import sys
import time
from collections import defaultdict


def insertion_sort(arr):
    """Pure-Python insertion sort. Returns a new sorted list."""
    a = list(arr)
    n = len(a)
    for i in range(1, n):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    return a


def generate_sorted(size, seed):
    rng = random.Random(seed)
    return sorted([rng.randint(-1000, 1000) for _ in range(size)])


def generate_partially_sorted(size, disorder_pct, seed):
    rng = random.Random(seed)
    data = list(range(size))
    k = int(size * disorder_pct / 100.0)
    if k > 0:
        indices = list(range(size))
        rng.shuffle(indices)
        for i in range(k):
            idx_a = indices[i]
            idx_b = indices[rng.randint(0, size - 1)]
            data[idx_a], data[idx_b] = data[idx_b], data[idx_a]
    return data


def generate_random(size, seed):
    rng = random.Random(seed)
    return [rng.randint(-1000, 1000) for _ in range(size)]


def benchmark_one_gc_disabled(algo, data, reps):
    """Benchmark with gc disabled."""
    gc.disable()
    times = []
    for _ in range(reps):
        data_copy = list(data)
        start = time.perf_counter()
        result = algo(data_copy)
        end = time.perf_counter()
        times.append(end - start)
    gc.enable()
    return times


def benchmark_one_gc_enabled(algo, data, reps):
    """Benchmark with gc enabled (default)."""
    times = []
    for _ in range(reps):
        data_copy = list(data)
        start = time.perf_counter()
        result = algo(data_copy)
        end = time.perf_counter()
        times.append(end - start)
    return times


def benchmark_one_gc_collect(algo, data, reps):
    """Benchmark with explicit gc.collect() before each measurement."""
    times = []
    for _ in range(reps):
        gc.collect()
        data_copy = list(data)
        start = time.perf_counter()
        result = algo(data_copy)
        end = time.perf_counter()
        times.append(end - start)
    return times


def run_benchmark():
    info = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    print("Platform information:")
    for k, v in info.items():
        print(f"  {k}: {v}")
    print()

    sizes = [32, 128, 512]
    input_types = ["sorted", "disorder_10", "random"]
    reps = 200

    print("Hypothesis: GC pauses cause extreme outliers in builtin_sorted timing.")
    print(f"GC modes: disabled, enabled, explicit collect")
    print(f"Sizes: {sizes}")
    print(f"Input types: {input_types}")
    print(f"Repetitions: {reps}")
    print()

    # Build conditions
    conditions = []
    for size in sizes:
        for itype in input_types:
            if itype == "sorted":
                data = generate_sorted(size, 1)
            elif itype == "disorder_10":
                data = generate_partially_sorted(size, 10, 42)
            elif itype == "random":
                data = generate_random(size, 42)
            conditions.append((size, itype, data))

    # Randomize measurement order
    rng_order = random.Random(12345)
    condition_indices = list(range(len(conditions)))
    rng_order.shuffle(condition_indices)

    print(f"Running {reps} repetitions per condition...")
    print(f"Total conditions: {len(conditions)} x 2 algorithms x 3 GC modes = {len(conditions) * 6}")
    print(f"Total measurements: {len(conditions) * 6 * reps}")
    print()

    all_rows = []
    algo_map = {
        "builtin_sorted": sorted,
        "insertion_sort": insertion_sort,
    }

    for idx in condition_indices:
        size, itype, data = conditions[idx]

        # Verify correctness
        expected = sorted(data)
        for algo_name in algo_map:
            test_data = list(data)
            result = algo_map[algo_name](test_data)
            if result != expected:
                print(f"ERROR: {algo_name} failed correctness on size={size} type={itype}")
                sys.exit(1)

        for algo_name in algo_map:
            for gc_mode in ["disabled", "enabled", "collect"]:
                if gc_mode == "disabled":
                    times = benchmark_one_gc_disabled(algo_map[algo_name], data, reps)
                elif gc_mode == "enabled":
                    times = benchmark_one_gc_enabled(algo_map[algo_name], data, reps)
                elif gc_mode == "collect":
                    times = benchmark_one_gc_collect(algo_map[algo_name], data, reps)

                for i, t in enumerate(times):
                    all_rows.append({
                        "size": size,
                        "input_type": itype,
                        "algorithm": algo_name,
                        "gc_mode": gc_mode,
                        "repetition": i,
                        "time_seconds": t,
                        "time_microseconds": t * 1e6,
                    })

    # Write raw CSV
    csv_path = os.path.join(os.path.dirname(__file__), "measurements.csv")
    fieldnames = list(all_rows[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Raw measurements written to: {csv_path}")
    print(f"  Rows: {len(all_rows)}")
    print(f"  File size: {os.path.getsize(csv_path)} bytes")
    print()

    # Summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS (microseconds)")
    print("=" * 80)

    groups = defaultdict(list)
    for row in all_rows:
        key = (row["size"], row["input_type"], row["algorithm"], row["gc_mode"])
        groups[key].append(row["time_microseconds"])

    for size in sizes:
        for itype in input_types:
            print(f"\n  Size={size}, Input={itype}")
            print(f"  {'GC Mode':>12s}  {'Algo':>15s}  {'Mean':>8s}  {'Median':>8s}  {'Std':>8s}  {'CV':>6s}  {'Min':>8s}  {'Max':>8s}  {'Outliers':>10s}")
            for algo_name in ["builtin_sorted", "insertion_sort"]:
                for gc_mode in ["disabled", "enabled", "collect"]:
                    key = (size, itype, algo_name, gc_mode)
                    if key in groups:
                        times = groups[key]
                        mean_t = sum(times) / len(times)
                        sorted_t = sorted(times)
                        median_t = sorted_t[len(sorted_t) // 2]
                        std_t = (sum((x - mean_t) ** 2 for x in times) / len(times)) ** 0.5
                        cv_t = (std_t / mean_t * 100) if mean_t > 0 else 0
                        min_t = sorted_t[0]
                        max_t = sorted_t[-1]
                        # Outliers: values > 3× the median
                        iqr = sorted_t[int(len(sorted_t) * 0.75)] - sorted_t[int(len(sorted_t) * 0.25)]
                        upper_fence = sorted_t[int(len(sorted_t) * 0.75)] + 3 * iqr
                        outlier_count = sum(1 for t in times if t > upper_fence)
                        print(f"  {gc_mode:>12s}  {algo_name:>15s}  {mean_t:>8.2f}  {median_t:>8.2f}  {std_t:>8.2f}  {cv_t:>5.1f}%  {min_t:>8.2f}  {max_t:>8.2f}  {outlier_count:>10d}")

    print()
    print("Outliers defined as values > Q3 + 3×IQR.")
    print("Copying is NOT timed; only the sort operation is measured.")
    print("GC disabled means gc.disable() before the loop, gc.enable() after.")
    print("GC collect means gc.collect() before each individual measurement.")

    return csv_path


if __name__ == "__main__":
    csv_path = run_benchmark()
    print()
    print(f"Done. Re-run: python3 {os.path.join(os.path.dirname(__file__), 'verify_gc_outliers.py')} {csv_path}")
