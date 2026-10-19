"""
Experiment 007 — Discrepancy Investigation: timeit vs perf_counter for presorted inputs

Hypothesis (from experiment_006):
  The large discrepancies (29-40%) between corrected timeit and perf_counter
  for presorted inputs at n=128/512 suggest that Timsort's adaptive behavior
  interacts differently with the two measurement approaches.

  Possible causes:
  1. GC effects — timeit's loop may trigger GC at different points
  2. Memory allocation — timeit's loop may cause different allocation patterns
  3. Timsort internal behavior — different code paths triggered by loop overhead

  Approach:
  - Measure builtin_sorted with both methods on identical inputs
  - Control GC with gc.collect() before each measurement
  - Track memory allocations with tracemalloc
  - Test with pre-allocated buffers
  - Test with frozen inputs (no copy needed)

  If the discrepancy disappears with gc.collect(), it's a GC effect.
  If it disappears with pre-allocated buffers, it's an allocation effect.
  If it persists, it's likely Timsort's internal behavior.
"""
import csv
import gc
import os
import sys
import time
import timeit
import tracemalloc

# ── Input generation ──────────────────────────────────────────────────────────

def make_inputs(seed, size, input_type):
    """Generate a deterministic input list."""
    import random
    rng = random.Random(seed)
    if input_type == "random":
        return [rng.randint(-1000, 1000) for _ in range(size)]
    elif input_type == "sorted":
        return list(range(size))
    elif input_type == "reverse":
        return list(range(size, 0, -1))
    elif input_type == "duplicates":
        return [rng.randint(0, 3) for _ in range(size)]
    else:
        raise ValueError(f"Unknown input_type: {input_type}")


# ── Measurement functions ─────────────────────────────────────────────────────

def measure_perf_counter(data):
    """Measure sorted() with time.perf_counter. Returns (time_us, snapshot)."""
    tracemalloc.start()
    t0 = time.perf_counter()
    result = sorted(data)
    t1 = time.perf_counter()
    elapsed = t1 - t0
    snapshot = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed * 1e6, snapshot  # return microseconds


def measure_timeit(data):
    """Measure sorted() with timeit.timeit. Returns (time_us, snapshot)."""
    tracemalloc.start()
    # timeit returns total time for N iterations; we use N=1
    elapsed = timeit.timeit(lambda: sorted(data), number=1)
    snapshot = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed * 1e6, snapshot  # return microseconds


def measure_perf_counter_gc(data):
    """Measure sorted() with gc.collect() before and after."""
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    result = sorted(data)
    t1 = time.perf_counter()
    gc.collect()
    elapsed = t1 - t0
    snapshot = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed * 1e6, snapshot


def measure_timeit_gc(data):
    """Measure sorted() with timeit and gc.collect()."""
    gc.collect()
    tracemalloc.start()
    elapsed = timeit.timeit(lambda: sorted(data), number=1)
    gc.collect()
    snapshot = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed * 1e6, snapshot


# ── Main experiment ───────────────────────────────────────────────────────────

def run_experiment():
    sizes = [32, 128, 512]
    input_types = ["random", "sorted", "reverse", "duplicates"]
    seeds = [42, 123, 456]  # multiple seeds per condition
    reps = 50  # repetitions per measurement

    results = []
    tracemalloc_results = []

    print("=" * 100)
    print("EXPERIMENT 007 — Discrepancy Investigation")
    print("=" * 100)
    print()
    print(f"Platform: Python {sys.version}")
    print(f"Sizes: {sizes}")
    print(f"Input types: {input_types}")
    print(f"Reps per condition: {reps}")
    print(f"Seeds per condition: {seeds}")
    print()

    # Header for measurements CSV
    csv_rows = []

    for size in sizes:
        for itype in input_types:
            print(f"--- size={size} {itype:15s} ---")

            for seed in seeds:
                data = make_inputs(seed, size, itype)

                # Collect measurements for each method
                perf_times = []
                timeit_times = []
                perf_gc_times = []
                timeit_gc_times = []
                perf_mem = []
                timeit_mem = []
                perf_gc_mem = []
                timeit_gc_mem = []

                for rep in range(reps):
                    # Standard perf_counter
                    t, snap = measure_perf_counter(data)
                    perf_times.append(t)
                    perf_mem.append(snap[1])  # peak memory

                    # Standard timeit
                    t, snap = measure_timeit(data)
                    timeit_times.append(t)
                    timeit_mem.append(snap[1])

                    # With gc.collect()
                    t, snap = measure_perf_counter_gc(data)
                    perf_gc_times.append(t)
                    perf_gc_mem.append(snap[1])

                    t, snap = measure_timeit_gc(data)
                    timeit_gc_times.append(t)
                    timeit_gc_mem.append(snap[1])

                # Compute statistics
                def stats(vals):
                    n = len(vals)
                    mean = sum(vals) / n
                    variance = sum((x - mean) ** 2 for x in vals) / n
                    std = variance ** 0.5
                    return mean, std

                p_mean, p_std = stats(perf_times)
                t_mean, t_std = stats(timeit_times)
                pg_mean, pg_std = stats(perf_gc_times)
                tg_mean, tg_std = stats(timeit_gc_times)

                pm_mean, pm_std = stats(perf_mem)
                tm_mean, tm_std = stats(timeit_mem)
                pgm_mean, pgm_std = stats(perf_gc_mem)
                tgm_mean, tgm_std = stats(timeit_gc_mem)

                # Discrepancies
                disc_no_gc = (t_mean - p_mean) / p_mean * 100 if p_mean > 0 else 0
                disc_gc = (tg_mean - pg_mean) / pg_mean * 100 if pg_mean > 0 else 0

                print(f"  seed={seed}:")
                print(f"    perf_counter:     {p_mean:8.3f} ± {p_std:6.3f} μs")
                print(f"    timeit:           {t_mean:8.3f} ± {t_std:6.3f} μs  (diff: {disc_no_gc:+6.1f}%)")
                print(f"    perf_counter+gc:  {pg_mean:8.3f} ± {pg_std:6.3f} μs")
                print(f"    timeit+gc:        {tg_mean:8.3f} ± {tg_std:6.3f} μs  (diff: {disc_gc:+6.1f}%)")
                print(f"    mem: perf={pm_mean:.0f} timeit={tm_mean:.0f} perf_gc={pgm_mean:.0f} timeit_gc={tgm_mean:.0f}")
                print()

                # Store CSV rows
                for method, mean_t, std_t, mean_m, std_m in [
                    ("perf_counter", p_mean, p_std, pm_mean, pm_std),
                    ("timeit", t_mean, t_std, tm_mean, tm_std),
                    ("perf_counter+gc", pg_mean, pg_std, pgm_mean, pgm_std),
                    ("timeit+gc", tg_mean, tg_std, tgm_mean, tgm_std),
                ]:
                    csv_rows.append({
                        "size": size,
                        "input_type": itype,
                        "seed": seed,
                        "method": method,
                        "mean_us": round(mean_t, 6),
                        "std_us": round(std_t, 6),
                        "mean_peak_mem_bytes": round(mean_m, 0),
                        "std_peak_mem_bytes": round(std_m, 0),
                    })

    # ── Summary analysis ──────────────────────────────────────────────────────
    print("=" * 100)
    print("SUMMARY: Discrepancy by condition")
    print("=" * 100)
    print()

    # Group by (size, input_type) and compute average discrepancy
    groups = {}
    for row in csv_rows:
        key = (int(row["size"]), row["input_type"])
        if key not in groups:
            groups[key] = {"perf_counter": [], "timeit": [], "perf_counter+gc": [], "timeit+gc": []}
        groups[key][row["method"]].append(float(row["mean_us"]))

    print(f"{'Size':>5} {'Input':15s} {'perf':>10s} {'timeit':>10s} {'No-GC%':>8s} {'perf+gc':>10s} {'timeit+gc':>10s} {'GC%':>8s}")
    print("-" * 100)

    for key in sorted(groups.keys()):
        size, itype = key
        g = groups[key]
        p_mean = sum(g["perf_counter"]) / len(g["perf_counter"])
        t_mean = sum(g["timeit"]) / len(g["timeit"])
        pg_mean = sum(g["perf_counter+gc"]) / len(g["perf_counter+gc"])
        tg_mean = sum(g["timeit+gc"]) / len(g["timeit+gc"])

        no_gc_disc = (t_mean - p_mean) / p_mean * 100 if p_mean > 0 else 0
        gc_disc = (tg_mean - pg_mean) / pg_mean * 100 if pg_mean > 0 else 0

        print(
            f"{size:5d} {itype:15s} "
            f"{p_mean:10.3f} {t_mean:10.3f} {no_gc_disc:8.1f}% "
            f"{pg_mean:10.3f} {tg_mean:10.3f} {gc_disc:8.1f}%"
        )

    # ── Key question: Does gc.collect() reduce the discrepancy? ────────────────
    print()
    print("=" * 100)
    print("KEY QUESTION: Does gc.collect() reduce the discrepancy?")
    print("=" * 100)
    print()

    for key in sorted(groups.keys()):
        size, itype = key
        g = groups[key]
        p_mean = sum(g["perf_counter"]) / len(g["perf_counter"])
        t_mean = sum(g["timeit"]) / len(g["timeit"])
        pg_mean = sum(g["perf_counter+gc"]) / len(g["perf_counter+gc"])
        tg_mean = sum(g["timeit+gc"]) / len(g["timeit+gc"])

        no_gc_disc = abs((t_mean - p_mean) / p_mean * 100) if p_mean > 0 else 0
        gc_disc = abs((tg_mean - pg_mean) / pg_mean * 100) if pg_mean > 0 else 0

        reduction = no_gc_disc - gc_disc
        if reduction > 5:
            verdict = "GC likely contributes"
        elif reduction < -5:
            verdict = "GC may worsen it"
        else:
            verdict = "GC has no effect"

        print(f"  size={size:3d} {itype:15s}: no-GC={no_gc_disc:5.1f}%  gc={gc_disc:5.1f}%  reduction={reduction:+5.1f}%  → {verdict}")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    output_path = os.path.join(os.path.dirname(__file__), "measurements.csv")
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "size", "input_type", "seed", "method",
            "mean_us", "std_us", "mean_peak_mem_bytes", "std_peak_mem_bytes"
        ])
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
    print(f"\nMeasurements written to: {output_path}")

    return output_path


if __name__ == "__main__":
    output_path = run_experiment()
    print()
    print(f"Done. Re-run: python3 {os.path.join(os.path.dirname(__file__), 'verify_discrepancy.py')} {output_path}")
