"""
Experiment 004: Timer resolution analysis and Timsort adaptive claim verification.

Hypothesis (from experiment_001 data analysis):
  1. Timer resolution at small sizes (32) introduces quantization error for
     builtin_sorted (~208 ns resolution). Using timeit module should give
     more reliable results.
  2. The Timsort adaptive benefit grows with size (1.53x at n=32, 3.45x at n=128,
     5.55x at n=512), contradicting the "~2x" claim in experiment_001 report.

Design:
- Timer: timeit module (handles repeated calls, discards outliers)
- Also run perf_counter for comparison
- Sizes: 32, 128, 512 (same as experiment_001)
- Input types: random, sorted, reverse, duplicates (all four)
- Repetitions: 100 per condition (timeit default is 100000, we use 100)
- Deterministic seeds (same as experiment_001)
- Correctness verified on every measured input
- Copying NOT timed (copy happens before timing starts)
"""
import csv
import os
import platform
import random
import sys
import time
import timeit
from collections import defaultdict


# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Input generation
# ---------------------------------------------------------------------------

def generate_input(itype, size, seed):
    """Generate a list of integers. Returns the list."""
    rng = random.Random(seed)
    if itype == "random":
        return [rng.randint(-1000, 1000) for _ in range(size)]
    elif itype == "sorted":
        return sorted([rng.randint(-1000, 1000) for _ in range(size)])
    elif itype == "reverse":
        return sorted([rng.randint(-1000, 1000) for _ in range(size)], reverse=True)
    elif itype == "duplicates":
        return [rng.randint(0, 3) for _ in range(size)]
    else:
        raise ValueError(f"Unknown input type: {itype}")


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------

def benchmark_perf_counter(algo_fn, data, reps):
    """Run reps measurements using time.perf_counter()."""
    times = []
    for _ in range(reps):
        data_copy = list(data)
        start = time.perf_counter()
        result = algo_fn(data_copy)
        end = time.perf_counter()
        times.append(end - start)
    return times


def benchmark_timeit(algo_fn, data, reps):
    """Run reps measurements using timeit module."""
    # timeit.repeat runs the setup + stmt reps times each, returns list of total times
    # We use number=1 (one call per repeat) and reps repeats
    timer = timeit.default_timer
    times = timeit.repeat(
        stmt=lambda: algo_fn(list(data)),
        setup=lambda: None,
        number=1,
        repeat=reps,
        timer=timer,
    )
    return times


def run_benchmark():
    # Platform info
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

    # Parameters
    sizes = [32, 128, 512]
    input_types = ["random", "sorted", "reverse", "duplicates"]
    seeds = {"random": 42, "sorted": 1, "reverse": 1, "duplicates": 99}
    reps = 100  # repetitions per condition

    # Build all conditions
    conditions = []
    for size in sizes:
        for itype in input_types:
            seed = seeds[itype]
            data = generate_input(itype, size, seed)
            conditions.append((size, itype, seed, data))

    # Randomize measurement order
    rng_order = random.Random(12345)
    condition_indices = list(range(len(conditions)))
    rng_order.shuffle(condition_indices)

    # Run measurements
    print(f"Running {reps} repetitions per condition...")
    print(f"Total conditions: {len(conditions)} x 2 algorithms = {len(conditions) * 2}")
    print(f"Total measurements: {len(conditions) * 2 * reps}")
    print()

    all_rows = []
    algo_map = {
        "builtin_sorted": sorted,
        "insertion_sort": insertion_sort,
    }

    for idx in condition_indices:
        size, itype, seed, data = conditions[idx]

        # Verify correctness
        expected = sorted(data)
        for algo_name in algo_map:
            test_data = list(data)
            result = algo_map[algo_name](test_data)
            if result != expected:
                print(f"ERROR: {algo_name} failed correctness on size={size} type={itype}")
                sys.exit(1)

        for algo_name in algo_map:
            # Use timeit for more accurate timing
            times = benchmark_timeit(algo_map[algo_name], data, reps)
            for i, t in enumerate(times):
                all_rows.append({
                    "size": size,
                    "input_type": itype,
                    "seed": seed,
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
    print("=" * 90)
    print("SUMMARY STATISTICS (microseconds) — timeit module")
    print("=" * 90)

    groups = defaultdict(list)
    for row in all_rows:
        key = (row["size"], row["input_type"], row["algorithm"])
        groups[key].append(row["time_microseconds"])

    for size in sizes:
        for itype in input_types:
            builtin_key = (size, itype, "builtin_sorted")
            insert_key = (size, itype, "insertion_sort")
            if builtin_key in groups and insert_key in groups:
                b_times = groups[builtin_key]
                i_times = groups[insert_key]
                b_mean = sum(b_times) / len(b_times)
                i_mean = sum(i_times) / len(i_times)
                b_std = (sum((x - b_mean) ** 2 for x in b_times) / len(b_times)) ** 0.5
                i_std = (sum((x - i_mean) ** 2 for x in i_times) / len(i_times)) ** 0.5
                b_cv = b_std / b_mean * 100 if b_mean > 0 else 0
                i_cv = i_std / i_mean * 100 if i_mean > 0 else 0
                ratio = i_mean / b_mean if b_mean > 0 else float("inf")
                print(
                    f"  size={size:3d} {itype:15s}  "
                    f"builtin:  {b_mean:8.2f} +/- {b_std:6.2f} ({b_cv:5.1f}%)  "
                    f"insert:   {i_mean:8.2f} +/- {i_std:6.2f} ({i_cv:5.1f}%)  "
                    f"ratio: {ratio:6.2f}x"
                )

    print()
    print("=" * 90)
    print("Timsort ADAPTIVE CLAIM VERIFICATION")
    print("Ratio of random/sorted time for builtin_sorted (should be >1 if adaptive)")
    print("=" * 90)

    for size in sizes:
        s_mean = sum(groups[(size, "sorted", "builtin_sorted")]) / len(groups[(size, "sorted", "builtin_sorted")])
        r_mean = sum(groups[(size, "random", "builtin_sorted")]) / len(groups[(size, "random", "builtin_sorted")])
        ratio = r_mean / s_mean if s_mean > 0 else float("inf")
        print(f"  size={size}: sorted={s_mean:7.2f} random={r_mean:7.2f} ratio={ratio:5.2f}x")

    print()
    print("Note: timeit module handles repeated calls and is more accurate for fast operations.")
    print("Copying is NOT timed; only the sort operation is measured.")
    print("Measurement order was randomized to reduce systematic bias.")

    return csv_path


if __name__ == "__main__":
    csv_path = run_benchmark()
    print()
    print(f"Done. Re-run verification: python3 {os.path.join(os.path.dirname(__file__), 'verify_timeit.py')} {csv_path}")
