"""Contract every Store must pass. The file store (T1.11) and Postgres store (T4.2) join the
params list below."""

import pytest

from talkaudit.core.errors import NotFoundError
from talkaudit.core.models.runtime import ConversationRecord, Evidence, Grade, Run
from talkaudit.core.ports import Store
from tests.fakes import InMemoryStore


@pytest.fixture(params=[InMemoryStore])
def store(request: pytest.FixtureRequest) -> Store:
    return request.param()


def run(org_id: str = "org_a", run_id: str = "run_1") -> Run:
    return Run(
        org_id=org_id,
        id=run_id,
        pack="banking-core@0.1.0",
        status="running",
        seed=42,
        manifest={},
    )


def conversation(
    org_id: str = "org_a", conv_id: str = "conv_1", **kw: object
) -> ConversationRecord:
    fields: dict[str, object] = {
        "org_id": org_id,
        "run_id": "run_1",
        "id": conv_id,
        "scenario_id": "failed_transfer_01",
        "persona_id": "roman_messy",
        "behavior_id": "default",
        "repetition": 0,
        "status": "completed",
        "stop_reason": "goal_reached",
        "turns": [],
        "final_state": {},
    }
    return ConversationRecord.model_validate(fields | kw)


def grade(org_id: str = "org_a") -> Grade:
    return Grade(
        org_id=org_id,
        conversation_id="conv_1",
        grader="outcome",
        grader_version="outcome-0.1.0",
        passed=True,
        reason="complaint exists",
        evidence=[Evidence(entity="complaint:CMP-1")],
        trust="exact",
    )


async def test_run_round_trip(store: Store) -> None:
    await store.save_run(run())
    assert await store.get_run("org_a", "run_1") == run()


async def test_missing_run_is_not_found(store: Store) -> None:
    with pytest.raises(NotFoundError):
        await store.get_run("org_a", "run_missing")


async def test_other_org_cannot_read_run(store: Store) -> None:
    await store.save_run(run(org_id="org_a"))
    with pytest.raises(NotFoundError):
        await store.get_run("org_b", "run_1")


async def test_other_org_sees_no_conversations_or_grades(store: Store) -> None:
    await store.save_conversation(conversation(org_id="org_a"))
    await store.save_grades([grade(org_id="org_a")])
    assert await store.list_conversations("org_b", "run_1") == []
    assert await store.list_grades("org_b", "conv_1") == []


async def test_saving_a_conversation_twice_keeps_one(store: Store) -> None:
    # Resume re-saves checkpoints; that must not duplicate conversations.
    await store.save_conversation(conversation(status="infra_failed", stop_reason="error"))
    await store.save_conversation(conversation())
    assert await store.list_conversations("org_a", "run_1") == [conversation()]


async def test_grades_round_trip(store: Store) -> None:
    await store.save_grades([grade()])
    assert await store.list_grades("org_a", "conv_1") == [grade()]
