"""Fakes for the core ports. No network, no real LLMs."""

from collections import deque
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any

from talkaudit.core.errors import NotFoundError
from talkaudit.core.models.runtime import (
    AgentReply,
    ConversationRecord,
    CustomerMessage,
    Evidence,
    Grade,
    GraderName,
    LLMMessage,
    LLMResponse,
    Run,
    ToolCall,
    ToolRequest,
    ToolSpec,
    TrustLevel,
)
from talkaudit.core.ports import (
    Clock,
    Connector,
    ConversationContext,
    Grader,
    LLMClient,
    Rng,
    Store,
    ToolExecutor,
)
from talkaudit.core.rng import SeededRng


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


class ScriptedLLM:
    """Returns queued responses in order and keeps every request for assertions."""

    def __init__(self, responses: Iterable[LLMResponse]) -> None:
        self._responses = deque(responses)
        self.requests: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        tools: Sequence[ToolSpec] | None = None,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> LLMResponse:
        self.requests.append(
            {
                "messages": list(messages),
                "model": model,
                "tools": tools,
                "response_schema": response_schema,
                "temperature": temperature,
                "seed": seed,
            }
        )
        if not self._responses:
            raise AssertionError("ScriptedLLM ran out of responses")
        return self._responses.popleft()


class FakeToolExecutor:
    """Answers each tool with a fixed result and records calls like the real executor."""

    def __init__(
        self, org_id: str, results: dict[str, Any], specs: Sequence[ToolSpec] = ()
    ) -> None:
        self._org_id = org_id
        self._results = results
        self._specs = list(specs)
        self.calls: list[ToolCall] = []

    def tools(self) -> list[ToolSpec]:
        return list(self._specs)

    async def call(self, request: ToolRequest) -> ToolCall:
        call = ToolCall(
            org_id=self._org_id,
            id=request.id,
            tool_name=request.name,
            args=request.args,
            result=self._results.get(request.name),
            source="harness",
        )
        self.calls.append(call)
        return call


class ScriptedConnector:
    """Plays back agent replies in order and keeps what the customer sent."""

    def __init__(self, replies: Iterable[AgentReply], trust_level: TrustLevel = "exact") -> None:
        self.trust_level: TrustLevel = trust_level
        self._replies = deque(replies)
        self.received: list[CustomerMessage] = []
        self.ctx: ConversationContext | None = None
        self.ended = False

    async def start(self, ctx: ConversationContext) -> None:
        self.ctx = ctx

    async def send(self, message: CustomerMessage) -> AgentReply:
        self.received.append(message)
        if not self._replies:
            raise AssertionError("ScriptedConnector ran out of replies")
        return self._replies.popleft()

    async def end(self) -> None:
        self.ended = True


class FixedGrader:
    def __init__(self, name: GraderName, passed: bool, version: str = "fixed-0.0.0") -> None:
        self.name: GraderName = name
        self.version = version
        self._passed = passed

    async def grade(self, record: ConversationRecord) -> Grade:
        return Grade(
            org_id=record.org_id,
            conversation_id=record.id,
            grader=self.name,
            grader_version=self.version,
            passed=self._passed,
            reason="fixed grade from FixedGrader",
            evidence=[Evidence(turn_index=0)],
            trust="exact",
        )


class InMemoryStore:
    def __init__(self) -> None:
        self._runs: dict[tuple[str, str], Run] = {}
        self._conversations: dict[tuple[str, str], dict[str, ConversationRecord]] = {}
        self._grades: dict[tuple[str, str], list[Grade]] = {}

    async def save_run(self, run: Run) -> None:
        self._runs[(run.org_id, run.id)] = run

    async def get_run(self, org_id: str, run_id: str) -> Run:
        try:
            return self._runs[(org_id, run_id)]
        except KeyError:
            raise NotFoundError(f"run {run_id} not found") from None

    async def save_conversation(self, record: ConversationRecord) -> None:
        self._conversations.setdefault((record.org_id, record.run_id), {})[record.id] = record

    async def list_conversations(self, org_id: str, run_id: str) -> list[ConversationRecord]:
        return list(self._conversations.get((org_id, run_id), {}).values())

    async def save_grades(self, grades: Sequence[Grade]) -> None:
        for grade in grades:
            self._grades.setdefault((grade.org_id, grade.conversation_id), []).append(grade)

    async def list_grades(self, org_id: str, conversation_id: str) -> list[Grade]:
        return list(self._grades.get((org_id, conversation_id), []))


def _conforms(
    clock: FakeClock,
    rng: SeededRng,
    llm: ScriptedLLM,
    tools: FakeToolExecutor,
    connector: ScriptedConnector,
    grader: FixedGrader,
    store: InMemoryStore,
) -> tuple[Clock, Rng, LLMClient, ToolExecutor, Connector, Grader, Store]:
    # Never called. mypy fails here if a fake drifts from its port.
    return clock, rng, llm, tools, connector, grader, store
