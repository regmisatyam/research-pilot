"""
Main benchmarking script: sorted() vs insertion_sort() for small integer lists.

Design decisions:
- Timer: time.perf_counter() (highest resolution available)
- Copying: NOT timed. Each sort receives a fresh copy of the input data.
  The copy happens BEFORE timing starts, so we measure sorting only.
- Randomization: Measurement order is randomized to avoid systematic bias
  (CPU frequency scaling, background processes, thermal throttling).
- Repetitions: 50 per condition (exceeds the 30 minimum).
- Conditions: 3 sizes × 4 input types × 2 algorithms = 24 conditions.
- Deterministic seeds recorded for every input generation.
- Correctness verified on every measured input before timing.
"""
import csv
import os
import platform
import random
import sys
import time
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

def benchmark_one(algo_name, data, reps):
    """Run reps measurements for one algorithm on one input.
    Returns list of elapsed times in seconds."""
    times = []
    for _ in range(reps):
        # Copy input BEFORE timing starts -- copy is NOT timed
        data_copy = list(data)
        start = time.perf_counter()
        result = algo_name(data_copy)
        end = time.perf_counter()
        times.append(end - start)
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
    reps = 50  # repetitions per condition

    # Build all conditions
    conditions = []
    for size in sizes:
        for itype in input_types:
            seed = seeds[itype]
            data = generate_input(itype, size, seed)
            conditions.append((size, itype, seed, data))

    # Randomize measurement order (shuffle conditions)
    rng_order = random.Random(12345)  # fixed seed for reproducibility of order
    condition_indices = list(range(len(conditions)))
    rng_order.shuffle(condition_indices)

    # Run measurements
    print(f"Running {reps} repetitions per condition...")
    print(f"Total conditions: {len(conditions)} × 2 algorithms = {len(conditions) * 2}")
    print(f"Total measurements: {len(conditions) * 2 * reps}")
    print()

    all_rows = []
    algo_map = {
        "builtin_sorted": sorted,
        "insertion_sort": insertion_sort,
    }
    algo_names = list(algo_map.keys())

    for idx in condition_indices:
        size, itype, seed, data = conditions[idx]

        # Verify correctness before timing
        expected = sorted(data)
        for algo_name in algo_names:
            test_data = list(data)
            result = algo_map[algo_name](test_data)
            if result != expected:
                print(f"ERROR: {algo_name} failed correctness on size={size} type={itype}")
                sys.exit(1)

        for algo_name in algo_names:
            times = benchmark_one(algo_map[algo_name], data, reps)
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
    print("=" * 70)
    print("SUMMARY STATISTICS (microseconds)")
    print("=" * 70)

    # Group by (size, input_type, algorithm)
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
                ratio = i_mean / b_mean if b_mean > 0 else float("inf")
                print(
                    f"  size={size:3d} {itype:15s}  "
                    f"builtin:  {b_mean:8.2f} ± {b_std:6.2f} μs  "
                    f"insert:   {i_mean:8.2f} ± {i_std:6.2f} μs  "
                    f"ratio(i/b): {ratio:6.2f}x"
                )

    print()
    print("Note: ratio > 1 means insertion_sort is slower than builtin_sorted.")
    print("Copying is NOT timed; only the sort operation is measured.")
    print("Measurement order was randomized to reduce systematic bias.")

    return csv_path


if __name__ == "__main__":
    csv_path = run_benchmark()
    print()
    print(f"Done. Re-run: python3 {os.path.join(os.path.dirname(__file__), 'verify_from_csv.py')} {csv_path}")
