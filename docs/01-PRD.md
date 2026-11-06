# 01 — Product Requirements Document

Status: Draft v0.1 · Owner: Ahmed Islam · Last updated: 2026-11-06

## 1. Summary

TalkAudit is a testing service for conversational AI agents used by Pakistani companies. It simulates customers who write in Roman Urdu, Urdu script, English and mixed styles, runs full conversations against a company's real agent, and grades the result on four things: outcome, actions taken, compliance, and language fit. It ships as an open-source engine plus a multi-tenant service that many companies can use at once.

## 2. Problem

Pakistani banks, telcos, wallets and e-commerce companies are shipping chatbots and voice agents that claim to understand Urdu and Roman Urdu. Their teams mostly test in English or by hand. Three things go wrong in production and nobody sees them until customers complain:

1. **Misunderstanding.** Spelling varies ("nahi", "nai", "nhi"), amounts are written many ways ("5k", "5,000", "paanch hazar"), and people switch language mid-sentence.
2. **Wrong action, happy customer.** The agent replies politely but calls the wrong backend action, or the right action with the wrong value. Satisfaction surveys can't catch this.
3. **Compliance slips.** The agent asks for an OTP, PIN or full card number, or makes up a policy. For a bank, one of these is worse than ten unhelpful answers.

Vendors who build these bots for banks have a related problem: they need proof of quality to win and keep contracts, and they have no standard way to produce it.

## 3. Users and buyers

| Who | Role | What they need |
|---|---|---|
| Bot developer (vendor or in-house) | Primary user | Find failures fast, fix them, avoid regressions |
| QA / product lead at bank or telco | User and approver | A test report they trust before go-live |
| Compliance / risk officer | Approver | Evidence that sensitive-data and escalation rules hold |
| Vendor sales lead | Buyer | A credible report to show clients |
| Open-source developer | Community | Free local testing, leaderboard, contribute scenarios |

First paying customer is most likely an AI vendor or agency, not a bank directly.

## 4. Lessons from existing tools

The closest existing tool is `hinglish-caller-bench` (India, MIT, released Oct 2026). Reading its docs, these are the weaknesses TalkAudit must not repeat:

| # | Weakness in existing tool | Why it matters | TalkAudit answer |
|---|---|---|---|
| L1 | Harness sends its own system prompt and tool list to the agent | Tests a model, not the company's real deployed bot | Black-box mode: talk to the real agent through its own chat API. Sandbox mode stays for model benchmarks |
| L2 | Scenarios hard-code tool names (`lookup_order`); adapter only on roadmap | Every company must rename tools before testing | Scenarios reference abstract **capabilities**; each company maps them once in an **agent manifest** |
| L3 | Tool correctness checks a required call sequence | Valid alternative paths fail. Inflates the "wrong tool" rate | Constraint-based grading: required set, forbidden set, only the ordering rules the business actually needs |
| L4 | Reports pass@k (at least one of k runs succeeds) | Flatters agents. A bank needs every attempt to work | Report **pass^k** (all k succeed) as the headline reliability metric; pass@k only as secondary |
| L5 | Very small samples (9 conversations per cell in the published baseline) | Percentages like 0% or 22% swing wildly with one result | Minimum sample rules, Wilson intervals on every number, "insufficient data" label when samples are too small |
| L6 | Language-fit judge self-reported as scoring too high | Unreliable metric | Binary rubric items, human-labelled gold set, judge agreement reported on every report |
| L7 | Personas are language only | Real customers are vague, impatient, change their mind | Persona = language style × behavior × literacy × channel |
| L8 | Simulator quality not measured | If the fake customer breaks character, the agent gets blamed | Simulator fidelity checks per turn; failed simulations excluded and reported separately |
| L9 | No compliance checks | Banks care most about this | Compliance grader with configurable rules (sensitive data, identity verification, escalation, made-up policy) |
| L10 | Single-user CLI, no regression comparison | Can't serve many companies or track versions | Multi-tenant API, runs linked to agent versions, run-to-run diff |
| L11 | Stateless only: full history sent each turn | Many production bots are session-based | Support both stateless and session-based agent protocols |
| L12 | Public scenarios only | Leaderboard can be overfit | Private holdout set for the leaderboard |

## 5. Goals

- G1. A developer can test a real agent in Roman Urdu in under 15 minutes from install.
- G2. Every failure comes with evidence: the turn, the tool call, the rule broken.
- G3. Results are reproducible: same inputs and versions produce the same report structure, with recorded variance.
- G4. Many companies can use one deployment safely, and a bank can self-host the same software.
- G5. A public leaderboard that Pakistani AI teams cite.

## 6. Non-goals (for now)

- Voice/audio testing (planned for later, see roadmap)
- A web dashboard (API and CLI first; dashboard after first paying customers)
- Training or fine-tuning models
- Testing with real customer data. TalkAudit uses synthetic data only
- Languages beyond Urdu/Roman Urdu/English in v1 (engine must allow adding them)

## 7. Functional requirements

### Testing engine
- FR-01 Load versioned scenario packs, personas, noise profiles and capability catalogs from YAML, validated against schemas.
- FR-02 Simulate a customer with an LLM, guided by persona and scenario, revealing hidden facts only when asked.
- FR-03 Apply a deterministic noise layer (spelling variants, amount formats, typos) controlled by a seed.
- FR-04 Check simulator fidelity each turn (stays in persona, doesn't leak hidden facts unprompted, stays on goal). Regenerate up to N times; mark conversation `sim_invalid` if it still fails.
- FR-05 Provide a mock backend per domain with state isolated per conversation.
- FR-06 Connect to agents in four modes: sandbox (harness-executed tools), MCP tool session, self-reported trace, outcome-only.
- FR-07 Support stateless and session-based agent chat protocols.
- FR-08 Map capabilities to agent tool names and arguments through an agent manifest.
- FR-09 Stop conversations on: goal reached, customer gives up, agent ends, max turns, or error.

### Grading
- FR-10 Outcome grader: assertions on final mock backend state.
- FR-11 Action grader: required, forbidden, ordering constraints and argument matchers.
- FR-12 Compliance grader: deterministic patterns plus calibrated judge for configured rules.
- FR-13 Language-fit grader: binary rubric via calibrated judge.
- FR-14 Every grader returns pass/fail, a reason, and evidence pointers (turn index, tool call id).
- FR-15 Statistics: pass rate with Wilson 95% interval, pass^k, pass@k, breakdown by persona and scenario tag, minimum sample warnings.
- FR-16 Judge calibration: store gold labels, compute agreement, block a judge version whose agreement is below threshold.

### Platform
- FR-20 Organizations, projects, users, API keys. Every record belongs to one organization.
- FR-21 Register agents with connection config and encrypted secrets.
- FR-22 Start runs via API; runs execute asynchronously on workers; status and progress via API and webhook.
- FR-23 Compare two runs of the same agent and show what got better or worse.
- FR-24 Bring-your-own LLM key per organization for simulator and judge.
- FR-25 Usage metering per organization (conversations, LLM tokens) for later billing.
- FR-26 Audit log for security-relevant actions.
- FR-27 Export reports as JSON and Markdown (PDF later).

### Developer experience
- FR-30 CLI: `init`, `validate`, `run`, `report`, `diff`, `demo` (no API key needed).
- FR-31 Python SDK for custom connectors and graders.
- FR-32 GitHub Action that fails a pull request when pass rates drop past a threshold.

## 8. Non-functional requirements

- NFR-01 Tenant isolation: no query can read another organization's data. Enforced in code and tested.
- NFR-02 Security: secrets encrypted at rest, never logged; outbound calls to agent URLs protected against SSRF in cloud mode.
- NFR-03 Reproducibility: each run stores a manifest of all versions, seeds and model IDs.
- NFR-04 Resilience: conversation-level checkpointing; a crashed worker resumes without redoing finished conversations.
- NFR-05 Rate limits: per-provider and per-organization concurrency limits; backoff on 429.
- NFR-06 Performance: one worker handles at least 8 concurrent conversations; adding workers scales linearly until provider limits.
- NFR-07 Self-hostable: whole platform runs with `docker compose up` on one machine with no external services except LLM APIs.
- NFR-08 Data: synthetic data only by default; transcripts stored with retention policy per organization.
- NFR-09 Observability: structured logs and OpenTelemetry traces with run and conversation IDs.

## 9. Success metrics

| Stage | Metric | Target |
|---|---|---|
| Launch (end of M3) | Public scenarios reviewed by native speakers | 30+ |
| Launch | Models on leaderboard | 6+ |
| 3 months after launch | GitHub stars | Track, not a goal |
| 3 months after launch | External teams who ran it on their own agent | 5+ |
| 6 months after launch | Teams using the hosted service | 3+ |
| 6 months after launch | Paying customer | 1 |
| Always | Judge agreement with human labels | Cohen's kappa ≥ 0.7 per rubric item |
| Always | Simulator-invalid conversations | Under 5% of a run |

## 10. Release plan

See `09-TASKS.md` for detail.

- M0 Foundations
- M1 Core engine, sandbox mode, CLI
- M2 Grading quality: judges, calibration, statistics, reports
- M3 Dataset, holdout, leaderboard, public launch
- M4 Multi-tenant server (API, worker, Postgres)
- M5 Real-agent integration: MCP sessions, session protocol, run diff, GitHub Action
- Later: voice, dashboard, private packs, SSO, billing

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Simulated Roman Urdu doesn't sound real | Results not trusted | Human-written seed messages, native speaker review, noise layer from real spelling patterns |
| LLM judge disagrees with humans | Wrong scores | Binary rubrics, gold set, agreement gate |
| Banks won't send data to a startup's cloud | No bank sales | Synthetic data only, self-hosted option |
| Solo builder at 5–10 h/week | Slow progress | Strict milestones, core before platform, kill rule after launch |
| Existing Indian tool adds Urdu | Competition | Depth on Pakistan: scenarios, compliance packs, holdout leaderboard, local relationships |
| LLM API costs during leaderboard | Budget overrun | Dry-run cost estimate, small pilot first, BYOK for customers |

## 12. Open questions

- Q1. Which domain after banking: telecom or mobile wallets?
- Q2. Is the server open source (self-host freely) or source-available? Decide before M4.
- Q3. Do vendors want a PDF certificate-style report, or raw data they present themselves?
- Q4. Which Pakistani regulatory references, if any, should the compliance pack cite? Needs research with a compliance professional, not guessing.
