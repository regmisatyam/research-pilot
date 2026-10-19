"""
Experiment 008: Partially Sorted Inputs — Follow-up to Experiment 001/003

Hypothesis:
  For partially sorted inputs (where k% of elements are out of order),
  insertion sort will perform proportionally better than on random input,
  and the performance gap with sorted() will be smaller than on random
  input but larger than on fully sorted input. The gap should scale
  roughly linearly with the disorder percentage.

Design:
  - Sizes: 32, 128, 512 (same as experiment_001)
  - Disorder levels: 0% (sorted), 10%, 25%, 50%, 75%, 100% (random)
  - Disorder method: Fisher-Yates shuffle of k% of elements in a sorted list
  - Repetitions: 50 per condition (same as experiment_001)
  - Timer: time.perf_counter()
  - Copying: NOT timed
  - Randomization: measurement order randomized (seed 12345)
  - Seeds: disorder=42, sorted=1, random=42
  - Correctness: verified on every measured input
"""
import csv
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


def generate_partially_sorted(size, disorder_pct, seed):
    """Generate a sorted list, then shuffle disorder_pct% of elements.

    disorder_pct=0 -> fully sorted
    disorder_pct=100 -> random permutation (not random values)
    """
    rng = random.Random(seed)
    # Start with sorted values
    data = list(range(size))
    # Shuffle disorder_pct% of elements
    k = int(size * disorder_pct / 100.0)
    if k > 0:
        indices = list(range(size))
        rng.shuffle(indices)
        # Swap k random pairs
        for i in range(k):
            idx_a = indices[i]
            idx_b = indices[rng.randint(0, size - 1)]
            data[idx_a], data[idx_b] = data[idx_b], data[idx_a]
    return data


def generate_random(size, seed):
    """Generate random integers in [-1000, 1000]."""
    rng = random.Random(seed)
    return [rng.randint(-1000, 1000) for _ in range(size)]


def benchmark_one(algo_name, data, reps):
    """Run reps measurements for one algorithm on one input."""
    times = []
    for _ in range(reps):
        data_copy = list(data)
        start = time.perf_counter()
        result = algo_name(data_copy)
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
    disorder_levels = [0, 10, 25, 50, 75, 100]
    reps = 50

    print(f"Hypothesis: Partially sorted insertion sort scales linearly with disorder.")
    print(f"Disorder levels: {disorder_levels}%")
    print(f"Sizes: {sizes}")
    print(f"Repetitions: {reps}")
    print()

    # Build conditions
    conditions = []
    for size in sizes:
        for dpct in disorder_levels:
            if dpct == 0:
                # Fully sorted
                rng = random.Random(1)
                data = sorted([rng.randint(-1000, 1000) for _ in range(size)])
            elif dpct == 100:
                # Fully random
                data = generate_random(size, 42)
            else:
                data = generate_partially_sorted(size, dpct, 42)
            conditions.append((size, dpct, data))

    # Randomize measurement order
    rng_order = random.Random(12345)
    condition_indices = list(range(len(conditions)))
    rng_order.shuffle(condition_indices)

    print(f"Running {reps} repetitions per condition...")
    print(f"Total conditions: {len(conditions)} x 2 algorithms = {len(conditions) * 2}")
    print(f"Total measurements: {len(conditions) * 2 * reps}")
    print()

    all_rows = []
    algo_map = {
        "builtin_sorted": sorted,
        "insertion_sort": insertion_sort,
    }
    algo_names = list(algo_map.keys())

    for idx in condition_indices:
        size, dpct, data = conditions[idx]

        # Verify correctness
        expected = sorted(data)
        for algo_name in algo_names:
            test_data = list(data)
            result = algo_map[algo_name](test_data)
            if result != expected:
                print(f"ERROR: {algo_name} failed correctness on size={size} disorder={dpct}%")
                sys.exit(1)

        for algo_name in algo_names:
            times = benchmark_one(algo_map[algo_name], data, reps)
            for i, t in enumerate(times):
                all_rows.append({
                    "size": size,
                    "disorder_pct": dpct,
                    "algorithm": algo_name,
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
        key = (row["size"], row["disorder_pct"], row["algorithm"])
        groups[key].append(row["time_microseconds"])

    for size in sizes:
        print(f"\n  Size = {size}")
        print(f"  {'Disorder':>10s}  {'Builtin':>10s}  {'Insertion':>10s}  {'Ratio':>8s}  {'B-CV':>6s}  {'I-CV':>6s}")
        for dpct in disorder_levels:
            b_key = (size, dpct, "builtin_sorted")
            i_key = (size, dpct, "insertion_sort")
            if b_key in groups and i_key in groups:
                b_times = groups[b_key]
                i_times = groups[i_key]
                b_mean = sum(b_times) / len(b_times)
                i_mean = sum(i_times) / len(i_times)
                b_std = (sum((x - b_mean) ** 2 for x in b_times) / len(b_times)) ** 0.5
                i_std = (sum((x - i_mean) ** 2 for x in i_times) / len(i_times)) ** 0.5
                ratio = i_mean / b_mean if b_mean > 0 else float("inf")
                b_cv = (b_std / b_mean * 100) if b_mean > 0 else 0
                i_cv = (i_std / i_mean * 100) if i_mean > 0 else 0
                print(f"  {dpct:>9}%  {b_mean:>10.2f}  {i_mean:>10.2f}  {ratio:>8.1f}x  {b_cv:>5.1f}%  {i_cv:>5.1f}%")

    print()
    print("Note: ratio > 1 means insertion_sort is slower than builtin_sorted.")
    print("Copying is NOT timed; only the sort operation is measured.")
    print("Disorder=0% = fully sorted, Disorder=100% = random values.")
    print("Measurement order was randomized to reduce systematic bias.")

    return csv_path


if __name__ == "__main__":
    csv_path = run_benchmark()
    print()
    print(f"Done. Re-run: python3 {os.path.join(os.path.dirname(__file__), 'verify_partially_sorted.py')} {csv_path}")
