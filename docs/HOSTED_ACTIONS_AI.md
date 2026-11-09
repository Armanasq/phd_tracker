# Hosted AI using GitHub Actions and GitHub encrypted secrets

GitHub Pages is a **static frontend**. GitHub Actions is a separate server-side execution platform capable of reading repository or environment secrets, executing Python, making authenticated model requests, and writing validated public outputs to the repository. A fork can use these capabilities independently of its local Python backend. Hosted Actions runs are **asynchronous**, not a real-time chat API.

## Configure your own GitHub repository

In your own repository, open **Settings → Environments → New environment** and create `phd-atlas-ai`. Configure environment protection (required reviewers and allowed branch `main`) when appropriate. Under the environment, set the secret:

| Environment secret | Purpose |
| --- | --- |
| `PHD_ATLAS_AI_API_KEY` | API credential for the selected model provider. Never put it in repository variables or application source. |

Under **Settings → Secrets and variables → Actions → Variables**, configure:

| Repository variable | Example or meaning |
| --- | --- |
| `PHD_ATLAS_ENABLE_HOSTED_AI` | `true` enables opted-in manual and daily hosted inference. Missing/false means disabled. |
| `PHD_ATLAS_AI_BASE_URL` | `https://api.openai.com/v1` or an HTTPS OpenAI-compatible `/v1` service URL. Azure v1: `https://RESOURCE.openai.azure.com/openai/v1`. |
| `PHD_ATLAS_AI_MODEL` | Exact model/deployment identifier supported by the configured endpoint. |
| `PHD_ATLAS_AI_AUTH_MODE` | `bearer` (default) or `api-key` (Azure v1). |
| `PHD_ATLAS_AI_TOKEN_PARAMETER` | `max_tokens` (default) or `max_completion_tokens`, depending on the endpoint. |
| `PHD_ATLAS_DATA_MODE` | `source` for a fork to read only its own `data/user_opportunities.json`; upstream defaults to source. |

Repository-level secrets with the same name are also supported by GitHub Actions, but environment secrets give tighter job-level access and can require reviewer approval. Use the environment for production providers. GitHub does not make configured secrets automatically available to code; the workflow references this one secret explicitly.

Enable **Settings → Actions → General → Workflow permissions → Read and write permissions**, if required for automated commits, and enable Actions in forks. The workflow grants read-only repository access to the model-inference job; a separate publish job receives write access without the provider credential.

Run **Actions → PhD Atlas | Hosted AI Verification Triage → Run workflow**. Scheduling is at 07:11 UTC each day, subject to GitHub Actions scheduling delays. The hosted job must be on `main` and explicitly enabled. A successful run commits `data/hosted_ai_advisories.json` containing only known opportunity IDs and enumerated verification priorities, then explicitly dispatches the Pages deployment workflow. The deployment will show these items in the Verification view when the underlying evidence still matches the run's input. It makes no application submission and never records verified outcomes on the model's authority.

## Information flow

```text
Public repository: source records
     | deterministic public-source builder
     v
GitHub Actions job: sanitized identifiers + verification flags
     | explicit environment-scoped provider secret
     v
OpenAI-compatible HTTPS endpoint
     | untrusted JSON proposal, never logged or uploaded directly
     v
Typed validator: known IDs + known open checks + priority enum
     | sanitized JSON only (no names, prompts, notes or credentials)
     v
Separate GitHub Actions publish job (no model credentials)
     | optimistic git push to main; explicit workflow_dispatch
     v
GitHub Pages: unverified triage suggestions, read-only
```

The model receives only public identifiers, days until recorded closing dates, and deterministic verification-gap categories. It does not receive applicant notes, correspondence, source URLs, application titles, CVs, receipts or private SQLite content. The generated JSON cannot contain free-form model text; unexpected model keys or ungrounded claims fail validation. Existing source facts are never overwritten. An old advisory is ignored when its date, repository identity, or public evidence signature no longer matches.

A public GitHub repository's Actions logs, generated files and uploaded artifacts may be accessible to other users. Do not print private prompts, credentials, model outputs, email messages or personal data into jobs. Restrict collaborators who can modify workflows; use branch protection and environment reviewers. Secrets may be visible to code run by anyone who can commit changes to a workflow that references them, so approval and repository governance matter. The workflow executes only on `main`, never on pull requests, and uses pinned first-party Actions.

## Limits

- Hosted Actions can run an authenticated batch agent, but cannot service low-latency interactive chat from a static GitHub Pages client.
- An interactive hosted Copilot needs an independently authenticated backend (serverless function, container service, or a local service accessed through its own origin); it must enforce user identity, rate limits, model usage budgets and data isolation.
- Local LLMs running on a user's own computer cannot be reached by standard GitHub-hosted runners; use the private loopback runtime to access local vLLM/Ollama/LM Studio.
- Only an OpenAI-compatible Chat Completions endpoint is supported in this batch workflow. Native Bedrock, Responses-only endpoints, or provider-specific transports require separate adapters.
- Enabling a new fork does not inherit another repository's secrets or environmental approvals.

## Validation

```bash
python -m unittest discover -s tests -p 'test_hosted_ai_advisories.py'
python scripts/build_workspace.py --out /tmp/phd-atlas-review.json
python scripts/hosted_ai_advisories.py --input /tmp/phd-atlas-review.json --validate data/hosted_ai_advisories.json
```

The second validation requires an advisory produced for the **same repository, current UTC day and unchanged public input**. It is expected to fail for stale evidence. The tests use a synthetic provider response, not a real API key.