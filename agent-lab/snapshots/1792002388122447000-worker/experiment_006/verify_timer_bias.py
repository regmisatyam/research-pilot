"""
Experiment 006 — Verification script for timer bias analysis.

Reads corrected_times.csv and verifies:
1. All conditions have R² > 0.90 (model fit quality)
2. True times are positive
3. Overhead values are positive (N=1 should overestimate)
4. Recompute summary statistics from corrected data
"""
import csv
import os
import sys


def load_csv(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <corrected_times.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found.")
        sys.exit(1)

    rows = load_csv(csv_path)
    print(f"Read {len(rows)} rows from {csv_path}")
    print()

    # Check R² values
    print("--- Model fit quality ---")
    all_r2 = [float(r["r_squared"]) for r in rows]
    min_r2 = min(all_r2)
    max_r2 = max(all_r2)
    mean_r2 = sum(all_r2) / len(all_r2)
    print(f"  R² range: {min_r2:.4f} – {max_r2:.4f}")
    print(f"  R² mean:  {mean_r2:.4f}")

    low_r2 = sum(1 for r in all_r2 if r < 0.90)
    if low_r2 > 0:
        print(f"  WARNING: {low_r2} conditions with R² < 0.90")
        for r in rows:
            if float(r["r_squared"]) < 0.90:
                print(f"    size={r['size']} {r['input_type']} {r['algorithm']} R²={r['r_squared']}")
    else:
        print(f"  All conditions have R² ≥ 0.90 ✓")

    # Check true times are positive
    print()
    print("--- True time values ---")
    all_times = [float(r["true_time_us"]) for r in rows]
    min_time = min(all_times)
    max_time = max(all_times)
    print(f"  True time range: {min_time:.3f} – {max_time:.3f} μs")
    if min_time <= 0:
        print(f"  ERROR: Non-positive true time found!")
        for r in rows:
            if float(r["true_time_us"]) <= 0:
                print(f"    size={r['size']} {r['input_type']} {r['algorithm']}")
    else:
        print(f"  All true times positive ✓")

    # Check overhead values
    print()
    print("--- Overhead values ---")
    all_overhead = [float(r["overhead_us"]) for r in rows]
    min_oh = min(all_overhead)
    max_oh = max(all_overhead)
    print(f"  Overhead range: {min_oh:.3f} – {max_oh:.3f} μs")
    if min_oh < 0:
        print(f"  WARNING: Negative overhead found (model may not fit)")
        for r in rows:
            if float(r["overhead_us"]) < 0:
                print(f"    size={r['size']} {r['input_type']} {r['algorithm']}")
    else:
        print(f"  All overheads positive ✓ (N=1 overestimates)")

    # Summary by algorithm
    print()
    print("--- Summary by algorithm ---")
    algo_times = {}
    for r in rows:
        algo = r["algorithm"]
        if algo not in algo_times:
            algo_times[algo] = []
        algo_times[algo].append(float(r["true_time_us"]))

    for algo in sorted(algo_times):
        times = algo_times[algo]
        mean_t = sum(times) / len(times)
        min_t = min(times)
        max_t = max(times)
        print(f"  {algo}: mean={mean_t:.3f} μs  min={min_t:.3f} μs  max={max_t:.3f} μs  n={len(times)}")

    # Recompute ratios from corrected data
    print()
    print("--- Corrected ratios (insertion_sort / builtin_sorted) ---")
    lookup = {}
    for r in rows:
        key = (int(r["size"]), r["input_type"], r["algorithm"])
        lookup[key] = float(r["true_time_us"])

    for size in [32, 128, 512]:
        for itype in ["random", "sorted", "reverse", "duplicates"]:
            b_key = (size, itype, "builtin_sorted")
            i_key = (size, itype, "insertion_sort")
            if b_key in lookup and i_key in lookup:
                ratio = lookup[i_key] / lookup[b_key] if lookup[b_key] > 0 else float("inf")
                print(f"  size={size:3d} {itype:15s}: {ratio:7.1f}x")

    print()
    print("Verification complete.")


if __name__ == "__main__":
    main()
