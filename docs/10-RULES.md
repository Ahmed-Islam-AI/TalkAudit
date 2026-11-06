# 10 — Engineering Rules

These rules are not optional. A PR that breaks one needs a written reason in the PR description.

## Architecture

1. Testing logic lives in `talkaudit.core`. `cli` and `server` only wire things together.
2. `core` never imports from `cli` or `server`, and never imports FastAPI, SQLAlchemy or any web/DB library.
3. Modules talk through interfaces in `ports.py`. No reaching into another module's internals.
4. All LLM calls go through `talkaudit.core.llm`, written on plain `httpx`. No provider SDKs anywhere. Model IDs live in config, never in code.
5. Business content (scenarios, personas, lexicons, number words, rules) lives in YAML under `packs/`, never in Python code. `examples/` holds format samples only. Native-speaker content starts as `status: draft` with `reviewed_by: []`; only a native-speaker review sets `approved`.

## Multi-tenancy and security

6. Every tenant-owned model and table has `org_id`. Every repository method takes `org_id` as a required argument.
7. Resources from another org return 404, never 403 (don't confirm they exist).
8. Every new endpoint gets a cross-tenant test.
9. Secrets are encrypted at rest, never logged, never returned by the API after creation.
10. Every outbound request to a customer URL goes through the SSRF guard in cloud mode.
11. Synthetic data only. Fixtures must never contain real names with real account numbers, real CNICs, or real phone numbers.
12. Holdout scenarios never appear in issues, PRs, logs, prompts sent to third-party tools, or public storage.

## Grading integrity

13. Graders are pure: same record in, same grade out (deterministic graders) or same request in (judge graders, temperature 0).
14. Every grade carries evidence. No evidence, no merge.
15. Facts that graders check come from scenario data, never from LLM output.
16. Never mix grader versions, trust levels (exact vs self-reported) or judge versions in one reported number.
17. Simulator failures never count as agent failures.
18. A judge without approved calibration produces a visible warning in every report that uses it.
19. Before releasing a scenario, it must pass on a correct reference agent.

## Reproducibility

20. Every run writes a manifest: package version, pack hash, persona and noise hashes, models, temperatures, seeds, judge versions.
21. All randomness goes through the injected `Rng` with the run seed. No `random.random()` or `uuid4()` in logic that affects results.
22. Time goes through the injected `Clock`. Scenario-relative dates ("kal") use the scenario clock.
23. Released pack versions are immutable. Changes require a new version.

## Code quality

24. Python 3.12+, `uv` for dependencies, `ruff` for lint and format, `mypy --strict` for `core`.
25. Pydantic v2 models for all data crossing a module boundary.
26. Async for all I/O (LLM, HTTP, DB). No blocking calls in async paths.
27. Unit tests never call real LLMs or networks. Use fakes from `tests/fakes` or recorded fixtures. Live tests are marked `@pytest.mark.live` and skipped by default.
28. Every bug fix starts with a failing test.
29. Errors are typed (`TalkAuditError` subclasses) with codes matching the API error codes.
30. Logs are structured JSON with `org_id`, `run_id`, `conversation_id` where available.
31. Keep functions small and names plain. Comments explain why, not what.

## Dependencies

32. Add a dependency only if writing it yourself would take more than a day or it's security-sensitive (crypto, auth). Pin versions in the lock file.
33. Prefer libraries with active maintenance and permissive licenses (MIT, Apache, BSD). No GPL in `core`.
34. Avoid wrapper frameworks for LLM calls in `core`; the thin adapter layer is enough.

## Git and releases

35. Small PRs, one task ID each (`T1.7: noise engine`).
36. Conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
37. `main` is always releasable. CI must be green to merge.
38. Semantic versioning for the package, packs, graders and judge prompts separately.
39. Database migrations are backward compatible for one release (expand, then contract).

## Documentation

40. If behavior in a spec doc changes, update the doc in the same PR.
41. Every spec format has a sample in `examples/`. Tests load every file in `examples/` and `packs/`, so neither can go stale.
