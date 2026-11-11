import pytest
from pydantic import ValidationError

from talkaudit.core.models.runtime import ConversationRecord, Evidence, Grade, ToolCall, Turn


def grade(evidence: list[Evidence]) -> Grade:
    return Grade(
        org_id="org_a",
        conversation_id="conv_1",
        grader="action",
        grader_version="action-0.1.0",
        passed=False,
        reason="complaint.create never called",
        evidence=evidence,
        trust="exact",
    )


def test_grade_needs_evidence() -> None:
    with pytest.raises(ValidationError):
        grade([])


def test_evidence_must_point_somewhere() -> None:
    with pytest.raises(ValidationError):
        Evidence(quote="OTP bata dein")


@pytest.mark.parametrize(
    "evidence",
    [Evidence(turn_index=3), Evidence(tool_call_id="tc_1"), Evidence(entity="complaint:CMP-1")],
)
def test_grade_with_evidence(evidence: Evidence) -> None:
    assert grade([evidence]).evidence == [evidence]


def record(turn_org: str, call_org: str) -> ConversationRecord:
    call = ToolCall(org_id=call_org, id="tc_1", tool_name="open_ticket", args={}, source="harness")
    turn = Turn(org_id=turn_org, index=1, role="agent", text="Ji", tool_calls=[call])
    return ConversationRecord(
        org_id="org_a",
        run_id="run_1",
        id="conv_1",
        scenario_id="failed_transfer_01",
        persona_id="roman_messy",
        behavior_id="default",
        repetition=0,
        status="completed",
        stop_reason="goal_reached",
        turns=[turn],
        final_state={},
    )


def test_conversation_accepts_its_own_org() -> None:
    assert record("org_a", "org_a").turns[0].tool_calls[0].org_id == "org_a"


@pytest.mark.parametrize(("turn_org", "call_org"), [("org_b", "org_a"), ("org_a", "org_b")])
def test_conversation_rejects_another_orgs_turns_or_calls(turn_org: str, call_org: str) -> None:
    with pytest.raises(ValidationError, match="must belong to the conversation's org"):
        record(turn_org, call_org)
