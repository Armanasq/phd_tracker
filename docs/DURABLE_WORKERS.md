# Durable local research jobs

The local Python runtime now exposes an opt-in SQLite-backed work queue for **local model providers only**. This feature runs independently of any open browser tab. It is not a public hosted worker service, authenticated multi-user queue or cloud-agent scheduler.

## Start

1. Start the owner-only runtime: `python -m phd_agents serve --port 8765`.
2. In a second local terminal using the same checkout and `PHDAI_PRIVATE_DIR`, start `python -m phd_agents worker-loop --interval-seconds 3`. Run this process under an operator-managed service supervisor for persistent operation.
3. Configure and test a local model (Ollama, vLLM, LM Studio or compatible loopback service). In **Copilot**, select an agent, enter a task and choose **Queue locally**.
4. Open **Run history** to inspect jobs, attempts, status and cancel requests; refresh for new state. The corresponding agent run is visible after the worker completes.
5. The one-shot `python -m phd_agents worker-once` command claims up to one eligible job and returns its result status or `idle`.

## Local API

| Method | Endpoint | Contract |
| --- | --- | --- |
| POST | `/api/jobs/enqueue` | `{ "agent_id": "portfolio_planner", "input_text": "...", "provider_id": "ollama", "max_attempts": 2 }`. Accepted work returns HTTP 202 and a job object |
| GET | `/api/jobs` | Recent jobs without applicant prompt text or credentials |
| GET | `/api/jobs/{id}` | Per-job state, attempts, timestamps, run ID and redacted error type |
| POST | `/api/jobs/{id}/cancel` | Queued work becomes canceled; an active job records a cancellation request |

The private HTTP API still enforces exact loopback Host/Origin and optional server token. Static GitHub Pages cannot invoke these privileged endpoints. The provider ID is captured at enqueue time, and each worker independently re-resolves it. If a provider is reconfigured to cloud, execution fails closed instead of transmitting applicant data.

## Delivery semantics

- The queue survives browser closure and runtime restart; its state is in the private, backed-up SQLite database.
- Atomic claims use a ten-minute lease token and concurrent worker fencing. Expired claims may be reattempted up to the configured limit (1–3), with a bounded delay after recoverable failures.
- A crashed worker can cause **at-least-once** local inference, not exactly-once execution. Repeated inference can consume GPU time. The model call itself is not idempotent.
- Queued cancellation prevents execution. For a running call, cancellation is cooperative; the call may still complete and be recorded as successful. The UI never claims that a remote request was forcibly terminated.
- The queue admits at most 100 queued/running jobs per private database. Each job input is bounded to 5,000 characters, and public status responses never include the prompt.
- This implementation does not support queued cloud jobs, durable multi-agent cloud workflows, isolated per-user identities, distributed workers across machines, priority scheduling, provider usage budgets or webhooks. These require the hosted security and cost-control gates tracked in Issues #6 and #7.

## Verify

Run `python -m pytest tests/test_phd_job_queue.py -q`, inspect the GitHub Actions code-quality workflow for the same commit, then run a local enqueue/worker/status round trip. A successful `/api/health` request alone does not establish that the independent worker process is running.

## Operational guidance

Back up the private SQLite state after queue schema changes. Do not run a worker against a public copy of the database. If the owner terminates the worker while a job is running, the lease will expire and a later worker can retry it. Logs and job statuses should contain error types only; original prompts and responses remain in private storage and must not be committed or published to GitHub Pages.
