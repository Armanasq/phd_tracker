# PhD Atlas — local private runtime with Docker

This is a **single-owner, Linux host-network** deployment. It keeps the existing Python API bound to `127.0.0.1:8765` on the host. It is not a public-cloud or multi-user deployment, and is not intended for an internet-facing port.

## Requirements

- Linux with Docker Engine and the Docker Compose v2 plugin
- A complete PhD Atlas checkout, including source data and scripts
- An available local TCP port 8765

## Run

```bash
cp .env.example .env
${EDITOR:-vi} .env
docker compose -f compose.local-linux.yml config --quiet
docker compose -f compose.local-linux.yml up --build -d
docker compose -f compose.local-linux.yml ps
```

Set `PHD_ATLAS_REPOSITORY` to your own fork identity and `PHD_ATLAS_COMPOSE_PROJECT` to a unique lowercase project name for this installation. Different forks must use different Compose project names to prevent accidental state-volume reuse. Open `http://127.0.0.1:8765/#settings`, configure an actual running OpenAI-compatible model endpoint, and run the model inference probe. No provider or agent is automatically granted cloud access.

The Compose file deliberately uses `network_mode: host` because the existing private API refuses non-loopback clients. Docker Desktop host networking requires separate enablement and is not a validated cross-platform deployment. On macOS or Windows, use the documented native Python runtime instead. **Do not replace `127.0.0.1` with `0.0.0.0` or publish this container to a public interface.**

## Data and operations

- Private SQLite state and saved provider credentials: project-scoped named volume `<your-compose-project>_private_state`
- Generated public workspace snapshot: project-scoped named volume `<your-compose-project>_generated_site`
- Filesystem: read-only except named volumes and a bounded temporary directory
- Runtime: non-root UID 10001, no additional Linux capabilities, no-new-privileges

Export and verify a private backup using the existing `python -m phd_agents backup` and `verify-backup` commands with the Compose service stopped or through a dedicated one-shot command. Backups exclude provider credentials; retain those separately in an OS-backed secrets store when feasible.

The container includes the Python scheduler, which checks eligible jobs while the process runs. Scheduling, cloud consent, provider activation, and daily cloud budgets remain controlled by the existing private runtime.

## Verify and stop

```bash
curl -fsS http://127.0.0.1:8765/api/health
docker compose -f compose.local-linux.yml logs --tail=60 atlas
docker compose -f compose.local-linux.yml down
```

Do not use `down --volumes` unless you deliberately want to destroy persisted private state. The `.env` file is ignored by Git; never commit secrets or private records.

For GitHub Pages + a model running on the same browser's computer, Docker is not required: use the direct loopback inference adapter documented in [SELF_HOSTING.md](SELF_HOSTING.md). Full authenticated cloud deployment remains separately scoped and requires identity, TLS, authorization, secure secrets, and durable jobs.
