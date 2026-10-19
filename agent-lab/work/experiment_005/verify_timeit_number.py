"""
Experiment 005: Verify timeit number=N optimization results from raw CSV.

Reads measurements.csv and recomputes summary statistics to confirm they match
the benchmark output.
"""
import csv
import os
import sys
from collections import defaultdict


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify_timeit_number.py <csv_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    # Read CSV
    rows = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["size"] = int(row["size"])
            row["number"] = int(row["number"])
            row["repetition"] = int(row["repetition"])
            row["time_microseconds"] = float(row["time_microseconds"])
            rows.append(row)

    print(f"Read {len(rows)} rows from {csv_path}")
    print()

    # Group by (size, input_type, algorithm, number)
    groups = defaultdict(list)
    for row in rows:
        key = (row["size"], row["input_type"], row["algorithm"], row["number"])
        groups[key].append(row["time_microseconds"])

    # Verify row counts per group
    print("--- Row count verification ---")
    expected_reps = 30
    for key in sorted(groups.keys()):
        size, itype, algo, number = key
        count = len(groups[key])
        status = "OK" if count == expected_reps else "MISMATCH"
        print(f"  size={size:3d} {itype:15s} {algo:15s} N={number:4d}: {count} rows [{status}]")
    print()

    # Recompute summary statistics
    print("--- Recomputed summary statistics (microseconds per call) ---")
    print()

    all_numbers_builtin = sorted(set(r["number"] for r in rows if r["algorithm"] == "builtin_sorted"))
    all_numbers_insert = sorted(set(r["number"] for r in rows if r["algorithm"] == "insertion_sort"))

    sizes = sorted(set(r["size"] for r in rows))
    input_types = sorted(set(r["input_type"] for r in rows))

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

    print()

    # Verify optimal N
    print("--- Optimal N verification ---")
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

    # Check for decreasing mean trend (warm-up / caching effect)
    print("--- Warm-up / caching effect check (builtin_sorted) ---")
    for size in sizes:
        for itype in input_types:
            means = []
            for number in all_numbers_builtin:
                key = (size, itype, "builtin_sorted", number)
                if key in groups:
                    times = groups[key]
                    mean = sum(times) / len(times)
                    means.append((number, mean))
            if len(means) >= 2:
                decreasing = all(means[i][1] >= means[i+1][1] for i in range(len(means)-1))
                if decreasing:
                    print(f"  WARNING: size={size} {itype}: mean DECREASES with N (possible warm-up/caching)")
                    for n, m in means:
                        print(f"    N={n}: {m:.2f} μs")

    print()
    print("Verification complete.")


if __name__ == "__main__":
    main()
