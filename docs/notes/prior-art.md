# Prior art: hinglish-caller-bench

Task T0.6. I read the source and docs only. No code was copied or run.

## What it is

`hinglish-caller-bench` (`hcb`) tests customer-service agents with simulated Indian callers in five language styles: English, Hindi in Devanagari, Hindi in Roman script, Hinglish, and a caller who switches language. It is MIT licensed. I read `github.com/payalkanyan/hinglish-caller-bench` at commit `58c936b`, tagged v0.2.0 and dated 2026-10-06. It is one Python package (pydantic, typer, httpx, openai) with a CLI: `init`, `demo`, `run`, `report`, `plot`. It has 30 YAML scenarios across delivery, EMI and refund. Each run has an LLM caller talk to either a built-in reference agent or an HTTP endpoint. Three graders score the result: task completion against the final mock DB state, tool correctness, and a 1–5 language-fit LLM judge. Reports show Wilson 95% intervals and a metric labelled pass@k.

All `file:line` references below point into that repo at `58c936b`.

## PRD §4 claims checked against the source

| # | Claim in 01-PRD §4 | Verdict | Evidence |
|---|---|---|---|
| L1 | Harness sends its own system prompt and tool list to the agent | **Confirmed** | `agent.py:128-133` adds the harness's own `AGENT_SYSTEM_PROMPT` to every HTTP request. `agent.py:190` sends the tool definitions, and `cli.py:344,375` passes the harness's `TOOL_DEFS`. |
| L2 | Scenarios hard-code tool names; adapter only on roadmap | **Confirmed** | Scenarios name tools directly (`scenarios/*.yaml`, `expected_tool_calls`). The executor looks tools up by those fixed names (`agent.py:64-71`). `hcb init` writes an `adapter_example.yaml` (`cli.py:494-511`), but no code ever reads it. The adapter is listed as a v0.3 roadmap item (README "Roadmap"). |
| L3 | Tool correctness checks a required call sequence | **Partly. Wording is inaccurate.** | It does not check a full sequence. Required calls are matched as an unordered set (`graders/tool_correctness.py:45-65`), and order is checked only for the `precedence` pairs a scenario lists (`:70-82`). The real rigidity is elsewhere: each requirement names exactly one tool, args are compared with plain `==` on raw values (`:11-13`), so `"5000"` ≠ `5000`, and there is no type normalization. Valid alternative paths still fail, just for a different reason. |
| L4 | Reports pass@k (at least one of k succeeds), which flatters agents | **Wrong as worded** | `stats.py:24-42` computes `C(c,k)/C(n,k)`. That is pass^k (all k succeed), but the code labels it pass@k and the docstring and README:221 describe it as "at least one". The tests lock in the pass^k values (`tests/test_stats.py:55-56`: n=3, c=2, k=2 → 1/3). The published numbers are therefore the strict metric under the wrong name, so they don't flatter agents. The lesson that metrics must be named precisely still holds. |
| L5 | Very small samples (9 per cell) | **Partly** | Confirmed that cells are tiny: 90 conversations, N=9 per persona×domain (`results/report.md`, README:23). But Wilson 95% intervals are already shown on every cell (`report.py:174-176`). What's actually missing is minimum-sample rules and "insufficient data" labels. Wilson intervals alone don't set TalkAudit apart. |
| L6 | Language-fit judge self-reported as scoring too high | **Confirmed** | README "Roadmap": "currently scores too high across the board". Every cell in `results/report.md` scores 5.0. The judge uses a 1–5 scale (`prompts/language_fit_judge.txt`), and agreement is measured with MAE, within-1 and Pearson, with no approval gate (`graders/language_fit.py:152-184`). |
| L7 | Personas are language only | **Partly** | The schema has `traits: [impatient, typos, vague]` (`schemas.py:9,65`), but no code reads that field. Some behavior is written into prompt text instead (the switcher persona in `personas.py:82-100`). In practice behavior is not a separate, combinable axis. |
| L8 | Simulator quality not measured | **Confirmed** | The caller's LLM output is used unchecked (`simulator.py:44-57`). Example of a fact mismatch: `delivery_damaged_carrier.yaml` says the crushed box was delivered, but the shared mock DB has ORD-22006 as `in_transit` (`examples/reference_agent.py:156-161,292-297`). |
| L9 | No compliance checks | **Confirmed** | There are only three graders: `graders/task_completion.py`, `tool_correctness.py`, `language_fit.py`. |
| L10 | Single-user CLI, no regression comparison | **Confirmed** | Commands are `demo/run/report/plot/init` (`cli.py:22-470`). There is no diff and no tenancy. |
| L11 | Stateless only: full history sent each turn | **Confirmed** | `agent.py:130-136` rebuilds the full message list on every call. There is no session protocol. |
| L12 | Public scenarios only | **Confirmed** | All 30 scenarios are in the repo (stored twice: `scenarios/` and `src/hinglish_bench/scenarios/`, identical). The validator hard-codes exactly 30 (`scenarios.py:12-13`). There is no holdout split. |

Suggested PRD edits: reword L3 as "one tool per requirement, raw-value arg equality, no alternatives". Reword L4 as "metric mislabelled: computes pass^k, documents pass@k". Change L5's answer to stress minimum-sample rules, since Wilson intervals already exist there.

## Design decisions for TalkAudit

| # | What hcb does | What TalkAudit does instead | Where |
|---|---|---|---|
| D1 | Sends its own system prompt and tools to the agent under test (L1) | Black-box connectors send only customer messages. `system` and `tools` are set only in sandbox mode. | 06-API Part 2; 03 §7 |
| D2 | Tools are bound by name to harness functions, and the adapter file is never read (L2) | Capabilities plus an agent manifest. One shared `ToolExecutor` works in capability space and is used by both the sandbox connector and the MCP gateway. | 07 §1–2; 03 §7–8; 05 §5 |
| D3 | Requirements are matched by exact tool name and raw `==` on args (L3) | Normalize args by type (`money_pkr`, `date`, `phone_pk`, `enum`) before matching. Required items can be `any_of` groups, e.g. failed_transfer_01 uses `any_of: [transaction.find, transaction.list]`. Capabilities have `kind: read\|write\|auth`, and `auth` calls are always allowed. | 07 §1, §7; 08 §4 |
| D4 | `C(c,k)/C(n,k)` is labelled pass@k (L4) | Both metrics are named explicitly: pass^k is the headline, and pass@k = `1 − C(n−c,k)/C(n,k)`. Hand-computed tests must tell the two apart. | 08 §8; T2.7 |
| D5 | The conversation stops the moment the mock DB matches `success_state` (`runner.py:150-153`), and some outcomes pass on *any* escalation (`delivery_damaged_carrier.yaml` `success_state`) | Stop on the planner's goal status, the agent ending, give-up, or max turns. Outcome assertions name specific entities and values, plus `complaint.reference_shared_with_customer`, so the agent has to actually tell the customer. | 07 §7; 01 FR-09 |
| D6 | One global mock DB in Python serves all scenarios, and it contradicts at least one scenario (L8 example) | Fixtures live per scenario in YAML. A scenario must pass on a correct reference agent before release. | 07 §7, §9 rules 2 and 4; 10-RULES #19 |
| D7 | The LLM caller types hidden-fact values itself, there's no noise layer, and the `typos` trait is unused | The planner writes typed slots, a seeded noise engine renders them, and a fidelity rule rejects planner output that contains literal fact values. Behaviors are their own axis. | 03 §9; 07 §3–5; 08 §2 |
| D8 | An HTTP agent error (`httpx.HTTPStatusError`, `agent.py:192`) isn't caught as an infra error (`runner.py:158`), so it aborts the whole `gather` batch (`runner.py:221`) | Retry twice, then mark the conversation `infra_failed`. A run-level error budget sits on top. | 06 Part 2 "Timeouts"; 05 §3 |
| D9 | The checkpoint key is (scenario, persona, *caller* model, run_index) with no agent identity (`runner.py:76,204`). Resuming a different agent into the same results dir silently skips its conversations. | Checkpoints are keyed by run ID, and the run manifest records the agent version. | 03 §12; T1.10 |
| D10 | Persona prompts, goodbye words and default model IDs are in Python (`personas.py`, `runner.py:26`, `cli.py:266-271`). Sampling uses unseeded `random.sample` (`graders/language_fit.py:119`, `report.py:327`). | Content lives in YAML packs, model IDs in config only, and all randomness goes through the injected `Rng`. | 10-RULES #5, #21 |
| D11 | 1–5 judge with no calibration gate (L6) | Binary rubric items, a human gold set, and a gate requiring Cohen's kappa ≥ 0.7. | 08 §6–7 |

## Ideas worth borrowing

- **Reveal gate for hidden facts** (`simulator.py:63-100`). The caller only learns a hidden fact's *name* at first. The value is released once the gate decides the agent asked for it: a keyword check first, then a yes/no classifier at temperature 0. In TalkAudit this gate would decide which slots the planner may use. The keyword lists would live in YAML, in English, Roman Urdu and Urdu script.
- **Gemini message-order quirk** (`simulator.py:104-109`). Strict providers want the message list to start with a user turn and to alternate. hcb adds a fixed opening user message. Our default simulator is a Gemini Flash-class model, so the LLM adapter needs to handle this.
- **Farewell backstop** (`runner.py:24-38`). Stop when the caller clearly says goodbye, so the two sides don't trade farewells until max turns. Use it as a fallback behind the planner's `wants_to_end`, with the word list in YAML.
- **Retrying infra failures on resume** (`runner.py:63-79`). Conversations that ended in an infra error aren't recorded as done, so re-running retries them.
- **Request-hash disk cache** (`providers/cache.py:11-22`). The key covers the request content and the repetition index and leaves out credentials.
- **`--dry-run` before building providers** (`cli.py:310-327`), and a **validator that collects every error before failing** (`scenarios.py:22-61`).
- **Worst-transcript ordering** (`report.py:86-97`): failed outcome, then forbidden calls, then wrong args, then missing calls, then order problems.
- **Per-provider rate limiter** shared across roles that use the same endpoint and key (`config.py:49-59`, `providers/ratelimit.py`).

A scenario-writing lesson from `delivery_damaged_carrier.yaml`: the caller's goal tells the caller to ask for the agent's procedure ("check the delivery status and then escalate"). A goal should state what the customer needs, not the steps the agent should take. Consider adding this as a rule in 07 §9.
