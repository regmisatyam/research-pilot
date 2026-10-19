"""
Scaling analysis: sorted() vs insertion_sort() at sizes 16, 64, 256, 1024, 4096.

Hypothesis (from experiment_001 follow-up):
  - Reverse-sorted insertion sort scales as O(n²):
    ratio of ~16× between consecutive sizes (factor-4 increase → 4² = 16×).
  - Sorted insertion sort scales as O(n):
    ratio of ~4× between consecutive sizes (factor-4 increase → 4¹ = 4×).
  - sorted() (Timsort) scales close to O(n) for both:
    ratio of ~4× between consecutive sizes.

Design:
- Sizes: 16, 64, 256, 1024, 4096 (factor-4 steps)
- Input types: sorted, reverse-sorted (the two extremes)
- Repetitions: 100 per condition
- Deterministic seeds recorded
- Correctness verified on every measured input
- Measurement order randomized
- Copying NOT timed (copy happens before timing starts)
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
    if itype == "sorted":
        return sorted([rng.randint(-1000, 1000) for _ in range(size)])
    elif itype == "reverse":
        return sorted([rng.randint(-1000, 1000) for _ in range(size)], reverse=True)
    else:
        raise ValueError(f"Unknown input type: {itype}")


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------

def benchmark_one(algo_fn, data, reps):
    """Run reps measurements for one algorithm on one input.
    Returns list of elapsed times in seconds."""
    times = []
    for _ in range(reps):
        # Copy input BEFORE timing starts -- copy is NOT timed
        data_copy = list(data)
        start = time.perf_counter()
        result = algo_fn(data_copy)
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
    sizes = [16, 64, 256, 1024, 4096]
    input_types = ["sorted", "reverse"]
    seeds = {"sorted": 1, "reverse": 1}
    reps = 100  # repetitions per condition

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

        for algo_name in algo_map:
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
    print("=" * 80)
    print("SUMMARY STATISTICS (microseconds)")
    print("=" * 80)

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
                    f"  size={size:4d} {itype:10s}  "
                    f"builtin:  {b_mean:10.2f} ± {b_std:8.2f} μs  "
                    f"insert:   {i_mean:10.2f} ± {i_std:8.2f} μs  "
                    f"ratio(i/b): {ratio:8.2f}x"
                )

    print()
    print("=" * 80)
    print("SCALING RATIOS (mean time / mean time at previous size)")
    print("=" * 80)

    # Compute scaling ratios between consecutive sizes
    for itype in input_types:
        print(f"\n  Input type: {itype}")
        print(f"  {'Algorithm':20s}  ", end="")
        for i, s in enumerate(sizes):
            label = f"s={s}"
            if i == 0:
                print(f"{label:>8s}", end="")
            else:
                print(f"  ratio({s}/{sizes[i-1]})>8s", end="")
        print()

        for algo_name in ["builtin_sorted", "insertion_sort"]:
            means = []
            for s in sizes:
                key = (s, itype, algo_name)
                if key in groups:
                    means.append(sum(groups[key]) / len(groups[key]))
                else:
                    means.append(0)

            print(f"  {algo_name:20s}  ", end="")
            for i, m in enumerate(means):
                if i == 0:
                    print(f"{m:8.2f}", end="")
                else:
                    ratio = m / means[i-1] if means[i-1] > 0 else float("inf")
                    print(f"  {ratio:8.2f}x", end="")
            print()

    print()
    print("Note: ratio > 1 means slower at larger size.")
    print("For O(n²) scaling with factor-4 size increase: expected ratio ≈ 16×")
    print("For O(n) scaling with factor-4 size increase: expected ratio ≈ 4×")
    print("Copying is NOT timed; only the sort operation is measured.")
    print("Measurement order was randomized to reduce systematic bias.")

    return csv_path


if __name__ == "__main__":
    csv_path = run_benchmark()
    print()
    print(f"Done. Re-run verification: python3 {os.path.join(os.path.dirname(__file__), 'verify_scaling.py')} {csv_path}")
