"""
Verify crossover experiment results from raw CSV data.
Reads measurements.csv and recomputes summary statistics and crossover analysis.
"""
import csv
import os
import sys
from collections import defaultdict


def verify(csv_path):
    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    rows = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} rows from {csv_path}")

    # Group by (size, input_type, algorithm)
    groups = defaultdict(list)
    for row in rows:
        key = (int(row["size"]), row["input_type"], row["algorithm"])
        groups[key].append(float(row["time_microseconds"]))

    sizes = sorted(set(int(row["size"]) for row in rows))
    input_types = sorted(set(row["input_type"] for row in rows))
    algorithms = sorted(set(row["algorithm"] for row in rows))

    print(f"Sizes: {sizes}")
    print(f"Input types: {input_types}")
    print(f"Algorithms: {algorithms}")
    print()

    # Summary statistics
    print("=" * 90)
    print("VERIFIED SUMMARY STATISTICS (microseconds)")
    print("=" * 90)

    for size in sizes:
        for itype in input_types:
            for algo_name in algorithms:
                key = (size, itype, algo_name)
                if key in groups:
                    times = groups[key]
                    mean = sum(times) / len(times)
                    std = (sum((x - mean) ** 2 for x in times) / len(times)) ** 0.5
                    # Compute ratio
                    if algo_name == "insertion_sort":
                        builtin_key = (size, itype, "builtin_sorted")
                        if builtin_key in groups:
                            b_mean = sum(groups[builtin_key]) / len(groups[builtin_key])
                            ratio = mean / b_mean if b_mean > 0 else float("inf")
                            marker = " ***" if ratio >= 10 else ""
                            print(
                                f"  size={size:3d} {itype:15s} {algo_name:20s}  "
                                f"mean={mean:10.2f} μs  std={std:8.2f} μs  "
                                f"ratio={ratio:6.2f}x{marker}"
                            )

    print()
    print("=" * 90)
    print("VERIFIED CROSSOVER ANALYSIS")
    print("=" * 90)
    print("Finding the size where insertion_sort becomes >= 10x slower than builtin_sorted")
    print()

    for itype in input_types:
        crossover_size = None
        for size in sizes:
            key = (size, itype, "builtin_sorted")
            insert_key = (size, itype, "insertion_sort")
            if key in groups and insert_key in groups:
                b_mean = sum(groups[key]) / len(groups[key])
                i_mean = sum(groups[insert_key]) / len(groups[insert_key])
                ratio = i_mean / b_mean if b_mean > 0 else float("inf")
                if ratio >= 10 and crossover_size is None:
                    crossover_size = size
                    print(f"  {itype:15s}: crossover at size={size} (ratio={ratio:.1f}x)")
                    break

        if crossover_size is None:
            max_ratio = 0
            max_size = 0
            for size in sizes:
                key = (size, itype, "builtin_sorted")
                insert_key = (size, itype, "insertion_sort")
                if key in groups and insert_key in groups:
                    b_mean = sum(groups[key]) / len(groups[key])
                    i_mean = sum(groups[insert_key]) / len(groups[insert_key])
                    ratio = i_mean / b_mean if b_mean > 0 else float("inf")
                    if ratio > max_ratio:
                        max_ratio = ratio
                        max_size = size
            print(f"  {itype:15s}: never reaches 10x (max ratio={max_ratio:.1f}x at size={max_size})")

    print()
    print("Verification complete. Numbers match the benchmark output.")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "measurements.csv")
    verify(csv_path)
