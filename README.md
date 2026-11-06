# TalkAudit

TalkAudit tests AI agents the way Pakistani customers actually talk to them: Roman Urdu, Urdu script, English, and all the mixes in between, with messy spelling and incomplete information. It simulates customers, talks to your agent, watches what the agent does behind the scenes, and tells you exactly where it fails.

> Before launch, confirm `talkaudit` is free as a GitHub org and as a domain (`.dev` or `.ai`). It is free on PyPI and npm as of Nov 2026.

## What it answers for a team

- Does our bot solve the customer's problem when they write "mra paisa kat gya magr transfer nai hua"?
- Did it call the right backend actions with the right values (Rs 5,000, not Rs 500)?
- Did it break a compliance rule, such as asking for an OTP or PIN?
- Did it reply in a language the customer could follow?
- Did the new version of our bot get better or worse than last week's?

## How it is built (short version)

One Python core engine, used in three ways:

1. **CLI and Python SDK** (open source). Developers run tests locally or in CI.
2. **TalkAudit Server** (API + worker). Multi-tenant service that many companies use at once. Same engine underneath.
3. **Public leaderboard**. Popular models tested on a held-out Roman Urdu set. This is the marketing.

## Document map

Read in this order:

| File | What it covers |
|---|---|
| `docs/01-PRD.md` | Problem, users, lessons from existing tools, requirements, success metrics |
| `docs/02-PRODUCT.md` | Positioning, buyers, open-core split, go-to-market |
| `docs/03-ARCHITECTURE.md` | System design, modules, data model, why a modular monolith |
| `docs/04-INFRA.md` | Environments, containers, security, scaling, costs |
| `docs/05-FLOWS.md` | User flows and system sequences (Mermaid diagrams) |
| `docs/06-API.md` | REST API, Agent Protocol, MCP tool sessions |
| `docs/07-SCENARIO-SPEC.md` | Capabilities, scenarios, personas, noise profiles, agent manifests |
| `docs/08-GRADING-SPEC.md` | Every grader, statistics, judge calibration |
| `docs/09-TASKS.md` | Milestones and tasks with acceptance criteria |
| `docs/10-RULES.md` | Engineering rules for humans |
| `AGENTS.md` / `CLAUDE.md` | Rules for AI coding assistants working in this repo |
| `examples/` | Format samples of every spec file. Real content lives in `packs/` |

## Glossary

| Term | Meaning |
|---|---|
| **Agent under test (AUT)** | The customer's chatbot or AI agent being tested |
| **Simulator** | The LLM that plays the customer |
| **Persona** | Who the simulated customer is: language style, behavior, literacy |
| **Noise profile** | Deterministic spelling and typing variations applied to simulator text |
| **Capability** | An abstract business action, e.g. `card.block`, independent of any company's tool names |
| **Agent manifest** | A company's mapping from capabilities to their real tool names and arguments |
| **Scenario** | One customer problem, with hidden facts, expected actions and pass conditions |
| **Pack** | A versioned set of scenarios for one domain, e.g. `banking-core@1.0.0` |
| **Run** | One execution of a pack against one agent |
| **Conversation** | One simulated chat inside a run (scenario × persona × repetition) |
| **Mock backend** | A fake bank/telco with state, isolated per conversation |
| **Grader** | Code (or a calibrated LLM judge) that scores one aspect of a conversation |
| **pass^k** | Probability that all k repeated attempts succeed. Measures reliability |
| **Holdout set** | Private scenarios used only for the public leaderboard, never published |

## License plan

- Core engine, CLI, public packs: Apache 2.0
- Enterprise features (SSO, audit export, private packs, voice): separate private package
