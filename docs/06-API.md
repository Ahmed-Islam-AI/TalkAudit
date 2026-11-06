# 06 — API Specification

Three interfaces:

1. **TalkAudit REST API**: how customers control TalkAudit.
2. **TalkAudit Agent Protocol**: how TalkAudit talks to a customer's agent over HTTP.
3. **MCP tool sessions**: how a customer's agent calls TalkAudit's mock tools.

Versioned under `/v1`. Breaking changes require `/v2`.

---

## Part 1 — REST API

### Conventions

- Auth: `Authorization: Bearer ta_live_<prefix>_<secret>`. Keys are scoped to one org.
- JSON everywhere. Timestamps ISO 8601 UTC. IDs are UUIDs prefixed by type in responses (`run_…`) for readability.
- Pagination: `?limit=50&cursor=…`, response has `next_cursor`.
- Idempotency: `POST` endpoints accept `Idempotency-Key` header.
- Errors:

```json
{ "error": { "code": "manifest_invalid", "message": "capability card.block mapped to unknown tool", "details": {...}, "request_id": "req_…" } }
```

| HTTP | code examples |
|---|---|
| 400 | `validation_error`, `manifest_invalid`, `pack_not_found` |
| 401 | `unauthorized` |
| 403 | `forbidden`, `scope_missing` |
| 404 | `not_found` (also returned for other orgs' resources) |
| 409 | `conflict`, `run_already_finished` |
| 422 | `agent_unreachable`, `ssrf_blocked` |
| 429 | `rate_limited`, `quota_exceeded` |

### Endpoints

#### Organization and keys
| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/org` | Current org, plan, usage this period |
| POST | `/v1/api-keys` | Create key (secret shown once) |
| GET | `/v1/api-keys` | List keys (prefix only) |
| DELETE | `/v1/api-keys/{id}` | Revoke |
| POST | `/v1/llm-credentials` | Add BYOK provider key (encrypted) |
| GET | `/v1/llm-credentials` | List (no secrets) |
| DELETE | `/v1/llm-credentials/{id}` | Remove |

#### Projects and agents
| Method | Path | Purpose |
|---|---|---|
| POST/GET | `/v1/projects` | Create / list |
| POST | `/v1/projects/{id}/agents` | Register agent |
| GET | `/v1/agents/{id}` | Agent with versions |
| POST | `/v1/agents/{id}/versions` | New version: connection config, secrets, manifest |
| POST | `/v1/agents/{id}/versions/{v}/validate` | Send one probe message, check protocol and manifest |

Register agent example:

```json
POST /v1/agents/agt_123/versions
{
  "version_label": "2026-11-20-prompt-v4",
  "connector": "http_session",
  "connection": {
    "base_url": "https://bot-staging.example.com/talkaudit",
    "timeout_s": 30
  },
  "secrets": { "auth_header": "Bearer sk-..." },
  "tool_visibility": "mcp_session",
  "manifest": { "$ref": "manifests/banking-agent.yaml" }
}
```

#### Manifests and packs
| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/manifests` | Upload agent manifest (YAML or JSON) |
| POST | `/v1/manifests/validate` | Validate without saving |
| GET | `/v1/packs` | Public packs + org's private packs |
| GET | `/v1/packs/{name}/versions` | Versions with content hash |
| POST | `/v1/packs` | Upload private pack (paid) |

#### Runs
| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/runs` | Start run |
| POST | `/v1/runs/estimate` | Dry run: conversation count, token and cost estimate |
| GET | `/v1/runs` | List (filter by project, agent, status) |
| GET | `/v1/runs/{id}` | Status, progress, manifest |
| POST | `/v1/runs/{id}/cancel` | Cancel |
| GET | `/v1/runs/{id}/summary` | Metrics, breakdowns, warnings |
| GET | `/v1/runs/{id}/conversations` | List with grades; filter `?failed=action&persona=roman_messy` |
| GET | `/v1/conversations/{id}` | Full transcript, tool calls, grades with evidence |
| GET | `/v1/runs/{id}/report?format=md\|json` | Report |
| GET | `/v1/runs/{id}/diff?baseline={run_id}` | Comparison |
| POST | `/v1/runs/{id}/regrade` | Re-run graders with current versions |
| POST | `/v1/agents/{id}/baseline` | Set baseline run |

Start run example:

```json
POST /v1/runs
{
  "project_id": "prj_…",
  "agent_version_id": "agv_…",
  "pack": "banking-core@1.0.0",
  "personas": ["urdu_script", "roman_clean", "roman_messy", "code_switch", "english", "voice_note"],
  "behaviors": ["default", "impatient", "vague"],
  "repetitions": 3,
  "max_turns": 12,
  "simulator": { "credential_id": "cred_…", "model": "…" },
  "judges": { "credential_id": "cred_…" },
  "seed": 42,
  "baseline_run_id": null,
  "tags": ["release-1.4"]
}
```

Run summary shape:

```json
{
  "run_id": "run_…",
  "status": "completed_with_warnings",
  "conversations": { "total": 540, "valid": 521, "sim_invalid": 12, "infra_failed": 7 },
  "metrics": {
    "outcome":    { "pass_rate": 0.81, "ci95": [0.77, 0.84], "pass_hat_3": 0.62, "pass_at_3": 0.93 },
    "action":     { "pass_rate": 0.64, "ci95": [0.60, 0.68] },
    "compliance": { "pass_rate": 0.97, "ci95": [0.95, 0.98], "violations": { "no_otp_request": 4, "no_invented_policy": 9 } },
    "language_fit": { "pass_rate": 0.88, "ci95": [0.85, 0.91], "judge_kappa": 0.78 }
  },
  "breakdowns": { "by_persona": { … }, "by_scenario_tag": { … } },
  "warnings": [ { "code": "low_samples_overall", "scope": "metric=action,trust=self_reported", "n": 64 } ]
}
```

#### Webhooks
| Method | Path |
|---|---|
| POST/GET/DELETE | `/v1/webhooks` |

Events: `run.started`, `run.progress` (every 10%), `run.completed`, `run.failed`. Header `X-TalkAudit-Signature: sha256=<hmac>`.

#### Health
`GET /healthz` (liveness), `GET /readyz` (DB reachable, migrations current).

---

## Part 2 — TalkAudit Agent Protocol v1

The customer exposes one small adapter endpoint in front of their bot. Two variants.

### 2a. Stateless (`http_stateless`)

TalkAudit sends full history each turn.

```
POST {base_url}/turn
Headers:
  Authorization: <customer secret>
  X-TalkAudit-Conversation-Id: conv_…
  X-TalkAudit-MCP-URL: https://api.talkaudit.example/mcp/<token>   (only in mcp_session mode)
Body:
{
  "protocol": "talkaudit/1",
  "conversation_id": "conv_…",
  "messages": [
    {"role": "user", "content": "mra card kho gya h usko band krdo"},
    {"role": "assistant", "content": "Ji, main madad karta hoon. Card ke aakhri 4 digits batayein?"},
    {"role": "user", "content": "4417"}
  ],
  "tools": null,            // only set in sandbox mode
  "system": null,           // only set in sandbox mode
  "metadata": {"channel": "chat", "locale_hint": null}
}
```

### 2b. Session-based (`http_session`)

```
POST {base_url}/sessions                 → {"session_id": "…"}
POST {base_url}/sessions/{id}/messages   body: {"content": "..."}  → AgentReply
DELETE {base_url}/sessions/{id}
```

### AgentReply (both variants)

```json
{
  "text": "Aapka card block kar diya gaya hai.",
  "tool_calls": [
    {"id": "tc_1", "name": "freeze_card", "args": {"cardLast4": "4417", "reason": "lost"}, "result": {"ok": true}}
  ],
  "ended": false,
  "handoff_to_human": false,
  "usage": {"prompt_tokens": 812, "completion_tokens": 64}
}
```

- `tool_calls` optional. In `trace` mode the agent reports what it did; TalkAudit labels these `self_reported`.
- In sandbox mode the agent returns `tool_calls` without `result`; TalkAudit executes them and sends a follow-up with `{"role": "tool", "tool_call_id": "tc_1", "content": "{...}"}` until the agent returns text.
- `handoff_to_human: true` ends the conversation and is graded against the scenario's escalation expectation.

### Timeouts and errors

- Default 30 s per turn, configurable.
- Non-2xx or timeout: retry twice with backoff, then mark conversation `infra_failed` (not counted as agent failure, counted in error budget).

---

## Part 3 — MCP tool sessions

For agents that use MCP. TalkAudit hosts a Streamable HTTP MCP server per conversation.

- URL: `{TALKAUDIT_PUBLIC_URL}/mcp/{session_token}`
- Token: random, 32+ bytes, valid only while the conversation runs, bound to one org and conversation.
- `tools/list` returns tools named and shaped per the agent manifest, so the agent sees its own familiar tool names.
- Every `tools/call` goes through the conversation's `ToolExecutor`, the same one sandbox mode uses: mapped to a capability, executed on the conversation's mock backend, recorded as an exact tool call, and answered in the agent's argument names.
- Unknown tool or bad arguments return an MCP error result (not a crash); the attempt is recorded and graded.

Integration snippet goal: under 15 lines for LangGraph, OpenAI Agents SDK and a plain MCP client. Ship these in `examples/integrations/`.
