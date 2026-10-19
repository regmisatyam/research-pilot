# Four-hour reproducibility pilot

Question: How does input order affect the runtime of Python's built-in sorted()
compared with a correct pure-Python insertion sort for small integer lists?

Use Python's standard library only. Use sizes 32, 128 and 512, with random,
sorted, reverse-sorted and duplicate-heavy inputs. Record deterministic seeds,
Python/platform information, algorithms and timer details. Test correctness on
every measured input. Include empty lists, singleton lists and negatives in
separate correctness tests. Use identical inputs for both algorithms, randomize
measurement order, and explain whether copying is timed. Keep each experiment
under two minutes and total files under 100 MB. Avoid dumping datasets to the
conversation; inspect them with scripts and print compact summaries.

Start with a small pilot, then at least 30 repetitions per condition. Retain raw
CSV measurements, scripts, correctness tests and a report with units, counts,
summary statistics, limitations and exact commands to reproduce results. Do not
equate repetition with independent samples. Verify report numbers from raw data.
The critic should look for timing bias, incorrect aggregation, untested edge
cases, misleading speedups and claims unsupported by the measurements.

After resolving problems, choose a justified follow-up within this question,
record a hypothesis before running it, and update the report. Save PROGRESS.md
after each experiment. This is a replication/methodology exercise, not a claim
of a new scientific discovery. Do not install dependencies or change the host.
