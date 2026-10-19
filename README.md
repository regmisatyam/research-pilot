# Research Pilot

**A reproducibility study of a supervised, long-running AI research workflow.**

Research Pilot explores whether an AI agent can work through a research question over an extended period: write and run experiments, test correctness, analyze results, respond to criticism, investigate errors, and leave a traceable record of its work. Rather than being a general-purpose research product, this repository is a **four-hour pilot** containing the controller code and the artifacts of an actual sorting-algorithm study.

> **Research question:** How does input order affect the runtime of Python's built-in `sorted()` compared with a correct pure-Python insertion sort for small integer lists?

**Start here:** [Overall research progress](agent-lab/work/PROGRESS.md) · [Nine experiments](agent-lab/work/) · [Research task](TASK.md) · [Setup guide](SETUP.md)

## What this repository demonstrates

- **Research execution:** an OpenHands-based worker writes scripts, operates a terminal, runs benchmarks and correctness tests, analyzes data, and documents findings.
- **Critique and supervision:** a separate critic session inspects read-only evidence, questions methodology, and proposes checks or follow-up experiments.
- **Error recovery:** a host-side supervisor manages session boundaries, retry/backoff, checkpoint files, deadlines, and event logs. The included `research_supervisor_v2.py` also contains a debugger role that attempts repairs in a copy of the workspace and tests them before promotion.
- **Persistent research artifacts:** numbered experiment folders retain code, measurements, verification scripts, and reports. `PROGRESS.md` summarizes the sequence and remaining issues.
- **Bounded autonomy:** the example is a fixed-duration experiment, not evidence of unlimited uninterrupted operation or independent scientific discovery.

The worker and critic are **separate conversations using the same model**, not independent model-based validation. In v2, worker, critic, and debugger roles are scheduled sequentially, not run simultaneously. Agent-written verification is useful but does not substitute for external replication and human review.

## How the research loop works

```text
                 TASK.md (research question)
                            |
                Host Python supervisor
                (deadline, state, retries, logs)
                            |
                   Research worker
                (code, tests, benchmarks)
                            |
                 Saved work + snapshot
                            |
                     Research critic
             (read-only evidence, review)
                            |
                  Findings / next steps
                            |
               Worker revises or extends
                            |
             [v2: debugger on certain failures]
                            |
              Progress, reports, logs, data
```

The supervisor uses Docker workspaces for agent sessions. The worker has a writable research area, while the critic reviews an evidence snapshot. The v2 controller includes file-based memory/checkpointing and an LLM context condenser; recovery does **not** restore an identical conversation state.

## The four-hour sorting pilot

The task compares CPython's built-in `sorted()` (Timsort) with a pure-Python insertion sort across **sorted, reverse-sorted, randomized, and duplicate-heavy integer lists**. Subsequent questions probe scaling, a 10× slowdown threshold, timer overhead, partial disorder, and timing outliers.

The research was run in the reported environment of **CPython 3.13.15 on aarch64 Linux inside Docker**. The study task uses the Python standard library and requires deterministic seeds, correctness checks, raw measurements, and verifiable reports.

### Experiments

| Experiment | Purpose | Where to read |
| --- | --- | --- |
| 001 | Baseline benchmark and correctness tests across input orders | [Report](agent-lab/work/experiment_001/report.md) |
| 002 | Algorithm scaling across larger list sizes | [Report](agent-lab/work/experiment_002/report.md) |
| 003 | First list size where insertion sort exceeds a 10× slowdown | [Report](agent-lab/work/experiment_003/report.md) |
| 004 | Compare `timeit` and `perf_counter` measurement behavior | [Report](agent-lab/work/experiment_004/report.md) |
| 005 | Vary `timeit` calls per measurement to assess noise and overhead | [Report](agent-lab/work/experiment_005/report.md) |
| 006 | Model timer overhead and compare corrected measurements | [Report](agent-lab/work/experiment_006/report.md) |
| 007 | Investigate differences between timing methods under matched conditions | [Report](agent-lab/work/experiment_007/report.md) |
| 008 | Examine how partially sorted inputs affect runtime | [Report](agent-lab/work/experiment_008/report.md) |
| 009 | Investigate timing outliers and garbage collection; correct an insertion-sort bug | [Report](agent-lab/work/experiment_009/report.md) |

Every experiment directory should be treated as a self-contained research artifact. Consult its report for the actual scripts, CSVs, measurements, assumptions, and caveats. The consolidated chronological narrative is in [PROGRESS.md](agent-lab/work/PROGRESS.md).

## Selected findings from the pilot

These are **findings reported by the agents**, not new independent measurements made for this README.

| Question | Reported observation |
| --- | --- |
| Does input order matter? | Yes. Presorted lists are comparatively favorable to insertion sort, while reverse-sorted inputs trigger its quadratic worst-case behavior. |
| How do the algorithms compare? | In the initial benchmark, insertion sort was reported as **6–2,235× slower** than `sorted()`, depending on size and order. |
| What happens at larger sizes? | For reverse-sorted lists of 4,096 integers, experiment 002 reports about **409 ms versus 25 μs** for insertion sort and `sorted()`, respectively. |
| When does the gap become 10×? | In experiment 003's tested sizes, the first reported threshold was **16 elements** for random, reverse, and duplicate-heavy inputs, and **256** for sorted inputs. |
| Why revisit measurement methods? | Later experiments found that timer configuration and system conditions can materially change very small timing measurements. |
| Did garbage collection explain the outliers? | Experiment 009 did **not** support that hypothesis; its report suggests other system noise as a possible explanation, without isolating a definitive cause. |

**Interpretation matters:** the raw timing ratios are environment-specific. Some earlier experiment reports contain statements corrected or qualified by later experiments. For example, timer differences investigated in experiments 004–007 should be read together rather than treating every initial hypothesis as settled. Experiment 003 also contains an internally inconsistent *hypothesis-validation* paragraph; its **reported crossover table** is the appropriate reference for the stated values. The experiment 009 bug fix is documented in its report and progress log.

## Repository guide

```text
research-pilot/
├── README.md                       # Project overview and research navigation
├── SETUP.md                        # Installation, execution and recovery
├── TASK.md                         # Original research protocol
├── research_supervisor.py          # Initial worker/critic controller
├── research_supervisor_v2.py       # Extended controller with debugger role
├── research_supervisor.*backup*.py # Historical controller backups
└── agent-lab/
    ├── TASK.md                     # Task supplied to the agent
    ├── state.json                  # Recorded controller status/metadata
    ├── supervisor.lock             # Duplicate-instance lock file
    ├── logs/                       # Session stdout and JSONL event logs
    ├── reviews/                    # Critic review artifacts
    ├── snapshots/                  # Snapshots provided for critic inspection
    └── work/
        ├── PROGRESS.md             # Across-experiment progress and findings
        ├── TASK.md                 # Task copy in research workspace
        ├── experiment_001/         # Scripts, raw data, checks, report
        ├── ...
        └── experiment_009/
```

### Finding the evidence

- **Understand the assignment:** [TASK.md](TASK.md) specifies inputs, test sizes, seeds, correctness requirements, and reporting standards.
- **Follow the complete research trail:** [PROGRESS.md](agent-lab/work/PROGRESS.md) records experiments, conclusions, fixes, and next steps.
- **Audit an individual claim:** read that experiment's `report.md`, inspect its `measurements.csv` or other outputs, and run its included verification script.
- **Review agent behavior:** [logs](agent-lab/logs/) contain session records, [reviews](agent-lab/reviews/) holds critic feedback, and [snapshots](agent-lab/snapshots/) preserves inspection inputs.
- **Inspect orchestration:** [research_supervisor.py](research_supervisor.py) is the original controller; [research_supervisor_v2.py](research_supervisor_v2.py) extends the design with debugging and context handling. The v2 file's own docstring describes its status and limitations.

## Design boundaries and limitations

This is a **research-methodology and reproducibility pilot**, not a verified autonomous-scientist system.

- Testing was conducted on one reported platform; performance values are not universal.
- Repeated trials of the same input are not equivalent to independent samples.
- The worker and critic use the same underlying model, so shared errors are possible.
- Reports are agent-generated and include hypotheses that were revised, rejected, or sometimes inconsistently described. Raw evidence and independent review take precedence.
- The v2 controller includes a debugger mechanism, but the committed study artifacts do not establish that every v2 path worked end-to-end on real infrastructure.
- The run record is fixed-duration. Its stored status is `deadline_reached`, and session failures/retries are part of the audit trail.
- File-based recovery and context summarization may lose details. A model endpoint health check does not establish successful generation.
- No dedicated scholarly-search or browser-search API is configured in these controllers. Docker-side network access is not the same as a complete literature-review pipeline.

## Reproducing the project

Instructions for installing Docker, Python, OpenHands, connecting the model, initializing a study, running the supervisor, stopping it, and diagnosing failures are deliberately kept separate:

**[Read SETUP.md →](SETUP.md)**

Individual experiment reports also include their own reproduction commands, which are the best starting point if you only want to inspect or rerun the sorting study.

---

**Maintainer:** [Satyam Regmi](https://github.com/regmisatyam) · **Repository:** [regmisatyam/research-pilot](https://github.com/regmisatyam/research-pilot)
