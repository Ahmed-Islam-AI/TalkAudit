# 09 — Tasks

Assumes 5–10 hours per week. Estimates are focused hours, not calendar time. Each task has acceptance criteria (AC). A task is done only when its AC pass and tests are merged.

Order matters: the server (M4) is built on a finished core. The core is designed for multi-tenancy from day one (`org_id` in models, storage behind an interface), so nothing is rewritten later.

---

## M0 — Foundations (≈ 10 h, weeks 1–2)

| ID | Task | Est. | AC |
|---|---|---|---|
| T0.1 | Check name availability (GitHub, PyPI, domain); create repo | 1 h | Repo exists, name reserved on PyPI with placeholder |
| T0.2 | Project scaffold: `uv`, `pyproject.toml`, src layout per `03-ARCHITECTURE.md`, Apache 2.0 license | 2 h | `uv run pytest` passes on empty test |
| T0.3 | Tooling: ruff, mypy (strict for `core`), pre-commit, GitHub Actions CI | 2 h | CI green on PR; lint and type errors fail CI |
| T0.4 | Copy `docs/`, `AGENTS.md`, `CLAUDE.md`, `examples/` into repo | 0.5 h | Present on main |
| T0.5 | `ports.py`: interfaces for LLMClient, Store, Clock, Rng, Connector, ToolExecutor, Grader | 2 h | Interfaces + fake implementations in `tests/fakes` |
| T0.6 | Read hinglish-caller-bench source; write `docs/notes/prior-art.md` with what to avoid | 2 h | Note lists at least 5 concrete design decisions |

## M1 — Core engine, sandbox mode, CLI (≈ 45 h, weeks 3–8)

| ID | Task | Est. | AC |
|---|---|---|---|
| T1.1 | Pydantic models for all spec kinds (spec 07) + runtime models (Run, Conversation, Turn, ToolCall, Grade). Runtime models carry `org_id`; spec kinds don't | 5 h | Every file in `examples/` validates on its own; invalid fixtures raise clear errors |
| T1.2 | Spec loader: YAML → models, reference resolution (spec 07 §0, `none` noise profile), pack resolution, content hashing, version pinning. Seed `packs/` with draft content: banking catalog, personas, behaviors, noise profiles, lexicon, number words, scenarios `failed_transfer_01`, `lost_card_01`, `atm_cash_not_dispensed_01` | 3 h | Same pack content → same hash; changed scenario → different hash; one test loads all of `packs/` (fully resolved) and all of `examples/` (per file); a missing reference names both files |
| T1.3 | Argument type normalizers: `money_pkr`, `date`, `phone_pk`, `cnic`, `enum`. Word lists come from the pack's `NumberWords` file | 4 h | Table-driven tests incl. "5k", "Rs.5,000", "1,50,000", "paanch hazar", "۵۰۰۰" → 5000/150000; "dairh lakh", "dhai hazar", "sawa do hazar", "saarhay teen hazar", "do crore"; "kal" → clock − 1 day for `date_direction: past`, + 1 day for `future`. Draft number words cover dairh, dhai, sawa, saarhay, lakh, crore and Urdu digits |
| T1.4 | Manifest mapper: tool call ↔ capability, arg mapping, transforms, one-to-many | 4 h | Round-trip tests; validation reports unmapped capabilities used by pack |
| T1.5 | LLM layer on plain `httpx`, no provider SDKs: OpenAI-compatible adapter + Anthropic adapter, retries, semaphores, token accounting, JSON-schema outputs, request cache | 6 h | Unit tests with HTTP mocks; one live smoke test behind `--live` flag; model IDs only in config |
| T1.6 | Banking mock backend: state from fixtures, implements v1 capabilities, isolated per conversation, complaint references | 5 h | Two conversations never share state (test); every capability has a test |
| T1.7 | Noise engine, placeholder rendering (amount and date styles), draft Roman Urdu lexicon (150 canonical words with candidate variants, `status: draft`) | 5 h | Deterministic with seed (test); protected slots never corrupted; every persona style renders a test amount and date |
| T1.8 | Simulator planner: prompt builder, structured output (message, revealed_facts, goal_status) | 4 h | With fake LLM: hidden facts only passed to prompt as "reveal when asked"; facts reach messages only through placeholders; output with a literal fact value or rendering is rejected |
| T1.9 | `ToolExecutor` (manifest mapping + mock backend + recording) and sandbox connector that runs the agent's tool loop through it; reference agent using any LLM | 3 h | Reference agent (open model via Groq) completes `failed_transfer_01` in English; config rejects a simulator and reference agent on the same provider |
| T1.10 | Conversation runner: loop, stop conditions, checkpoint per conversation, resume | 4 h | Killing the process mid-run and re-running finishes only remaining conversations |
| T1.11 | Local file store (JSONL per conversation, run manifest JSON) implementing Store | 2 h | Store interface tests shared with future Postgres store |
| T1.12 | Outcome and action graders (deterministic), incl. capability groups (`any_of`), extras judged by capability `kind`, `action.allowed` | 4 h | Tests for every failure reason in spec 08 §4 |
| T1.13 | CLI: `init`, `validate`, `demo`, `run`, `report` (basic) | 3 h | `talkaudit demo` runs end-to-end with no API key in < 30 s |

**M1 exit:** `talkaudit run` executes 3 scenarios (`failed_transfer_01`, `lost_card_01`, `atm_cash_not_dispensed_01`) × 6 personas × 3 repetitions in sandbox mode and prints outcome and action pass rates.

## M2 — Grading quality and reports (≈ 30 h, weeks 9–12)

| ID | Task | Est. | AC |
|---|---|---|---|
| T2.1 | Simulator fidelity checker + regeneration + `sim_invalid` | 5 h | Injected broken simulator outputs get caught (tests); sim_invalid rate in report |
| T2.2 | Compliance grader: pattern stage (EN, Roman Urdu, Urdu script lists) | 4 h | Catches "OTP bata dein", "او ٹی پی", "share your OTP" in tests |
| T2.3 | Compliance grader: judge stage + `no_invented_policy` with domain knowledge file | 4 h | Judge JSON validated; evidence quotes present |
| T2.4 | Language-fit judge with binary rubric | 4 h | Outputs per-item booleans with turn index and quote |
| T2.5 | Gold-labelling tool: CLI that shows a transcript and records labels to JSONL | 3 h | Two labellers can label independently; merge command flags disagreements |
| T2.6 | Calibration command: kappa per item, approval gate, stored results | 3 h | Report prints kappa; unapproved judge produces warning |
| T2.7 | Stats module: Wilson CI, pass^k, pass@k, min-sample warnings, scenario-weighted aggregation | 3 h | Unit tests against hand-computed values |
| T2.8 | Markdown + JSON report per spec 08 §9 | 3 h | Report includes 5 worst conversations with evidence |
| T2.9 | `talkaudit diff` | 1.5 h | Detects regressed cells; "within noise" labelling works |

**M2 exit:** full report with all four metrics, intervals, judge kappas and warnings.

## M3 — Dataset, leaderboard, launch (≈ 35 h, weeks 13–17)

| ID | Task | Est. | AC |
|---|---|---|---|
| T3.1 | Recruit 3–5 native speaker reviewers (MindMatrix); write a 1-page review guide | 2 h | Reviewers confirmed; guide in `docs/reviewing.md` |
| T3.2 | Write 30 public + 15 holdout banking scenarios with seed lines | 12 h | All validate; every scenario has ≥ 3 seed lines |
| T3.3 | Native review rounds; fix scenarios | 4 h | Each scenario approved by ≥ 1 reviewer |
| T3.4 | Run against 2 reference agents to catch unfair expectations | 3 h | No scenario fails on a correct reference agent for a grader-design reason |
| T3.5 | Gold labels (60+ conversations) and judge approval | 5 h | All judges approved (kappa ≥ 0.7) or warning documented |
| T3.6 | Cost estimate (`--dry-run`), then leaderboard runs on 6+ models | 3 h | Results stored with manifests |
| T3.7 | Publish: GitHub release, PyPI, HF dataset (public split only), leaderboard page | 3 h | `pip install talkaudit` works on clean machine |
| T3.8 | Launch post with real failure transcripts (public split) | 3 h | Posted on LinkedIn + 3 communities |

**M3 exit:** public launch. Start counting external users for the kill rule in `02-PRODUCT.md`.

## M4 — Multi-tenant server (≈ 40 h, weeks 18–23)

| ID | Task | Est. | AC |
|---|---|---|---|
| T4.1 | SQLAlchemy models + Alembic migrations per spec 03 §6 | 5 h | Migrations up/down on empty DB |
| T4.2 | Postgres Store implementing Store interface | 4 h | Same Store test suite passes as file store |
| T4.3 | Tenancy: repository layer requiring `org_id`; cross-tenant tests | 4 h | Test: org A cannot read any org B resource via any endpoint (404) |
| T4.4 | Auth: API keys (hashed), scopes, users/roles minimal | 3 h | Revoked keys rejected; secret shown once |
| T4.5 | Secret encryption with key rotation | 2 h | Rotation test re-encrypts; logs never contain secrets (log capture test) |
| T4.6 | Postgres job queue + worker process | 5 h | Two workers never run the same job; crashed worker's job retried after lock timeout |
| T4.7 | REST endpoints: projects, agents, versions, manifests, runs, summary, conversations, report, diff | 8 h | OpenAPI schema generated; integration tests per endpoint |
| T4.8 | SSRF guard for outbound agent calls (cloud mode) | 2 h | Blocks private, loopback, link-local, metadata IPs incl. via redirect and DNS rebinding test |
| T4.9 | Rate limiting: per provider, per org, quotas | 2 h | Org exceeding concurrency waits, others unaffected (test) |
| T4.10 | Webhooks with HMAC signing and retries | 2 h | Signature verifies with documented snippet |
| T4.11 | Docker image, compose for dev and self-host, Caddy config | 3 h | `docker compose up` → working API on clean machine |

**M4 exit:** two orgs can register agents and run tests concurrently on one deployment, isolated.

## M5 — Real-agent integration (≈ 30 h, weeks 24–28)

| ID | Task | Est. | AC |
|---|---|---|---|
| T5.1 | HTTP stateless + session connectors (TalkAudit Agent Protocol v1, `protocol: "talkaudit/1"`) | 4 h | Contract tests against a sample FastAPI agent |
| T5.2 | MCP gateway: per-conversation sessions on the shared `ToolExecutor` (manifest-shaped tools, recording) | 8 h | LangGraph sample agent completes scenario using gateway tools; calls recorded as exact |
| T5.3 | Integration snippets: LangGraph, OpenAI Agents SDK, plain MCP client | 4 h | Each under 15 lines, tested in CI |
| T5.4 | Trace (self-reported) and outcome-only modes | 3 h | Reports label trust levels separately |
| T5.5 | Agent version validation endpoint (probe message) | 2 h | Clear error for wrong protocol, auth, manifest |
| T5.6 | Baselines + CI gate logic | 3 h | Gate fails on real regression, passes within noise |
| T5.7 | GitHub Action | 3 h | Example workflow comments results on PR |
| T5.8 | Retention job, backups, staging deploy | 3 h | Restore drill documented and done once |

**M5 exit:** an outside team can test their real agent through the hosted API and get a regression check in CI.

## Later (only after users ask)

- Telecom or wallet pack
- Voice connector (TTS/STT, accents, call-quality noise)
- Web dashboard
- Private packs, compliance packs with an expert
- SSO, audit export, roles
- Billing and usage plans
- Helm chart

## Weekly routine

- Start of week: pick tasks for the week from the next milestone only.
- End of week: update task status, write 3 lines in `docs/notes/log.md`: done, blocked, next.
- Every milestone end: one public post about what you learned.
