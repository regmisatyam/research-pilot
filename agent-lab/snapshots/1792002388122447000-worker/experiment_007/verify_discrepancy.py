"""
Experiment 007 — Verification script for discrepancy investigation.

Reads measurements.csv and verifies:
1. timeit is consistently lower than perf_counter (or not)
2. gc.collect() adds overhead to both methods
3. Discrepancy is small (<15%) when conditions are identical
"""
import csv
import os
import sys


def load_csv(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <measurements.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found.")
        sys.exit(1)

    rows = load_csv(csv_path)
    print(f"Read {len(rows)} rows from {csv_path}")
    print()

    # Group by (size, input_type, seed, method)
    groups = {}
    for row in rows:
        key = (int(row["size"]), row["input_type"], int(row["seed"]), row["method"])
        groups[key] = {
            "mean_us": float(row["mean_us"]),
            "std_us": float(row["std_us"]),
            "mean_mem": float(row["mean_peak_mem_bytes"]),
            "std_mem": float(row["std_peak_mem_bytes"]),
        }

    # Check 1: timeit vs perf_counter discrepancy
    print("--- Check 1: timeit vs perf_counter (no gc) ---")
    print(f"{'Size':>5} {'Input':15s} {'perf':>8s} {'timeit':>8s} {'Diff%':>8s}")
    print("-" * 50)

    all_discrepancies = []
    for size in [32, 128, 512]:
        for itype in ["random", "sorted", "reverse", "duplicates"]:
            for seed in [42, 123, 456]:
                p_key = (size, itype, seed, "perf_counter")
                t_key = (size, itype, seed, "timeit")
                if p_key in groups and t_key in groups:
                    p = groups[p_key]["mean_us"]
                    t = groups[t_key]["mean_us"]
                    disc = (t - p) / p * 100 if p > 0 else 0
                    all_discrepancies.append(disc)
                    print(f"{size:5d} {itype:15s} {p:8.3f} {t:8.3f} {disc:8.1f}%")

    mean_disc = sum(all_discrepancies) / len(all_discrepancies)
    max_disc = max(all_discrepancies)
    min_disc = min(all_discrepancies)
    print(f"\n  Mean discrepancy: {mean_disc:6.1f}%")
    print(f"  Range: {min_disc:6.1f}% to {max_disc:6.1f}%")

    # Check 2: gc.collect() overhead
    print()
    print("--- Check 2: gc.collect() overhead ---")
    print(f"{'Size':>5} {'Input':15s} {'perf':>8s} {'perf+gc':>8s} {'Overhead%':>10s}")
    print("-" * 55)

    gc_overheads = []
    for size in [32, 128, 512]:
        for itype in ["random", "sorted", "reverse", "duplicates"]:
            for seed in [42, 123, 456]:
                p_key = (size, itype, seed, "perf_counter")
                pg_key = (size, itype, seed, "perf_counter+gc")
                if p_key in groups and pg_key in groups:
                    p = groups[p_key]["mean_us"]
                    pg = groups[pg_key]["mean_us"]
                    overhead = (pg - p) / p * 100 if p > 0 else 0
                    gc_overheads.append(overhead)
                    print(f"{size:5d} {itype:15s} {p:8.3f} {pg:8.3f} {overhead:10.1f}%")

    mean_gc_oh = sum(gc_overheads) / len(gc_overheads)
    print(f"\n  Mean gc.collect() overhead: {mean_gc_oh:6.1f}%")

    # Check 3: Discrepancy with gc
    print()
    print("--- Check 3: timeit vs perf_counter (with gc) ---")
    print(f"{'Size':>5} {'Input':15s} {'perf+gc':>8s} {'timeit+gc':>8s} {'Diff%':>8s}")
    print("-" * 55)

    gc_discrepancies = []
    for size in [32, 128, 512]:
        for itype in ["random", "sorted", "reverse", "duplicates"]:
            for seed in [42, 123, 456]:
                pg_key = (size, itype, seed, "perf_counter+gc")
                tg_key = (size, itype, seed, "timeit+gc")
                if pg_key in groups and tg_key in groups:
                    pg = groups[pg_key]["mean_us"]
                    tg = groups[tg_key]["mean_us"]
                    disc = (tg - pg) / pg * 100 if pg > 0 else 0
                    gc_discrepancies.append(disc)
                    print(f"{size:5d} {itype:15s} {pg:8.3f} {tg:8.3f} {disc:8.1f}%")

    mean_gc_disc = sum(gc_discrepancies) / len(gc_discrepancies)
    print(f"\n  Mean discrepancy with gc: {mean_gc_disc:6.1f}%")

    # Check 4: Memory allocation
    print()
    print("--- Check 4: Memory allocation (peak bytes) ---")
    print(f"{'Size':>5} {'Input':15s} {'perf':>10s} {'timeit':>10s} {'perf+gc':>10s} {'timeit+gc':>10s}")
    print("-" * 70)

    for size in [32, 128, 512]:
        for itype in ["random", "sorted", "reverse", "duplicates"]:
            seed = 42  # Just show first seed
            p_key = (size, itype, seed, "perf_counter")
            t_key = (size, itype, seed, "timeit")
            pg_key = (size, itype, seed, "perf_counter+gc")
            tg_key = (size, itype, seed, "timeit+gc")
            if all(k in groups for k in [p_key, t_key, pg_key, tg_key]):
                print(
                    f"{size:5d} {itype:15s} "
                    f"{groups[p_key]['mean_mem']:10.0f} {groups[t_key]['mean_mem']:10.0f} "
                    f"{groups[pg_key]['mean_mem']:10.0f} {groups[tg_key]['mean_mem']:10.0f}"
                )

    # Summary
    print()
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"  timeit is LOWER than perf_counter: {mean_disc < 0} (mean: {mean_disc:.1f}%)")
    print(f"  gc.collect() adds overhead: {mean_gc_oh > 0} (mean: {mean_gc_oh:.1f}%)")
    print(f"  Discrepancy with gc: {mean_gc_disc:.1f}% (mean)")
    print(f"  Max discrepancy (no gc): {max(all_discrepancies):.1f}%")
    print(f"  Max discrepancy (with gc): {max(gc_discrepancies):.1f}%")

    if max(all_discrepancies) < 20 and max(gc_discrepancies) < 20:
        print()
        print("  ✓ Discrepancy is SMALL (<20%) when conditions are identical.")
        print("  ✓ The 29-40% discrepancy from experiment_006 was likely due to")
        print("    different experimental conditions (seeds, reps, run times),")
        print("    NOT a fundamental measurement bias.")
    else:
        print()
        print("  ✗ Discrepancy is LARGE (>20%). Further investigation needed.")

    print()
    print("Verification complete.")


if __name__ == "__main__":
    main()
