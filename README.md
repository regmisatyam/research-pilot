# Research pilot

This controller alternates separate OpenHands worker and critic conversations
using cstem remote llm1 endpoint. A host Python supervisor owns retries, the fixed
deadline and logs. Agents run in Docker; only study directories are mounted.
The critic gets a read-only evidence snapshot. Both roles use the same model,
so their agreement is not independent validation.

## Prerequisites on the Mac mini

Install Docker Desktop for Apple Silicon from:
https://docs.docker.com/desktop/setup/install/mac-install/
Open Docker, finish its setup and wait for the engine to start. Run these in
the csra account. Skip uv installation if `uv --version` already works.

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
open -a Docker
docker context use desktop-linux
docker run --rm hello-world
mkdir -p ~/research-agent
cd ~/research-agent
uv python install 3.12
uv venv --python 3.12 .venv-mini
source .venv-mini/bin/activate
uv pip install 'openhands-sdk==1.54.0' 'openhands-tools==1.54.0' 'openhands-workspace==1.54.0'
python -c 'from openhands.sdk import LLM, Agent, Conversation; from openhands.workspace import DockerWorkspace; print("Imports OK")'
uv pip freeze > requirements-mac-mini.txt
```

If .venv-mini already exists, activate it instead of recreating it. These SDK
versions match the earlier successful personal-Mac test. The agent-server image
is pulled once and its digest recorded; its version may differ from the SDK.
If a protocol/version error occurs, retain the error and use a matching published
agent-server image. No particular version-tag naming convention is assumed here.

## Install and run

Download mac-mini-research-pilot.zip to Downloads. If Safari extracted it already,
move the research-pilot directory into ~/research-agent instead of unzipping.

```sh
cd ~/research-agent
source .venv-mini/bin/activate
unzip ~/Downloads/mac-mini-research-pilot.zip -d .
```

Read/edit research-pilot/TASK.md before initializing. Then:

```sh
python research-pilot/research_supervisor.py --init --hours 4 --task research-pilot/TASK.md
python research-pilot/research_supervisor.py --install-service
python research-pilot/research_supervisor.py --status
tail -f research-pilot/agent-lab/logs/supervisor.log
```

Initialization pulls the ARM64 image before setting the four-hour deadline.
Installing the per-user LaunchAgent starts the run. It checks every minute and
resumes an unfinished run after a supervisor exit. It does not reset the deadline.
Ctrl+C exits tail, not the background study. To run in the foreground instead of
installing the service, use `python research-pilot/research_supervisor.py --resume`.
Do not launch both modes deliberately; a file lock blocks duplicate supervisors.

The supervisor uses caffeinate while running to prevent idle system sleep. Keep
Docker Desktop running and stay logged in to csra; locking the screen is fine.
Enable Docker's launch-at-sign-in option if needed. This is not unattended boot
recovery: reboot, logout, manual sleep and power loss can interrupt it. A user
LaunchAgent needs a login session; FileVault can require an unlock after reboot.

## Stop, inspect and remove

```sh
python research-pilot/research_supervisor.py --stop
python research-pilot/research_supervisor.py --status
```

Stop sets a persistent flag. An active session normally receives SIGINT, with
forced termination after a cleanup allowance of about 40 seconds. Network health
checks can delay noticing the flag. No new sessions start after the deadline;
cleanup can extend beyond it. To remove the background service after stopping:

```sh
launchctl bootout "gui/$(id -u)/local.csra.research-pilot"
rm ~/Library/LaunchAgents/local.csra.research-pilot.plist
```

For a new trial, preserve the old study and extract the package into another
directory. Initialize there. The service has one label; install only one study
service at a time. Do not delete state.json to restart an existing experiment.

## Recovery and limitations

- Session failures retain files and error logs. A new conversation is started
  after backoff of 15, 30, 60, 120, 240 then 300 seconds, bounded by the deadline.
- Each new session receives the last error and is asked to use a different
  method when research attempts repeatedly fail. This is a prompt instruction,
  not a guarantee that it changes strategy or produces valid research.
- A failed model connection is retried by the supervisor; an unavailable LLM
  cannot diagnose its own outage. /models checks do not prove generation works.
- Turns have 20 worker or 10 critic iterations and a 30-minute process limit.
  Each LLM attempt has a 600-second timeout. Session logs preserve events.
- Progress recovery is file-based, not exact conversation restoration. The
  worker is prompted to checkpoint incrementally; unfinished computations may
  be lost. The controller itself records phase, cycle and deadline atomically.
- Hard crashes can leave a Docker container behind. An occupied port 8010 stops
  new launches; inspect `docker ps` and stop only the identified study container
  before resuming. The supervisor never indiscriminately kills other containers.
- Snapshot storage grows per cycle. The sample task requests small files, but
  there are no enforced storage/CPU quotas. Review disk usage during the pilot.
- Same-model criticism can share errors. Human review and independent tests
  remain necessary. No external search tool is configured for literature work.

Results: agent-lab/work; reviews: agent-lab/reviews; immutable-to-critic snapshots:
agent-lab/snapshots; event/stdout logs: agent-lab/logs; run metadata: state.json.
Record failures, completed cycles, wall time, token usage when available, verified
claims, critic findings and fixes for the eventual research methods section.

Validation of this package: Python syntax, file snapshot safeguards, fixed
deadline/stop handling, phase transitions and failure backoff tested locally
with mocked process execution. Docker, launchd and live model integration must
be verified on your Mac mini. Previous Mac success does not establish this new
controller's end-to-end compatibility.
