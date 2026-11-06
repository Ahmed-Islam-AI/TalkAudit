# 05 — Flows

All diagrams are Mermaid. They render on GitHub.

## 1. Developer flow: local CLI (open source)

```mermaid
flowchart TD
  A[pip install talkaudit] --> B[talkaudit init my-tests]
  B --> C[talkaudit demo\nno API key, fake agent, fake LLM]
  C --> D[Add LLM key to .env]
  D --> E{What are you testing?}
  E -->|A model| F[Sandbox mode\ntalkaudit run --model groq/...]
  E -->|My real agent| G[Write agent manifest\nmap capabilities to my tools]
  G --> H[talkaudit validate manifest.yaml]
  H --> I[talkaudit run --agent manifest.yaml]
  F --> J[talkaudit report results/]
  I --> J
  J --> K[Read worst transcripts\nfix agent]
  K --> L[Run again]
  L --> M[talkaudit diff old/ new/]
```

## 2. Company flow: hosted platform

```mermaid
flowchart TD
  A[Sign up / org created] --> B[Create API key]
  B --> C[Add BYOK LLM credential\noptional]
  C --> D[Create project]
  D --> E[Register agent\nconnector type + URL + secrets]
  E --> F[Upload agent manifest]
  F --> G[Validation call\nTalkAudit sends a test message]
  G -->|fails| E
  G -->|ok| H[Start run\npack + personas + repetitions]
  H --> I[Webhook / poll status]
  I --> J[Fetch report]
  J --> K[Set as baseline]
  K --> L[CI: run on every release\nGitHub Action compares to baseline]
```

## 3. Run lifecycle (server)

```mermaid
stateDiagram-v2
  [*] --> queued
  queued --> preparing: worker claims run.start
  preparing --> running: conversations expanded into jobs
  preparing --> failed: invalid config / manifest
  running --> grading: all conversations finished
  running --> cancelling: user cancels
  cancelling --> cancelled
  grading --> completed: summary written
  grading --> completed_with_warnings: low samples, high sim_invalid, judge gate failed
  running --> failed: error budget exceeded
  completed --> [*]
  completed_with_warnings --> [*]
  failed --> [*]
  cancelled --> [*]
```

Error budget: if more than 20% of conversations fail for infrastructure reasons (agent down, provider errors after retries), stop the run as `failed` rather than reporting misleading numbers.

## 4. Starting a run (sequence)

```mermaid
sequenceDiagram
  participant C as Client (CLI/CI/API user)
  participant API
  participant DB as Postgres
  participant W as Worker
  C->>API: POST /v1/runs {agent_version, pack, personas, repetitions}
  API->>API: auth, org scope, quota check
  API->>DB: insert run(status=queued), job run.start
  API-->>C: 202 {run_id}
  W->>DB: claim run.start
  W->>W: load pack version, manifest, personas; validate
  W->>DB: freeze manifest JSON on run
  W->>DB: insert conversations + conversation.execute jobs
  loop each conversation job
    W->>DB: claim conversation.execute
    W->>W: execute conversation (see 5)
    W->>DB: store turns, tool calls, grades
  end
  W->>DB: run.finalize: stats, summary, warnings
  W-->>C: webhook run.completed
```

## 5. Conversation loop

```mermaid
sequenceDiagram
  participant R as Runner
  participant S as Simulator (planner LLM)
  participant N as Noise engine
  participant F as Fidelity checker
  participant A as Connector → Agent
  participant T as ToolExecutor
  participant M as Mock backend
  R->>M: create isolated state from scenario fixtures
  R->>A: start(context with ToolExecutor)
  loop until stop condition
    R->>S: persona, goal, facts as placeholders, history
    S-->>R: message with placeholders + revealed_facts + goal_status
    R->>N: fill placeholders in persona styles, apply noise (seeded)
    N-->>R: noised message
    R->>F: check planner output and noised message
    alt invalid (max 2 retries)
      R->>S: regenerate
    end
    R->>A: send(customer message)
    alt sandbox mode
      loop until the agent replies with text
        A->>T: tool calls
        T->>M: map via manifest, execute capability
        M-->>T: results
        T-->>A: results in agent's arg names (recorded, exact)
      end
    else mcp_session mode
      A->>T: tool calls via MCP gateway
      T->>M: map via manifest, execute capability
      T-->>A: results (recorded, exact)
    end
    A-->>R: agent reply
    R->>R: check stop: goal satisfied / gave up / agent ended / max turns / error
  end
  R->>A: end()
  R->>R: freeze ConversationRecord (turns, tool calls, final mock state)
  R->>R: run graders
```

## 6. MCP session mode (testing a real agent's tool use)

```mermaid
sequenceDiagram
  participant W as Worker
  participant G as MCP gateway
  participant T as ToolExecutor (conversation)
  participant M as Mock backend (conversation state)
  participant A as Customer's agent
  W->>G: create session (conversation_id) → token
  W->>A: start conversation, header X-TalkAudit-MCP-URL=https://…/mcp/{token}
  Note over A: Agent connects its MCP client to the given URL\nfor this conversation only
  W->>A: customer message
  A->>G: tools/list
  G-->>A: ToolExecutor.tools(): named per agent manifest
  A->>G: tools/call freeze_card {...}
  G->>T: call(freeze_card, args)
  T->>M: map to capability card.block, execute
  M-->>T: result
  T-->>G: result (agent's argument names)
  G-->>A: result
  T->>W: recorded tool call (exact)
  A-->>W: reply text
  W->>G: close session (token expires)
```

The agent needs one small change: when `X-TalkAudit-MCP-URL` is present, use it as the tool server. Document this as a 10-line integration snippet per framework (LangGraph, OpenAI Agents SDK, plain MCP client).

## 7. Grading flow

```mermaid
flowchart LR
  R[Frozen ConversationRecord] --> SF{sim_fidelity ok?}
  SF -->|no| X[Exclude from agent metrics\ncount as sim_invalid]
  SF -->|yes| O[Outcome grader]
  O --> AC[Action grader]
  AC --> CO[Compliance grader]
  CO --> LF[Language-fit grader]
  LF --> G[(Grades with evidence)]
  G --> ST[Stats: Wilson CI, pass^k, pass@k,\nbreakdowns, warnings]
  ST --> D{Baseline given?}
  D -->|yes| DF[Diff: improved / regressed / unchanged\nper scenario × persona]
  D -->|no| REP[Report]
  DF --> REP
```

## 8. Scenario authoring flow

```mermaid
flowchart TD
  A[Pick capability + real-world situation] --> B[Write scenario YAML\nfacts, hidden facts, expectations]
  B --> C[Write 3-5 seed customer lines\nby a native speaker]
  C --> D[talkaudit validate]
  D --> E[talkaudit preview --scenario X --persona Y\nsee simulated customer messages only]
  E --> F[Native speaker review\nsounds real? yes/no + fixes]
  F -->|no| B
  F -->|yes| G[Run against 2 reference agents]
  G --> H{Expectations fair?\nno false failures on correct behavior}
  H -->|no| B
  H -->|yes| I[Assign to public or holdout split]
  I --> J[Release pack version\nfrozen, hashed]
```

## 9. Judge calibration flow

```mermaid
flowchart TD
  A[Sample 50-100 conversations\nacross personas] --> B[Two humans label each rubric item]
  B --> C[Resolve disagreements → gold set]
  C --> D[Run judge model + prompt version]
  D --> E[Compute Cohen's kappa per item]
  E --> F{kappa ≥ 0.7?}
  F -->|yes| G[Mark judge version approved]
  F -->|no| H[Fix prompt / rubric / model]
  H --> D
  G --> I[Runs record judge version + kappa]
```

## 10. Leaderboard flow

```mermaid
flowchart LR
  A[Holdout pack version] --> B[Fixed simulator model + seed]
  B --> C[Run each model in sandbox mode\nsame repetitions]
  C --> D[Grade with approved judges]
  D --> E[Publish: scores, intervals,\nsample public-set transcripts only]
  E --> F[Never publish holdout scenarios]
```
