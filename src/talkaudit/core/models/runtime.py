"""Runtime records: what happened in a run. Runs, conversations, turns, tool calls and grades
carry org_id (docs/03-ARCHITECTURE.md §6). Fields are added when a task needs them."""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

GraderName = Literal["sim_fidelity", "outcome", "action", "compliance", "language_fit"]
TrustLevel = Literal["exact", "self_reported", "none"]
GradeTrust = Literal["exact", "self_reported", "judge", "none"]
ToolSource = Literal["harness", "mcp", "self_reported"]
RunStatus = Literal[
    "queued",
    "preparing",
    "running",
    "grading",
    "completed",
    "completed_with_warnings",
    "failed",
    "cancelling",
    "cancelled",
]


class Record(BaseModel):
    # Frozen: graders and stats work on records that must not change under them.
    model_config = ConfigDict(frozen=True, extra="forbid")


class TokenUsage(Record):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ToolSpec(Record):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


class ToolRequest(Record):
    """A tool call as the agent or LLM made it, before manifest mapping."""

    id: str
    name: str
    args: dict[str, Any]


class ToolCall(Record):
    """A recorded tool call. `capability` and `normalized_args` are set once mapped."""

    org_id: str
    id: str
    tool_name: str
    args: dict[str, Any]
    result: Any = None
    capability: str | None = None
    normalized_args: dict[str, Any] | None = None
    source: ToolSource


class LLMMessage(Record):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolRequest] = []
    tool_call_id: str | None = None


class LLMResponse(Record):
    model: str
    text: str | None = None
    tool_calls: list[ToolRequest] = []
    parsed: dict[str, Any] | None = None  # set when a response_schema was given
    usage: TokenUsage = TokenUsage()


class CustomerMessage(Record):
    text: str  # what the agent sees, after noise
    raw_text: str  # placeholders filled, before noise


class AgentReply(Record):
    text: str
    tool_calls: list[ToolCall] = []
    ended: bool = False
    handoff_to_human: bool = False
    latency_ms: int = 0
    usage: TokenUsage | None = None


class Turn(Record):
    org_id: str
    index: int
    role: Literal["customer", "agent", "tool"]
    text: str
    raw_text: str | None = None
    latency_ms: int | None = None
    tool_calls: list[ToolCall] = []
    meta: dict[str, Any] = {}


class ConversationRecord(Record):
    org_id: str
    run_id: str
    id: str
    scenario_id: str
    persona_id: str
    behavior_id: str
    repetition: int
    status: Literal["completed", "sim_invalid", "infra_failed"]
    stop_reason: (
        Literal["goal_reached", "gave_up", "agent_ended", "handoff", "max_turns", "error"] | None
    )
    turns: list[Turn]
    final_state: dict[str, Any]

    @model_validator(mode="after")
    def _one_org(self) -> Self:
        orgs = {t.org_id for t in self.turns} | {c.org_id for t in self.turns for c in t.tool_calls}
        if orgs - {self.org_id}:
            raise ValueError("every turn and tool call must belong to the conversation's org")
        return self


class Run(Record):
    org_id: str
    id: str
    pack: str  # e.g. "banking-core@0.1.0"
    status: RunStatus
    seed: int
    manifest: dict[str, Any]  # reproducibility manifest, docs/03-ARCHITECTURE.md §12
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class Evidence(Record):
    turn_index: int | None = None
    tool_call_id: str | None = None
    entity: str | None = None  # mock-state entity id, e.g. "complaint:CMP-0001"
    quote: str | None = None

    @model_validator(mode="after")
    def _points_somewhere(self) -> Self:
        if self.turn_index is None and self.tool_call_id is None and self.entity is None:
            raise ValueError("evidence must point to a turn, a tool call or an entity")
        return self


class Grade(Record):
    org_id: str
    conversation_id: str
    grader: GraderName
    grader_version: str
    passed: bool
    reason: str
    evidence: list[Evidence] = Field(min_length=1)  # no grade without evidence
    trust: GradeTrust
    details: dict[str, Any] = {}
