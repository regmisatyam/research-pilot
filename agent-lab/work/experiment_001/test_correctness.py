"""
Correctness tests for sorted() and insertion_sort().
Tests edge cases: empty list, singleton, negatives, duplicates,
and all measured input types at sizes 32, 128, 512.
"""
import random
import sys


def insertion_sort(arr):
    """Pure-Python insertion sort. Returns a new sorted list."""
    a = list(arr)  # work on a copy
    n = len(a)
    for i in range(1, n):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    return a


def run_tests():
    results = []
    all_pass = True

    # --- Edge case tests ---
    edge_cases = [
        ("empty list", []),
        ("singleton", [42]),
        ("negatives only", [-5, -1, -3, -2, -4]),
        ("mixed pos/neg", [3, -1, 0, 5, -2, 4]),
        ("all duplicates", [7, 7, 7, 7, 7]),
        ("already sorted", [1, 2, 3, 4, 5]),
        ("reverse sorted", [5, 4, 3, 2, 1]),
    ]

    print("=" * 60)
    print("CORRECTNESS TESTS")
    print("=" * 60)

    for name, data in edge_cases:
        builtin_result = sorted(data)
        insert_result = insertion_sort(data)
        builtin_ok = builtin_result == sorted(data)
        insert_ok = insert_result == builtin_result
        status = "PASS" if insert_ok else "FAIL"
        if not insert_ok:
            all_pass = False
        results.append(("edge", name, "builtin", builtin_ok))
        results.append(("edge", name, "insertion", insert_ok))
        print(f"  {name:25s} builtin={status:4s} insertion={status:4s}")

    # --- Measured input tests (sizes 32, 128, 512; types: random, sorted, reverse, duplicates) ---
    sizes = [32, 128, 512]
    input_types = ["random", "sorted", "reverse", "duplicates"]
    seeds = {
        "random": 42,
        "sorted": 1,
        "reverse": 1,
        "duplicates": 99,
    }

    for size in sizes:
        for itype in input_types:
            seed = seeds[itype]
            rng = random.Random(seed)

            if itype == "random":
                data = [rng.randint(-1000, 1000) for _ in range(size)]
            elif itype == "sorted":
                data = sorted([rng.randint(-1000, 1000) for _ in range(size)])
            elif itype == "reverse":
                data = sorted([rng.randint(-1000, 1000) for _ in range(size)], reverse=True)
            elif itype == "duplicates":
                data = [rng.randint(0, 3) for _ in range(size)]  # only 4 distinct values

            builtin_result = sorted(data)
            insert_result = insertion_sort(data)
            insert_ok = insert_result == builtin_result
            status = "PASS" if insert_ok else "FAIL"
            if not insert_ok:
                all_pass = False
            print(f"  size={size:3d} {itype:15s} insertion={status:4s}  (seed={seed})")

    print()
    print("=" * 60)
    if all_pass:
        print("ALL CORRECTNESS TESTS PASSED")
    else:
        print("SOME CORRECTNESS TESTS FAILED")
    print("=" * 60)

    return all_pass


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
