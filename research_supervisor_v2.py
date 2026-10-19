#!/usr/bin/env python3
"""Mac OpenHands worker/critic pilot. Run --help for commands.

Worker and critic alternate; a debugger handles unclassified failed worker sessions.
This is not concurrent execution. Failed tool commands within a session remain
visible to the active agent, which can fix them using its terminal.

Context uses LLMSummarizingCondenser(max_size=12, keep_first=2), an event-count
trigger, not a guarantee that no individual tool output can exceed context.
Overflow retries use fresh conversations and best-effort agent-written MEMORY.md.
Summaries and model-authored regression tests can be incomplete or incorrect.

Debugger changes are made in a copy, and a passing regression command produces
an acceptance receipt. Only after the session exits cleanly does the supervisor
select that copy via state.work_path. Original files remain preserved. The test
is model-authored, not independent scientific verification. Three failed repair
sessions route original evidence to the critic. Critic and infrastructure failures
retry their own roles. Host interpreter/Docker/supervisor repairs are not automated.

/research mounts the entire agent-lab tree read-only. /workspace is writable for
the active role; the worker gets the entire active research project there.
No host home-directory, Docker socket or native Mac terminal is exposed.
Network access comes from Docker. No browser GUI or search API is configured.
Install packages inside a project-local environment if your TASK permits it;
container system installs do not survive fresh containers. The existing sorting
TASK still prohibits installing dependencies. Logs, snapshots and repairs can
consume disk; no hard storage quota is enforced.

Validated with mocked SDK/process tests; live integration needs Mac verification.
Use this file in the same directory as the old controller and existing agent-lab.
Do not initialize a new run or delete state to upgrade. Deadline stays unchanged.
Session recovery uses saved files, not exact restoration of conversation state.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import threading
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "agent-lab"
STATE = LAB / "state.json"
STOP = LAB / "STOP"
LABEL = "local.csra.research-pilot"


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w") as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def read_state():
    return json.loads(STATE.read_text())


def configure_environment():
    os.environ["PATH"] = ":".join([
        "/Applications/Docker.app/Contents/Resources/bin",
        str(Path.home() / ".docker/bin"), "/usr/local/bin", "/opt/homebrew/bin",
        os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")])
    if not os.environ.get("DOCKER_HOST"):
        result = subprocess.run([
            "docker", "context", "inspect", "desktop-linux", "--format",
            "{{.Endpoints.docker.Host}}"], capture_output=True, text=True,
            check=True, timeout=15)
        os.environ["DOCKER_HOST"] = result.stdout.strip()


def alive(state):
    return time.time() < state["deadline"] and not STOP.exists()


def wait_interruptibly(seconds, state):
    until = min(time.time() + seconds, state["deadline"])
    while time.time() < until and not STOP.exists():
        time.sleep(min(1, max(0, until - time.time())))


def health(state):
    configure_environment()
    subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                   check=True, capture_output=True, timeout=20)
    request = urllib.request.Request(state["base_url"] + "/models")
    with urllib.request.urlopen(request, timeout=20) as response:
        models = json.load(response)
    if state["model"] not in [m["id"] for m in models.get("data", [])]:
        raise RuntimeError("Configured model is absent from /models")
    # Do not launch onto a port left occupied by another process/container.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 8010))


def snapshot(source, destination):
    # Reject symlinks and special files rather than copying outside the workspace.
    for path in source.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise RuntimeError(f"Snapshot cannot include symlink/special file: {path}")
    shutil.copytree(source, destination)


def session(state, attempt):
    from pydantic import SecretStr
    from openhands.sdk import LLM, Agent, Conversation, Tool
    from openhands.tools.terminal import TerminalTool
    from openhands.tools.file_editor import FileEditorTool
    from openhands.workspace import DockerWorkspace

    configure_environment()
    role = state["phase"]
    work = Path(state.get("work_path", str(LAB / "work")))
    reviews = LAB / "reviews"
    budget = {"worker": 20, "critic": 15, "debugger": 20}[role]
    if role == "debugger":
        candidate = LAB / "repairs" / attempt
        candidate.parent.mkdir(exist_ok=True)
        snapshot(work, candidate)
        (candidate / "REPAIR_TEST.py").unlink(missing_ok=True)
        volumes = [f"{candidate}:/workspace:rw", f"{work}:/original:ro"]
        directory = "/workspace"
        prompt = (
            "You are the debugging agent. /workspace is a writable copy of the research "
            "folder; /original is the original, read-only. Diagnose the supplied failure "
            "using code, logs under /research/logs, and saved progress. Modify only the "
            "copy. Preserve raw measurements and explain every code change in REPAIR.md. "
            "Create REPAIR_TEST.py: a short regression test that reproduces the actual "
            "failure on /original and verifies the fix on /workspace. Run both versions "
            "and record the outcomes. The controller will rerun REPAIR_TEST.py with a "
            "120-second timeout. Do not write a trivial always-passing test. Do not try "
            "to modify host software or the supervisor. If this is an infrastructure "
            "problem you cannot fix, explain it and do not claim a repair. Read earlier "
            "repair reports under /research/repairs and choose a different diagnosis "
            "after a failed attempt. Save REPAIR.md and REPAIR_TEST.py before finishing.\n"
        )
    elif role == "worker":
        volumes = [f"{work}:/workspace:rw", f"{reviews}:/reviews:ro"]
        directory = "/workspace"
        prompt = (
            "You are the research worker. Work only in /workspace. "
            "Read PROGRESS.md and existing results before acting. Read the newest "
            "review under /reviews if present. Address supported criticisms with "
            "experiments or calculations. Do not assume the critic is correct. "
            "Preserve raw results and write new experiments to numbered folders. "
            "Update PROGRESS.md after each experiment with evidence, failed attempts, "
            "remaining issues and next actions. If a method repeatedly fails, explain "
            "why and choose a meaningfully different method. If the task is complete, "
            "verify reproducibility or investigate a justified follow-up within scope. "
            "Never manufacture results or claim novelty without evidence. "
            "Keep experiments short; this turn has at most 20 iterations. "
            "Before finishing, save a concise checkpoint.\n\n"
        )
    else:
        snap = Path(state["snapshot"])
        output = reviews / attempt
        output.mkdir(parents=True, exist_ok=True)
        volumes = [f"{snap}:/evidence:ro", f"{output}:/workspace:rw"]
        directory = "/workspace"
        prompt = (
            "You are the research critic in a fresh conversation. Evidence under "
            "/evidence is read-only. Inspect code and data, recompute key claims, "
            "and test implementations using copies in /workspace when needed. "
            "Do not rerun a long benchmark unnecessarily. Write REVIEW.md in "
            "/workspace, saving findings incrementally. Include each issue's severity, "
            "file/line or calculation evidence, requested fix, and a concrete verification "
            "test. Distinguish verified facts, suggestions, and uncertainty. Note correct "
            "claims too; do not invent issues. Review methodology, unsupported claims, "
            "reproducibility and progress since earlier experiments. End with unresolved "
            "issues and a suggested next experiment. Your approval is not independent "
            "proof of discovery. You have at most 15 iterations.\n\n"
        )
    volumes.append(f"{LAB}:/research:ro")
    prompt += (
        "\nCurrent UTC date: " + datetime.now(timezone.utc).isoformat() +
        "\nYou have Linux terminal and file-editor tools, network access subject to "
        "Docker networking, and read access to the entire study under /research. "
        "Your writable project is /workspace. This is not the host Mac terminal. "
        "Use Python/curl to fetch public sources when the task requires it; record URLs. "
        "Keep command output compact. After each substantial action update a concise "
        "MEMORY.md with goal, verified findings, failed approaches, exact paths and next "
        "steps. Read it on startup. Finish before your turn budget; do not start endless "
        "follow-ups in one turn. Preserve evidence across compaction.\n"
    )
    memory = work / "MEMORY.md"
    if memory.is_file():
        prompt += "\nSAVED MEMORY (bounded excerpt):\n" + memory.read_text(errors="replace")[:12000]
    prompt += "RESEARCH TASK:\n" + (LAB / "TASK.md").read_text()
    prompt += "\n\nLast infrastructure/session error (may not be a research error):\n"
    prompt += state.get("last_error", "None")[-4000:]
    prompt += "\nAnalyze large files with Python; print compact summaries, not entire datasets."

    llm = LLM(usage_id=role, model="openai/" + state["model"],
              base_url=state["base_url"], api_key=SecretStr("local-no-key"),
              native_tool_calling=True, max_input_tokens=32000,
              max_output_tokens=4096, temperature=0, timeout=600, num_retries=2)
    from openhands.sdk.context.condenser import LLMSummarizingCondenser
    condenser = LLMSummarizingCondenser(
        llm=llm.model_copy(update={"usage_id": "condenser"}),
        max_size=12, keep_first=2)
    agent = Agent(llm=llm, condenser=condenser, tools=[Tool(name=TerminalTool.name),
                                Tool(name=FileEditorTool.name)])
    def record(event):
        with (LAB / "logs" / f"{attempt}.jsonl").open("a") as f:
            f.write(event.model_dump_json() + "\n")

    with DockerWorkspace(server_image=state["image"], platform="linux/arm64",
                         host_port=8010, working_dir=directory,
                         volumes=volumes) as workspace:
        conversation = Conversation(agent=agent, workspace=workspace,
            callbacks=[record], max_iteration_per_run=budget,
            stuck_detection=True)
        try:
            conversation.send_message(prompt)
            try:
                conversation.run()
            except Exception as error:
                from openhands.sdk.conversation.exceptions import ConversationRunError
                if not (isinstance(error, ConversationRunError) and
                        "MaxIterationsReached: Agent reached maximum iterations limit" in str(error)):
                    raise
                print("Turn budget reached; handoff with saved evidence.", flush=True)
            if role == "debugger":
                if not (candidate / "REPAIR.md").is_file() or not (candidate / "REPAIR_TEST.py").is_file():
                    raise RuntimeError("Repair requires REPAIR.md and REPAIR_TEST.py")
                check = workspace.execute_command(
                    "python -c \"import subprocess; "
                    "r=subprocess.run(['python','/workspace/REPAIR_TEST.py'],cwd='/workspace',timeout=120); "
                    "raise SystemExit(r.returncode)\"")
                (LAB / "logs" / f"{attempt}-verification.txt").write_text(
                    check.stdout + "\n" + check.stderr)
                if check.exit_code != 0:
                    raise RuntimeError("Repair regression test failed")
                # Original remains intact; supervisor atomically selects this candidate.
                atomic_json(LAB / "logs" / f"{attempt}-repair.json",
                            {"work_path": str(candidate)})
            if role == "critic" and not (output / "REVIEW.md").is_file():
                conversation.send_message(
                    "STOP investigating. Write /workspace/REVIEW.md NOW using only "
                    "evidence already inspected. Use one terminal or file-editor call. "
                    "Label this a PARTIAL REVIEW. List verified findings, uncertainties, "
                    "unreviewed files, and next checks. If no findings were verified, "
                    "say so explicitly. Do not run more experiments or read more files. "
                    "After saving the file, finish immediately."
                )
                try:
                    conversation.run()
                except Exception as error:
                    from openhands.sdk.conversation.exceptions import ConversationRunError
                    if not (isinstance(error, ConversationRunError) and
                            "MaxIterationsReached: Agent reached maximum iterations limit" in str(error)):
                        raise
                if not (output / "REVIEW.md").is_file():
                    raise RuntimeError("Critic failed to save REVIEW.md after finalization")
        finally:
            conversation.close()


def stop_child(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def classify_error(message):
    lower = message.lower()
    if any(term in lower for term in ("contextwindow", "context window", "context_length", "maximum context", "too many tokens")):
        return "context"
    if any(term in lower for term in ("llmtimeout", "llmserviceunavailable", "connection error", "server disconnected", "connection refused", "rate limit", "timed out")):
        return "infrastructure"
    return "research_or_runtime"


def append_incident(state, attempt, category, message):
    with (LAB / "logs/incidents.jsonl").open("a") as f:
        f.write(json.dumps({"time": time.time(), "attempt": attempt,
            "phase": state["phase"], "category": category, "error": message}) + "\n")


def supervise():
    if not STATE.exists():
        print("No run initialized. Use --init first.")
        return
    state = read_state()
    if not alive(state):
        state["status"] = "stopped" if STOP.exists() else "deadline_reached"
        atomic_json(STATE, state)
        return
    caffeine = subprocess.Popen(["/usr/bin/caffeinate", "-is", "-w", str(os.getpid())])
    child = None
    try:
        while alive(state):
            attempt = f"{time.time_ns()}-{state['phase']}"
            logpath = LAB / "logs" / f"{attempt}.log"
            try:
                launched = False
                health(state)
                state.update(status="running", attempt=attempt)
                atomic_json(STATE, state)
                print(f"{state['phase']} cycle {state['cycle']} — {logpath}", flush=True)
                with logpath.open("w") as log:
                    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                        "--session", attempt], stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True)
                    launched = True
                    phase_end = min(state["deadline"], time.time() + 1800)
                    while child.poll() is None and alive(state) and time.time() < phase_end:
                        time.sleep(1)
                    if child.poll() is None:
                        stop_child(child)
                        raise RuntimeError("Session stopped: deadline, stop flag, or 30-minute turn limit")
                    if child.returncode:
                        tail = logpath.read_text(errors="replace")[-4000:]
                        raise RuntimeError(f"Session exit {child.returncode}:\n{tail}")
                if state["phase"] == "worker":
                    snap = LAB / "snapshots" / attempt
                    snapshot(Path(state.get("work_path", str(LAB / "work"))), snap)
                    state.update(snapshot=str(snap), phase="critic")
                elif state["phase"] == "debugger":
                    repair = json.loads((LAB / "logs" / f"{attempt}-repair.json").read_text())
                    state.update(work_path=repair["work_path"], phase="worker")
                else:
                    state.update(phase="worker", cycle=state["cycle"] + 1)
                state["repair_attempts"] = 0
                state.update(status="checkpointed", failures=0, last_error="")
                atomic_json(STATE, state)
            except Exception as error:
                state["failures"] += 1
                message = str(error)[-4000:]
                state.update(status="recovery_wait", last_error=message)
                category = classify_error(message)
                append_incident(state, attempt, category, message)
                if launched and category == "research_or_runtime":
                    if state["phase"] == "worker":
                        state.update(phase="debugger", repair_attempts=0)
                    elif state["phase"] == "debugger":
                        state["repair_attempts"] = state.get("repair_attempts", 0) + 1
                        if state["repair_attempts"] >= 3:
                            # Preserve failed repairs, ask critic to triage original evidence.
                            snap = LAB / "snapshots" / (attempt + "-blocked")
                            snapshot(Path(state.get("work_path", str(LAB / "work"))), snap)
                            state.update(snapshot=str(snap), phase="critic", repair_attempts=0)
                # Context/network failures use a fresh conversation plus saved memory.
                # Critic failures retry the critic with error evidence, preserving isolation.
                atomic_json(STATE, state)
                delay = min(300, 15 * 2 ** min(state["failures"] - 1, 5))
                print(f"Recovery: {error}\nRetry in {delay}s", flush=True)
                wait_interruptibly(delay, state)
        state["status"] = "stopped" if STOP.exists() else "deadline_reached"
        atomic_json(STATE, state)
    finally:
        if child is not None:
            stop_child(child)
        caffeine.terminate()


def install_service():
    if sys.platform != "darwin":
        raise RuntimeError("LaunchAgent installation requires macOS")
    if not STATE.exists():
        raise RuntimeError("Initialize a run before installing the service")
    destination = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    destination.parent.mkdir(parents=True, exist_ok=True)
    spec = {"Label": LABEL,
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "--resume"],
        "WorkingDirectory": str(ROOT), "RunAtLoad": True, "StartInterval": 60,
        "StandardOutPath": str(LAB / "logs/supervisor.log"),
        "StandardErrorPath": str(LAB / "logs/supervisor-error.log")}
    destination.write_bytes(plistlib.dumps(spec))
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    # Give the previous job time to unload; retain final diagnostics on failure.
    for delay in (1, 2, 4, 8):
        time.sleep(delay)
        loaded = subprocess.run(["launchctl", "bootstrap", domain, str(destination)],
                                capture_output=True, text=True)
        if loaded.returncode == 0:
            break
    else:
        raise RuntimeError("Service reload failed: " + loaded.stderr +
                           " Use --resume in the foreground; deadline is unchanged.")
    print("Service installed. It checks for an unfinished run every 60 seconds.")
    print("Lock the screen; stay logged into this account. Docker must be running.")


def main():
    def terminate(signum, frame):
        raise KeyboardInterrupt("Termination requested")
    signal.signal(signal.SIGTERM, terminate)
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("init", "resume", "stop", "status", "install-service"):
        mode.add_argument("--" + name, action="store_true")
    mode.add_argument("--session", metavar="INTERNAL_ATTEMPT")
    parser.add_argument("--hours", type=float, default=4)
    parser.add_argument("--task", type=Path)
    parser.add_argument("--base-url", default="http://172.40.1.35/ai/v1")
    parser.add_argument("--model", default="llm1")
    args = parser.parse_args()
    if args.session:
        parent = os.getppid()
        def watch_parent():
            while True:
                time.sleep(2)
                if os.getppid() != parent:
                    os.kill(os.getpid(), signal.SIGINT)
                    return
        threading.Thread(target=watch_parent, daemon=True).start()
        session(read_state(), args.session)
        return
    LAB.mkdir(parents=True, exist_ok=True)
    if args.stop:
        STOP.touch()
        print("Stop requested; allow up to about 40 seconds for child cleanup.")
        return
    if args.status:
        print(STATE.read_text() if STATE.exists() else "Not initialized")
        return
    if args.install_service:
        install_service()
        return
    with (LAB / "supervisor.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("A supervisor is already running.")
            return
        if args.init:
            if STATE.exists():
                raise RuntimeError("Run already exists. Resume it; use another project folder for a new study.")
            if args.hours <= 0 or not args.task or not args.task.is_file():
                raise RuntimeError("Supply --task FILE and a positive --hours value")
            configure_environment()
            image = "ghcr.io/openhands/agent-server:latest-python"
            subprocess.run(["docker", "pull", "--platform", "linux/arm64", image], check=True)
            result = subprocess.run(["docker", "image", "inspect", image, "--format",
                "{{index .RepoDigests 0}}"], check=True, capture_output=True, text=True)
            pinned = result.stdout.strip()
            if "@sha256:" not in pinned:
                raise RuntimeError("Could not pin image digest")
            for folder in ("work", "reviews", "logs", "snapshots"):
                (LAB / folder).mkdir(exist_ok=True)
            (LAB / "TASK.md").write_text(args.task.read_text())
            (LAB / "work/TASK.md").write_text(args.task.read_text())
            now = time.time()
            atomic_json(STATE, dict(started=now, deadline=now+args.hours*3600,
                phase="worker", cycle=1, failures=0, status="initialized",
                base_url=args.base_url.rstrip("/"), model=args.model, image=pinned))
            print("Initialized. The deadline is now fixed. Run --resume or --install-service.")
        else:
            supervise()


if __name__ == "__main__":
    main()
