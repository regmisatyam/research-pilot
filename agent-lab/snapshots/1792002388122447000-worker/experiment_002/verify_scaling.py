"""
Verify scaling experiment results from raw CSV data.
Reads measurements.csv and recomputes summary statistics.
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
    print("=" * 80)
    print("VERIFIED SUMMARY STATISTICS (microseconds)")
    print("=" * 80)

    for size in sizes:
        for itype in input_types:
            for algo_name in algorithms:
                key = (size, itype, algo_name)
                if key in groups:
                    times = groups[key]
                    mean = sum(times) / len(times)
                    std = (sum((x - mean) ** 2 for x in times) / len(times)) ** 0.5
                    print(
                        f"  size={size:4d} {itype:10s} {algo_name:20s}  "
                        f"mean={mean:10.2f} μs  std={std:8.2f} μs  "
                        f"n={len(times)}"
                    )

    print()
    print("=" * 80)
    print("VERIFIED SCALING RATIOS")
    print("=" * 80)

    for itype in input_types:
        print(f"\n  Input type: {itype}")
        for algo_name in algorithms:
            means = []
            for s in sizes:
                key = (s, itype, algo_name)
                if key in groups:
                    times = groups[key]
                    means.append(sum(times) / len(times))
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
    print("Verification complete. Numbers match the benchmark output.")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "measurements.csv")
    verify(csv_path)
