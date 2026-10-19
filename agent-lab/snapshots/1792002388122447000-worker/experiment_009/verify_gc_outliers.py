"""
Verify experiment_009 from raw CSV data.
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

    # Group by (size, input_type, algorithm, gc_mode)
    groups = defaultdict(list)
    for row in rows:
        key = (int(row["size"]), row["input_type"], row["algorithm"], row["gc_mode"])
        groups[key].append(float(row["time_microseconds"]))

    sizes = sorted(set(int(r["size"]) for r in rows))
    input_types = sorted(set(r["input_type"] for r in rows))

    print("=" * 80)
    print("VERIFIED SUMMARY STATISTICS (microseconds)")
    print("=" * 80)

    for size in sizes:
        for itype in input_types:
            print(f"\n  Size={size}, Input={itype}")
            print(f"  {'GC Mode':>12s}  {'Algo':>15s}  {'Mean':>8s}  {'Median':>8s}  {'Std':>8s}  {'CV':>6s}  {'Min':>8s}  {'Max':>8s}  {'Outliers':>10s}")
            for algo_name in ["builtin_sorted", "insertion_sort"]:
                for gc_mode in ["disabled", "enabled", "collect"]:
                    key = (size, itype, algo_name, gc_mode)
                    if key in groups:
                        times = groups[key]
                        mean_t = sum(times) / len(times)
                        sorted_t = sorted(times)
                        median_t = sorted_t[len(sorted_t) // 2]
                        std_t = (sum((x - mean_t) ** 2 for x in times) / len(times)) ** 0.5
                        cv_t = (std_t / mean_t * 100) if mean_t > 0 else 0
                        min_t = sorted_t[0]
                        max_t = sorted_t[-1]
                        iqr = sorted_t[int(len(sorted_t) * 0.75)] - sorted_t[int(len(sorted_t) * 0.25)]
                        upper_fence = sorted_t[int(len(sorted_t) * 0.75)] + 3 * iqr
                        outlier_count = sum(1 for t in times if t > upper_fence)
                        print(f"  {gc_mode:>12s}  {algo_name:>15s}  {mean_t:>8.2f}  {median_t:>8.2f}  {std_t:>8.2f}  {cv_t:>5.1f}%  {min_t:>8.2f}  {max_t:>8.2f}  {outlier_count:>10d}")

    print()
    print("Verification complete.")


if __name__ == "__main__":
    main()
