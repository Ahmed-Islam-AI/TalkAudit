"""Interfaces between core modules and the outside world. Implementations plug in; tests use
the fakes in tests/fakes."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from talkaudit.core.models.runtime import (
    AgentReply,
    ConversationRecord,
    CustomerMessage,
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


class Clock(Protocol):
    def now(self) -> datetime: ...


class Rng(Protocol):
    def random(self) -> float: ...

    def randint(self, a: int, b: int) -> int: ...

    def choice[T](self, options: Sequence[T], weights: Sequence[float] | None = None) -> T: ...

    def derive(self, key: str) -> "Rng": ...


class LLMClient(Protocol):
    async def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        tools: Sequence[ToolSpec] | None = None,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> LLMResponse: ...


class ToolExecutor(Protocol):
    """Runs agent tool calls for one conversation: map through the manifest, execute on the
    mock backend, record as exact. Shared by the sandbox connector and the MCP gateway."""

    def tools(self) -> list[ToolSpec]: ...

    async def call(self, request: ToolRequest) -> ToolCall: ...


@dataclass(frozen=True)
class ConversationContext:
    # A dataclass, not a Pydantic model: it carries a live service, not data.
    org_id: str
    run_id: str
    conversation_id: str
    tools: ToolExecutor | None  # set when TalkAudit executes tools (sandbox, mcp_session)


class Connector(Protocol):
    trust_level: TrustLevel

    async def start(self, ctx: ConversationContext) -> None: ...

    async def send(self, message: CustomerMessage) -> AgentReply: ...

    async def end(self) -> None: ...


class Grader(Protocol):
    """Pure: same record in, same grade out (judges: same request out, temperature 0)."""

    name: GraderName
    version: str

    async def grade(self, record: ConversationRecord) -> Grade: ...


class Store(Protocol):
    """Every read is scoped by org_id. Another org's data must look missing (NotFoundError)."""

    async def save_run(self, run: Run) -> None: ...

    async def get_run(self, org_id: str, run_id: str) -> Run: ...

    async def save_conversation(self, record: ConversationRecord) -> None: ...

    async def list_conversations(self, org_id: str, run_id: str) -> list[ConversationRecord]: ...

    async def save_grades(self, grades: Sequence[Grade]) -> None: ...

    async def list_grades(self, org_id: str, conversation_id: str) -> list[Grade]: ...
