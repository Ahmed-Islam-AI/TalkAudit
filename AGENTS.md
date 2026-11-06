# AGENTS.md — Instructions for AI coding assistants

You are working on TalkAudit, a testing service for AI agents serving Pakistani customers (Roman Urdu, Urdu, English, mixed). Read this file fully before writing code.

## Read first
1. `docs/03-ARCHITECTURE.md` — module boundaries and data model
2. `docs/10-RULES.md` — rules you must follow
3. The spec for the area you're touching: `07-SCENARIO-SPEC.md`, `08-GRADING-SPEC.md`, or `06-API.md`
4. The task in `docs/09-TASKS.md` you've been asked to do, including its acceptance criteria

## How to work
- Work on one task ID at a time. Don't start the next task unasked.
- Before coding, state in 3–6 lines: which files you'll change, which interfaces you'll use, how you'll test it.
- Write tests first for graders, normalizers, stats and tenancy. These are where silent bugs hurt most.
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/talkaudit/core tests/fakes && uv run pytest` before saying a task is done. (mypy on `tests/fakes` catches fakes drifting from the ports.)
- If a spec is unclear or contradicts another spec, stop and ask. Don't guess and don't silently change the spec.
- If you change behavior described in a doc, update the doc in the same change.

## Hard rules (never break)
- `talkaudit.core` must not import from `talkaudit.cli`, `talkaudit.server`, FastAPI, SQLAlchemy, or provider SDKs.
- All LLM calls go through `talkaudit.core.llm.LLMClient`.
- Every tenant-owned model, table and repository method uses `org_id`.
- No real LLM or network calls in unit tests. Use `tests/fakes`.
- All randomness via injected `Rng`, all time via injected `Clock`.
- Never put scenario content, personas or word lists in Python code. They belong in YAML under `packs/`. `examples/` holds format samples only.
- Content you draft (personas, scenarios, lexicons, number words) gets `status: draft` and `reviewed_by: []`. Never set `approved`.
- Never read, print, copy or summarize files under `packs/**/holdout/`.
- Never log or return secrets. Never write real personal data into fixtures.
- Graders must return evidence for every grade.

## Style
- Python 3.12+, Pydantic v2, async I/O, type hints everywhere, mypy strict in core.
- Small functions, plain names, comments only for the why.
- Typed errors (`TalkAuditError` subclasses) with stable codes.

## Commands
```
uv sync                       # install
uv run pytest                 # unit + integration (no live calls)
uv run pytest -m live         # live LLM smoke tests (needs keys)
uv run talkaudit demo            # end-to-end with fakes
uv run talkaudit validate examples/
```

## Definition of done
- Acceptance criteria of the task pass
- Tests added and green, lint and types clean
- Docs updated if behavior changed
- No new dependency without a one-line reason in the PR description
