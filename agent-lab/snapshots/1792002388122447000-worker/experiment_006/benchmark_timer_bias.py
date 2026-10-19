"""
Experiment 006 — Timer Overhead Bias Quantification and Correction

Hypothesis (from experiment_005):
  The timeit-measured per-call time follows the model:
    measured_time(N) = true_time + overhead/N
  where overhead is the fixed timeit overhead per repeat. By measuring at
  multiple N values and fitting this model, we can estimate the true time
  (overhead→0) and the overhead itself.

  This is a linear model in 1/N:
    measured_time = true_time + overhead × (1/N)

  We fit this model to experiment_005 data and extrapolate to N=∞ (1/N=0)
  to get corrected times. We then compare corrected times with experiment_001
  (perf_counter) measurements.

Design:
- Uses experiment_005 data (already collected)
- Fits linear model: time = a + b*(1/N) via least squares
- Extrapolates to N=∞ for corrected times
- Compares corrected times with experiment_001 perf_counter results
- Validates model by checking R² and residual patterns
- Python standard library only
"""
import csv
import os
import sys
from collections import defaultdict


def load_csv(path):
    """Load CSV and return list of dicts."""
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def linear_regression(x, y):
    """Simple least-squares linear regression: y = a + b*x.
    Returns (a, b, r_squared)."""
    n = len(x)
    if n < 2:
        return None, None, None

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return None, None, None

    b = (n * sum_xy - sum_x * sum_y) / denom
    a = (sum_y - b * sum_x) / n

    # R²
    mean_y = sum_y / n
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((yi - (a + b * xi)) ** 2 for xi, yi in zip(x, y))
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return a, b, r_squared


def run_analysis():
    # Look for experiment_005 data
    csv_path = os.path.join(os.path.dirname(__file__), "..", "experiment_005", "measurements.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found. Run experiment_005 first.")
        sys.exit(1)

    rows = load_csv(csv_path)
    print(f"Loaded {len(rows)} rows from experiment_005")

    # Platform info (from experiment_005)
    print()
    print("Platform: Python 3.13.15 / aarch64 Linux (from experiment_005)")
    print()

    # Group by (size, input_type, algorithm, N) and compute mean/std
    groups = defaultdict(list)
    for row in rows:
        key = (int(row["size"]), row["input_type"], row["algorithm"], int(row["number"]))
        t = float(row["time_microseconds"])
        groups[key].append(t)

    # Aggregate: mean and std per N within each condition
    aggregated = defaultdict(list)
    for (size, itype, algo, n), times in groups.items():
        mean_t = sum(times) / len(times)
        std_t = (sum((x - mean_t) ** 2 for x in times) / len(times)) ** 0.5
        aggregated[(size, itype, algo)].append((n, mean_t, std_t, len(times)))

    print("=" * 100)
    print("TIMER OVERHEAD BIAS MODEL: measured_time(N) = true_time + overhead/N")
    print("=" * 100)
    print()
    print("Note: Model fitted to MEANS within each N group (not individual points).")
    print("This reduces within-group noise and reveals the systematic trend.")
    print()

    # Fit model for each condition using aggregated means
    results = []
    for key in sorted(aggregated.keys()):
        size, itype, algo = key
        data = aggregated[key]

        # Sort by N
        data.sort(key=lambda x: x[0])

        # Extract x=1/N and y=mean_time
        x = [1.0 / n for n, mean_t, std_t, count in data]
        y = [mean_t for n, mean_t, std_t, count in data]

        a, b, r2 = linear_regression(x, y)
        if a is not None:
            results.append({
                "size": size,
                "input_type": itype,
                "algorithm": algo,
                "true_time": a,       # extrapolated to N=∞
                "overhead": b,        # overhead per repeat (in μs)
                "r_squared": r2,
                "n_points": sum(count for n, mean_t, std_t, count in data),
                "n_groups": len(data),
                "group_data": [(n, mean_t, std_t) for n, mean_t, std_t, count in data],
            })

    # Print model fits
    print("--- Model fits (per-call time in μs) ---")
    print()
    print(f"{'Size':>5} {'Input':15s} {'Algorithm':15s} {'True':>8s} {'Overhead':>10s} {'R²':>6s} {'Groups':>7s} {'Pts':>5s}")
    print("-" * 90)

    for r in results:
        print(
            f"{r['size']:5d} {r['input_type']:15s} {r['algorithm']:15s} "
            f"{r['true_time']:8.3f} {r['overhead']:10.3f} {r['r_squared']:6.4f} "
            f"{r['n_groups']:7d} {r['n_points']:5d}"
        )

    # Print group means for a sample condition
    print()
    print("--- Group means (sample: size=32, random, builtin_sorted) ---")
    for r in results:
        if r["size"] == 32 and r["input_type"] == "random" and r["algorithm"] == "builtin_sorted":
            for n, mean_t, std_t in r["group_data"]:
                print(f"    N={n:5d}: mean={mean_t:8.3f} μs  std={std_t:6.3f}  1/N={1.0/n:.6f}")
            break

    # Validate model: R² should be high if the model is correct
    print()
    print("=" * 100)
    print("MODEL VALIDATION")
    print("=" * 100)
    print()

    high_r2 = sum(1 for r in results if r["r_squared"] > 0.95)
    low_r2 = sum(1 for r in results if r["r_squared"] < 0.95)
    print(f"  R² > 0.95: {high_r2}/{len(results)} conditions")
    print(f"  R² < 0.95: {low_r2}/{len(results)} conditions")

    if low_r2 > 0:
        print()
        print("  Conditions with R² < 0.95:")
        for r in results:
            if r["r_squared"] < 0.95:
                print(
                    f"    size={r['size']} {r['input_type']:15s} {r['algorithm']:15s} R²={r['r_squared']:.4f}"
                )

    # Compare corrected times with experiment_001 (perf_counter)
    print()
    print("=" * 100)
    print("COMPARISON: Corrected timeit vs experiment_001 (perf_counter)")
    print("=" * 100)
    print()

    # Load experiment_001 data
    exp001_path = os.path.join(os.path.dirname(__file__), "..", "experiment_001", "measurements.csv")
    if os.path.exists(exp001_path):
        exp001_rows = load_csv(exp001_path)
        exp001_groups = defaultdict(list)
        for row in exp001_rows:
            key = (int(row["size"]), row["input_type"], row["algorithm"])
            t = float(row["time_microseconds"])
            exp001_groups[key].append(t)

        print(f"{'Size':>5} {'Input':15s} {'Algorithm':15s} {'Corrected':>10s} {'Exp001':>10s} {'Diff%':>8s}")
        print("-" * 70)

        for r in results:
            key = (r["size"], r["input_type"], r["algorithm"])
            if key in exp001_groups:
                exp001_mean = sum(exp001_groups[key]) / len(exp001_groups[key])
                diff_pct = (r["true_time"] - exp001_mean) / exp001_mean * 100 if exp001_mean > 0 else 0
                print(
                    f"{r['size']:5d} {r['input_type']:15s} {r['algorithm']:15s} "
                    f"{r['true_time']:10.3f} {exp001_mean:10.3f} {diff_pct:8.1f}%"
                )
    else:
        print(f"  experiment_001/measurements.csv not found at {exp001_path}")
        print("  Skipping comparison.")

    # Compare ratios: insertion_sort / builtin_sorted
    print()
    print("=" * 100)
    print("RATIO ANALYSIS: insertion_sort / builtin_sorted")
    print("=" * 100)
    print()

    # Build lookup for corrected times
    corrected = {}
    for r in results:
        key = (r["size"], r["input_type"], r["algorithm"])
        corrected[key] = r["true_time"]

    # Also get experiment_001 ratios
    exp001_ratios = {}
    for key in exp001_groups:
        size, itype, algo = key
        if algo == "insertion_sort":
            b_key = (size, itype, "builtin_sorted")
            if b_key in exp001_groups:
                i_mean = sum(exp001_groups[key]) / len(exp001_groups[key])
                b_mean = sum(exp001_groups[b_key]) / len(exp001_groups[b_key])
                exp001_ratios[key] = i_mean / b_mean if b_mean > 0 else float("inf")

    print(f"{'Size':>5} {'Input':15s} {'Corrected':>10s} {'Exp001':>10s} {'Diff%':>8s}")
    print("-" * 60)

    for key in sorted(exp001_ratios.keys()):
        size, itype, algo = key
        if (size, itype, "builtin_sorted") in corrected and algo == "insertion_sort":
            b_time = corrected[(size, itype, "builtin_sorted")]
            i_time = corrected[(size, itype, "insertion_sort")]
            ratio = i_time / b_time if b_time > 0 else float("inf")
            exp001_ratio = exp001_ratios[key]
            diff_pct = (ratio - exp001_ratio) / exp001_ratio * 100 if exp001_ratio > 0 else 0
            print(
                f"{size:5d} {itype:15s} {ratio:10.1f}x {exp001_ratio:10.1f}x {diff_pct:8.1f}%"
            )

    # Residual analysis
    print()
    print("=" * 100)
    print("RESIDUAL ANALYSIS (sample)")
    print("=" * 100)
    print()

    # Show residuals for a few conditions
    sample_keys = [
        (32, "random", "builtin_sorted"),
        (32, "sorted", "builtin_sorted"),
        (512, "random", "builtin_sorted"),
        (512, "random", "insertion_sort"),
    ]

    for r in results:
        key = (r["size"], r["input_type"], r["algorithm"])
        if key in sample_keys:
            print(f"  size={r['size']} {r['input_type']:15s} {r['algorithm']:15s}")
            for n, mean_t, std_t in r["group_data"]:
                predicted = r["true_time"] + r["overhead"] / n
                residual = mean_t - predicted
                print(f"    N={n:5d}: measured={mean_t:8.3f} μs  predicted={predicted:8.3f} μs  residual={residual:+7.3f} μs")
            print()

    # Write corrected data to CSV
    output_path = os.path.join(os.path.dirname(__file__), "corrected_times.csv")
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "size", "input_type", "algorithm", "true_time_us",
            "overhead_us", "r_squared", "n_points"
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "size": r["size"],
                "input_type": r["input_type"],
                "algorithm": r["algorithm"],
                "true_time_us": round(r["true_time"], 6),
                "overhead_us": round(r["overhead"], 6),
                "r_squared": round(r["r_squared"], 6),
                "n_points": r["n_points"],
            })
    print(f"Corrected times written to: {output_path}")

    return output_path


if __name__ == "__main__":
    output_path = run_analysis()
    print()
    print(f"Done. Re-run: python3 {os.path.join(os.path.dirname(__file__), 'verify_timer_bias.py')} {output_path}")
