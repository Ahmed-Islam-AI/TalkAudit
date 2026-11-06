# 04 — Infrastructure

## 1. Environments

| Environment | Where | Purpose |
|---|---|---|
| Local dev | Your laptop or Mac mini, Docker Compose | Development, tests |
| CI | GitHub Actions | Lint, type check, unit + integration tests, build images |
| Staging | Same VPS as prod, separate compose project and database | Test releases with real LLM calls |
| Production (cloud) | One VPS to start | Hosted multi-tenant service |
| Customer self-hosted | Customer's server or private cloud | Banks that can't use the cloud. Same images |

Don't run customer-facing workloads on a home server. Home internet, power and IP changes make it unreliable, and it exposes your home network.

## 2. Containers

| Container | Image | Scales | Notes |
|---|---|---|---|
| `api` | `talkaudit-server` | Horizontally, stateless | FastAPI via Uvicorn. Also serves MCP gateway routes in v1 |
| `worker` | `talkaudit-server` (different command) | Horizontally | Pulls jobs from Postgres queue, runs conversations |
| `postgres` | Postgres 16+ | Vertically | Data + job queue |
| `minio` | MinIO (optional) | — | S3-compatible storage for self-host. Cloud can use any S3-compatible service |
| `caddy` | Caddy | — | TLS and reverse proxy in single-VPS setups |

One image, two commands keeps builds simple:

```
api:    talkaudit-server api --host 0.0.0.0 --port 8000
worker: talkaudit-server worker --concurrency 8
```

## 3. Docker Compose sketch

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: talkaudit
      POSTGRES_USER: talkaudit
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U talkaudit"]
  minio:
    image: minio/minio
    command: server /data
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY}
    volumes: [objdata:/data]
  api:
    image: talkaudit-server:${VERSION}
    command: talkaudit-server api --host 0.0.0.0 --port 8000
    env_file: .env
    depends_on: { postgres: { condition: service_healthy } }
  worker:
    image: talkaudit-server:${VERSION}
    command: talkaudit-server worker --concurrency 8
    env_file: .env
    depends_on: { postgres: { condition: service_healthy } }
    deploy: { replicas: 1 }
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes: [./Caddyfile:/etc/caddy/Caddyfile]
volumes: { pgdata: {}, objdata: {} }
```

Pin exact image versions in the real file.

## 4. Job queue

Postgres-backed queue to avoid running Redis:

- `jobs` table, workers claim with `SELECT … FOR UPDATE SKIP LOCKED`.
- Job types: `run.start` (expands into conversations), `conversation.execute`, `run.finalize`, `run.regrade`, `webhook.deliver`.
- Retries with exponential backoff; `attempts` cap; dead jobs visible via admin API.
- Lock timeout so jobs from crashed workers return to the queue.

Switch to Redis or a dedicated broker only if queue contention shows up in metrics.

## 5. Configuration and secrets

All config by environment variables, loaded with pydantic-settings.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection |
| `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Object storage |
| `TALKAUDIT_ENCRYPTION_KEYS` | Comma-separated keys for encrypting secrets (first is current, rest for rotation) |
| `TALKAUDIT_MODE` | `cloud` or `self_hosted` (affects SSRF policy) |
| `TALKAUDIT_PUBLIC_URL` | Base URL used for MCP session URLs |
| `DEFAULT_LLM_*` | Platform LLM keys used when org has no BYOK (leaderboard, demo) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional tracing export |
| `SENTRY_DSN` | Optional error tracking |

Rules:
- Customer agent secrets and BYOK LLM keys are encrypted with application-level encryption before storing.
- Secrets never appear in logs, traces, error messages or reports. Redaction filter in the logging config.
- `.env` never committed. `.env.example` lists every variable with fake values.

## 6. Network security

**SSRF guard (cloud mode).** Customers give you URLs that your workers will call. Without protection, someone can point an "agent URL" at your internal network or cloud metadata service. Before every outbound request to an agent:
- Resolve DNS, reject private, loopback, link-local and metadata IP ranges.
- Re-check after redirects; cap redirects.
- Allow only http/https on standard or explicitly allowed ports.
- Timeouts on connect and read.

In `self_hosted` mode, private addresses are allowed because the bank's agent is inside their network.

**Inbound.** API behind Caddy with TLS. MCP session endpoints use unguessable per-conversation tokens that expire when the conversation ends.

**Webhooks.** Signed with HMAC; customers verify the signature.

## 7. Scaling model

- Throughput is limited by LLM provider rate limits, not your CPU. Design for waiting, not computing: workers are async and run many conversations concurrently.
- Three levels of limits: per provider (global), per org (fairness), per run.
- Each conversation = roughly (turns × 2) LLM calls for simulator + agent (sandbox mode) + judge calls at the end.
- Add workers when queue wait time grows and provider limits still have headroom.

## 8. Observability

- Structured JSON logs with `org_id`, `run_id`, `conversation_id`, `job_id` on every line.
- OpenTelemetry traces: one trace per conversation, spans for simulator call, agent call, tool calls, graders.
- Metrics to watch: queue depth, job latency, conversations per minute, LLM error rate by provider, sim_invalid rate, cost per run.
- Error tracking via Sentry (free tier is enough at the start), optional.

## 9. Data retention and backups

- Per-org `retention_days` for transcripts (default 90). Nightly job deletes expired transcripts and turn rows; keeps summaries.
- Postgres: nightly `pg_dump` to object storage with 14-day retention, plus a monthly copy. Test a restore once a month.
- Synthetic data only. If a customer insists on real data later, that needs a separate design review (redaction, consent, residency).

## 10. CI/CD

GitHub Actions:
1. On every PR: ruff, mypy, unit tests, integration tests with Postgres service container. No real LLM calls (fakes and recorded fixtures).
2. Nightly (main branch): small live smoke run against one cheap model to catch provider API changes.
3. On tag `v*`: build and push image to GitHub Container Registry, publish package to PyPI via trusted publishing, deploy to staging.
4. Manual approval to promote staging to production.

Database migrations with Alembic, run as a one-off container before the new API/worker starts. Migrations must be backward compatible for one release (expand, then contract).

## 11. Self-hosted package for banks

- Same images, `docker-compose.selfhost.yml`, and later a Helm chart.
- Works with only outbound access to the LLM provider they choose, including a local model server inside their network.
- License key check for enterprise features happens offline (signed license file), no phone-home.

## 12. Costs

| Item | Free or paid | Notes |
|---|---|---|
| GitHub (public repo, Actions, Container Registry) | Free for public repos | Limits apply on private repos |
| PyPI | Free | |
| Hugging Face Hub, basic Spaces | Free | Dataset + leaderboard |
| Docker, Postgres, MinIO, Caddy | Free (open source) | |
| VPS for staging + prod | Paid | One small/medium VPS is enough until real customers |
| Domain name | Paid | Small yearly cost |
| S3-compatible storage | Free tier on some providers, then paid | Or MinIO on the VPS |
| Sentry | Free tier | Optional |
| LLM APIs (Groq, Gemini) | Free tiers with rate limits | Fine for development |
| LLM APIs (OpenAI, Anthropic, paid tiers) | Paid per token | Main cost: leaderboard runs. Customers use their own keys |
| Local models via Ollama | Free | Slower; good for offline development |

Free tiers and prices change. Check each provider before planning a budget, and always run `talkaudit run --dry-run` to estimate tokens before a large run.
