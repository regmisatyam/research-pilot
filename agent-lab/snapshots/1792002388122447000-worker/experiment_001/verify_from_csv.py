"""
Verify report numbers from raw CSV data.
Reads measurements.csv and prints summary statistics.
Usage: python3 verify_from_csv.py [path_to_csv]
"""
import csv
import os
import sys
from collections import defaultdict


def main():
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = os.path.join(os.path.dirname(__file__), "measurements.csv")

    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found. Run benchmark.py first.")
        sys.exit(1)

    print(f"Verifying from: {csv_path}")
    print(f"File size: {os.path.getsize(csv_path)} bytes")
    print()

    # Read all rows
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Total rows: {len(rows)}")
    print(f"Columns: {list(rows[0].keys())}")
    print()

    # Group by (size, input_type, algorithm)
    groups = defaultdict(list)
    for row in rows:
        key = (int(row["size"]), row["input_type"], row["algorithm"])
        groups[key].append(float(row["time_microseconds"]))

    sizes = sorted(set(k[0] for k in groups.keys()))
    input_types = sorted(set(k[1] for k in groups.keys()))
    algorithms = sorted(set(k[2] for k in groups.keys()))

    print("=" * 80)
    print("VERIFICATION: Summary Statistics from Raw CSV (microseconds)")
    print("=" * 80)
    print()

    for size in sizes:
        for itype in input_types:
            for algo in algorithms:
                key = (size, itype, algo)
                if key not in groups:
                    continue
                times = groups[key]
                n = len(times)
                mean = sum(times) / n
                variance = sum((x - mean) ** 2 for x in times) / n
                std = variance ** 0.5
                mn = min(times)
                mx = max(times)
                sorted_t = sorted(times)
                median = sorted_t[n // 2]
                if n % 2 == 0:
                    median = (sorted_t[n // 2 - 1] + sorted_t[n // 2]) / 2

                print(
                    f"  size={size:3d} {itype:15s} {algo:18s}  "
                    f"n={n:3d}  mean={mean:8.2f}  std={std:6.2f}  "
                    f"median={median:8.2f}  min={mn:6.2f}  max={mx:6.2f}"
                )

    print()
    print("=" * 80)
    print("Cross-algorithm ratios (insertion_sort / builtin_sorted)")
    print("=" * 80)
    print()

    for size in sizes:
        for itype in input_types:
            insert_key = (size, itype, "insertion_sort")
            builtin_key = (size, itype, "builtin_sorted")
            if insert_key in groups and builtin_key in groups:
                i_mean = sum(groups[insert_key]) / len(groups[insert_key])
                b_mean = sum(groups[builtin_key]) / len(groups[builtin_key])
                ratio = i_mean / b_mean if b_mean > 0 else float("inf")
                print(
                    f"  size={size:3d} {itype:15s}  ratio={ratio:6.2f}x  "
                    f"(insert={i_mean:8.2f} μs, builtin={b_mean:8.2f} μs)"
                )

    print()
    print("Verification complete.")


if __name__ == "__main__":
    main()
