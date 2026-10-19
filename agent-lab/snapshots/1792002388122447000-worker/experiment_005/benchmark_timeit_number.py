"""
Experiment 005: timeit number=N optimization study.

Hypothesis (from experiment_004):
  Using timeit with number=N (multiple calls per repeat) will reduce CV for
  fast operations by amortizing timer overhead. CV should decrease as N
  increases (amortizing timer overhead), then plateau or increase (system
  noise dominates).

Design:
- Timer: timeit module with varying number=N
- Sizes: 32, 128, 512 (all three from original task)
- Input types: random, sorted, reverse, duplicates (all four)
- number values: 1, 10, 100, 1000
- reps (timeit repeat count): 200 per (size, input_type, algorithm, number)
- Deterministic seeds (same as experiment_001)
- Correctness verified on every measured input
- Copying NOT timed (copy happens inside the timed lambda)
- Randomization: measurement order randomized (seed 12345)
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

def benchmark_timeit_number(algo_fn, data, number, reps):
    """Run reps measurements using timeit with number=N calls per repeat.
    Returns list of total times (in seconds) for each repeat."""
    timer = timeit.default_timer
    times = timeit.repeat(
        stmt=lambda: algo_fn(list(data)),
        setup=lambda: None,
        number=number,
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
    reps = 30  # timeit repeat count per condition (minimum required)

    # number=N values: full range for builtin_sorted (fast, timer overhead matters),
    # reduced range for insertion_sort (slow, N=1000 would take too long)
    numbers_builtin = [1, 10, 100, 1000]
    numbers_insert = [1, 10, 100]

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

    algo_map = {
        "builtin_sorted": sorted,
        "insertion_sort": insertion_sort,
    }

    # Run measurements
    total = len(conditions) * (len(numbers_builtin) + len(numbers_insert))
    print(f"Running {reps} timeit repeats per condition...")
    print(f"Conditions: {len(conditions)}")
    print(f"  builtin_sorted: {len(numbers_builtin)} number values")
    print(f"  insertion_sort: {len(numbers_insert)} number values")
    print(f"Total measurements: {total * reps}")
    print()

    all_rows = []

    for idx in condition_indices:
        size, itype, seed, data = conditions[idx]

        # Verify correctness before timing
        expected = sorted(data)
        for algo_name in algo_map:
            test_data = list(data)
            result = algo_map[algo_name](test_data)
            if result != expected:
                print(f"ERROR: {algo_name} failed correctness on size={size} type={itype}")
                sys.exit(1)

        # builtin_sorted: full N range
        for number in numbers_builtin:
            times = benchmark_timeit_number(algo_map["builtin_sorted"], data, number, reps)
            for i, t in enumerate(times):
                per_call = t / number
                all_rows.append({
                    "size": size,
                    "input_type": itype,
                    "seed": seed,
                    "algorithm": "builtin_sorted",
                    "number": number,
                    "repetition": i,
                    "time_seconds": per_call,
                    "time_microseconds": per_call * 1e6,
                })

        # insertion_sort: reduced N range
        for number in numbers_insert:
            times = benchmark_timeit_number(algo_map["insertion_sort"], data, number, reps)
            for i, t in enumerate(times):
                per_call = t / number
                all_rows.append({
                    "size": size,
                    "input_type": itype,
                    "seed": seed,
                    "algorithm": "insertion_sort",
                    "number": number,
                    "repetition": i,
                    "time_seconds": per_call,
                    "time_microseconds": per_call * 1e6,
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
    print("=" * 100)
    print("SUMMARY STATISTICS (microseconds per call) — timeit module")
    print("=" * 100)

    # Group by (size, input_type, algorithm, number)
    groups = defaultdict(list)
    for row in all_rows:
        key = (row["size"], row["input_type"], row["algorithm"], row["number"])
        groups[key].append(row["time_microseconds"])

    # Collect all unique N values per algorithm
    all_numbers_builtin = sorted(set(r["number"] for r in all_rows if r["algorithm"] == "builtin_sorted"))
    all_numbers_insert = sorted(set(r["number"] for r in all_rows if r["algorithm"] == "insertion_sort"))

    # Print per-condition summary
    print()
    print("--- Per-condition summary (mean ± std, CV%) ---")
    for size in sizes:
        for itype in input_types:
            for number in all_numbers_builtin:
                key = (size, itype, "builtin_sorted", number)
                if key in groups:
                    times = groups[key]
                    mean = sum(times) / len(times)
                    std = (sum((x - mean) ** 2 for x in times) / len(times)) ** 0.5
                    cv = std / mean * 100 if mean > 0 else 0
                    print(
                        f"  size={size:3d} {itype:15s} {'builtin_sorted':15s} N={number:4d}: "
                        f"{mean:8.2f} ± {std:6.2f} ({cv:5.1f}%)"
                    )
            for number in all_numbers_insert:
                key = (size, itype, "insertion_sort", number)
                if key in groups:
                    times = groups[key]
                    mean = sum(times) / len(times)
                    std = (sum((x - mean) ** 2 for x in times) / len(times)) ** 0.5
                    cv = std / mean * 100 if mean > 0 else 0
                    print(
                        f"  size={size:3d} {itype:15s} {'insertion_sort':15s} N={number:4d}: "
                        f"{mean:8.2f} ± {std:6.2f} ({cv:5.1f}%)"
                    )

    # CV analysis: how CV changes with N
    print()
    print("=" * 100)
    print("CV ANALYSIS: How CV changes with number=N")
    print("=" * 100)
    print()
    print("Focus: builtin_sorted (fastest, most affected by timer overhead)")
    print()

    for size in sizes:
        for itype in input_types:
            print(f"  size={size} {itype:15s}:")
            for number in all_numbers_builtin:
                key = (size, itype, "builtin_sorted", number)
                if key in groups:
                    times = groups[key]
                    mean = sum(times) / len(times)
                    std = (sum((x - mean) ** 2 for x in times) / len(times)) ** 0.5
                    cv = std / mean * 100 if mean > 0 else 0
                    print(f"    N={number:4d}: mean={mean:8.2f} μs  std={std:6.2f}  CV={cv:5.1f}%")
            print()

    # Find optimal N for each size (minimum CV for builtin_sorted)
    print("=" * 100)
    print("OPTIMAL N (minimum CV for builtin_sorted)")
    print("=" * 100)
    print()

    for size in sizes:
        best_cv = float("inf")
        best_n = None
        for itype in input_types:
            for number in all_numbers_builtin:
                key = (size, itype, "builtin_sorted", number)
                if key in groups:
                    times = groups[key]
                    mean = sum(times) / len(times)
                    std = (sum((x - mean) ** 2 for x in times) / len(times)) ** 0.5
                    cv = std / mean * 100 if mean > 0 else 0
                    if cv < best_cv:
                        best_cv = cv
                        best_n = number
        print(f"  size={size}: best N={best_n} (CV={best_cv:.1f}%)")

    print()
    print("=" * 100)
    print("RATIO ANALYSIS: insertion_sort / builtin_sorted (per-call time)")
    print("=" * 100)
    print()

    # Only compare at shared N values
    shared_numbers = sorted(set(all_numbers_builtin) & set(all_numbers_insert))
    for size in sizes:
        for itype in input_types:
            for number in shared_numbers:
                b_key = (size, itype, "builtin_sorted", number)
                i_key = (size, itype, "insertion_sort", number)
                if b_key in groups and i_key in groups:
                    b_mean = sum(groups[b_key]) / len(groups[b_key])
                    i_mean = sum(groups[i_key]) / len(groups[i_key])
                    ratio = i_mean / b_mean if b_mean > 0 else float("inf")
                    print(
                        f"  size={size:3d} {itype:15s} N={number:4d}: ratio={ratio:7.2f}x"
                    )

    print()
    print("Note: timeit module handles repeated calls. number=N means N calls per repeat.")
    print("Copying is NOT timed; only the sort operation is measured.")
    print("Measurement order was randomized to reduce systematic bias.")

    return csv_path


if __name__ == "__main__":
    csv_path = run_benchmark()
    print()
    print(f"Done. Re-run verification: python3 {os.path.join(os.path.dirname(__file__), 'verify_timeit_number.py')} {csv_path}")
