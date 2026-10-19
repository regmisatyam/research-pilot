"""
Verify experiment_008 from raw CSV data.
"""
import csv
import sys
from collections import defaultdict


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <csv_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    print(f"Verifying from: {csv_path}")

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Total rows: {len(rows)}")
    print(f"Columns: {list(rows[0].keys())}")
    print()

    # Group by (size, disorder_pct, algorithm)
    groups = defaultdict(list)
    for row in rows:
        key = (int(row["size"]), int(row["disorder_pct"]), row["algorithm"])
        groups[key].append(float(row["time_microseconds"]))

    sizes = sorted(set(int(r["size"]) for r in rows))
    disorder_levels = sorted(set(int(r["disorder_pct"]) for r in rows))

    print("=" * 80)
    print("VERIFIED SUMMARY STATISTICS (microseconds)")
    print("=" * 80)

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
    print("Verification complete.")


if __name__ == "__main__":
    main()
