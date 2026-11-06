# 02 — Product

## 1. Positioning

For teams building AI agents that serve Pakistani customers, TalkAudit is a testing service that shows how the agent behaves when real people write in Roman Urdu, Urdu and mixed English. Unlike generic eval tools, it ships realistic local customers, banking and telecom scenarios, and compliance checks out of the box, and it tests the real deployed agent, not just the underlying model.

One-line pitch: **"Before your customers find the failures, TalkAudit does."**

## 2. Who pays, who uses

| Segment | Uses it for | Likely to pay for |
|---|---|---|
| AI vendors and agencies building bots for banks/telcos | Proving quality to clients, catching regressions | Hosted runs, private packs, client-ready reports |
| In-house AI teams at banks, telcos, wallets | Pre-launch testing, regression in CI | Self-hosted license, compliance packs, support |
| Freelance AI developers | Testing client bots | Small hosted plan |
| Open-source community and researchers | Local testing, leaderboard, research | Nothing. They are distribution |

Start with vendors. They are fewer, faster to reach, and feel the pain of proving quality on every contract.

## 3. Jobs to be done

1. "Before we hand this bot to the bank, show me where it breaks for Urdu speakers."
2. "We changed the prompt. Tell me if anything got worse."
3. "Prove to our compliance team that the bot never asks for an OTP."
4. "Which model should we build on for Roman Urdu customers?" (leaderboard)

## 4. Product surfaces

| Surface | Milestone | Notes |
|---|---|---|
| Python package + CLI | M1 | `pip install talkaudit` |
| Public scenario packs | M3 | Banking first |
| Public leaderboard (Hugging Face Space or static site) | M3 | Scored on private holdout |
| REST API + worker (TalkAudit Server) | M4 | Multi-tenant, self-hostable |
| GitHub Action | M5 | Fail PR on regression |
| Web dashboard | Later | Only after paying users ask |
| Voice testing | Later | First major paid feature |

## 5. Open-core split

| Free and open source (Apache 2.0) | Paid (private package or hosted only) |
|---|---|
| Core engine, CLI, SDK | Hosted multi-tenant service |
| Sandbox and black-box connectors | Private domain packs (bank-specific, wallet, telco) |
| Public personas, noise profiles, banking-core pack | Compliance packs maintained with experts |
| All graders and statistics | Voice testing |
| Self-host server for single organization | SSO, audit export, role-based access |
| Public leaderboard | Client-ready branded reports (PDF) |
| | Priority support, custom scenario writing |

Rule: never move a feature from free to paid. Decide the boundary early and keep it.

## 6. Pricing hypotheses (to test, not decide)

Don't set numbers until 5 teams have used it. Hypotheses to test in conversations:

- Usage-based hosted plan: priced per simulated conversation, customer brings their own LLM key.
- Vendor plan: monthly fee including a fixed number of runs and branded reports.
- Self-hosted annual license for banks, including compliance pack updates.

Ask every early user: "What would you pay for this report today, and who signs off?"

## 7. Go-to-market

1. **Leaderboard launch.** Publish how popular models fail on Roman Urdu banking tasks with real transcripts. Post on LinkedIn, MindMatrix, Pakistani dev groups, Hugging Face, r/LocalLLaMA, X.
2. **Free audits.** Offer three AI vendor teams a free run on their real bot in exchange for feedback and permission to use anonymized findings.
3. **Content.** One short post per finding: "Why 'paanch hazar' broke three bots", "The OTP question test".
4. **Community scenarios.** Contribution guide so others add scenarios and personas.
5. **Direct outreach.** After launch, message engineers at vendors and agencies who publicly announce Urdu bots.

## 8. Defensibility

Code is easy to copy. These are harder:

- Human-reviewed Roman Urdu scenarios and personas, built over months
- Private holdout set that keeps the leaderboard honest
- Compliance packs written with domain experts
- Calibrated judges with published agreement scores
- Being known as the reference for Urdu agent quality

## 9. Expansion path

Pakistan is the start, not the ceiling. The engine supports any language through persona and noise packs. Natural next markets have the same mixed-language problem: Arabic-English in the Gulf (large Pakistani diaspora, similar banking bots), Bangla-English, Taglish. Don't build these until Pakistan has paying users.

## 10. Kill and pivot rules

- 8 weeks after launch, fewer than 3 external teams have run it on their own agent → interview 10 non-users, then decide to pivot domain or stop.
- Teams use it but none will pay after 6 months → test the vendor-report angle or a consulting-led model before more engineering.
