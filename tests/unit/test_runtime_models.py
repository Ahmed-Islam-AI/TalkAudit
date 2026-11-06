import pytest
from pydantic import ValidationError

from talkaudit.core.models.runtime import Evidence, Grade


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
