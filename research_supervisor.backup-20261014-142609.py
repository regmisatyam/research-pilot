#!/usr/bin/env python3
"""Mac OpenHands worker/critic pilot. Run --help for commands.

Two separate conversations alternate; this is not concurrent execution.
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
    work = LAB / "work"
    reviews = LAB / "reviews"
    if role == "worker":
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
            "proof of discovery. You have at most 10 iterations.\n\n"
        )
    prompt += "RESEARCH TASK:\n" + (LAB / "TASK.md").read_text()
    prompt += "\n\nLast infrastructure/session error (may not be a research error):\n"
    prompt += state.get("last_error", "None")[-4000:]
    prompt += "\nAnalyze large files with Python; print compact summaries, not entire datasets."

    llm = LLM(usage_id=role, model="openai/" + state["model"],
              base_url=state["base_url"], api_key=SecretStr("local-no-key"),
              native_tool_calling=True, max_input_tokens=32000,
              max_output_tokens=4096, temperature=0, timeout=600, num_retries=2)
    agent = Agent(llm=llm, tools=[Tool(name=TerminalTool.name),
                                Tool(name=FileEditorTool.name)])
    def record(event):
        with (LAB / "logs" / f"{attempt}.jsonl").open("a") as f:
            f.write(event.model_dump_json() + "\n")

    with DockerWorkspace(server_image=state["image"], platform="linux/arm64",
                         host_port=8010, working_dir=directory,
                         volumes=volumes) as workspace:
        conversation = Conversation(agent=agent, workspace=workspace,
            callbacks=[record], max_iteration_per_run=20 if role == "worker" else 10,
            stuck_detection=True)
        try:
            conversation.send_message(prompt)
            conversation.run()
            if role == "critic" and not (output / "REVIEW.md").is_file():
                raise RuntimeError("Critic ended without REVIEW.md; see event log")
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
                health(state)
                state.update(status="running", attempt=attempt)
                atomic_json(STATE, state)
                print(f"{state['phase']} cycle {state['cycle']} — {logpath}", flush=True)
                with logpath.open("w") as log:
                    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                        "--session", attempt], stdout=log, stderr=subprocess.STDOUT,
                        start_new_session=True)
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
                    snapshot(LAB / "work", snap)
                    state.update(snapshot=str(snap), phase="critic")
                else:
                    state.update(phase="worker", cycle=state["cycle"] + 1)
                state.update(status="checkpointed", failures=0, last_error="")
                atomic_json(STATE, state)
            except Exception as error:
                state["failures"] += 1
                state.update(status="recovery_wait", last_error=str(error)[-4000:])
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
    subprocess.run(["launchctl", "bootstrap", domain, str(destination)], check=True)
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
