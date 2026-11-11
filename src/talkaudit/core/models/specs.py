"""Spec file models (docs/07-SCENARIO-SPEC.md).

Each model validates one file on its own. References between files (catalog, noise profile,
lexicon, number words, capability ids) are resolved by the loader in core.specs. Spec content
belongs to no org, so these models carry no org_id.
"""

import re
import string
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Discriminator,
    Field,
    StringConstraints,
    Tag,
    TypeAdapter,
    field_validator,
    model_validator,
)

Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*$")]
CapabilityId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")]
FactKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
SemVer = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+\.\d+$")]
# A bare id, or id@version where version is a major ("banking@1") or full semver.
Ref = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]*(@\d+(\.\d+\.\d+)?)?$")]


def _no_duplicates(what: str, items: Iterable[str]) -> None:
    duplicates = sorted(item for item, count in Counter(items).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {what}: {', '.join(duplicates)}")


def _placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name is not None}


def _by_shape(mapping_tag: str, plain_tag: str) -> Callable[[Any], str]:
    # For "plain value or mapping" fields: pick the branch from the input's shape, so an error
    # describes only the form the author meant instead of every form the field accepts.
    return lambda value: mapping_tag if isinstance(value, dict | BaseModel) else plain_tag


class Spec(BaseModel):
    # extra="forbid" turns a misspelled field into an error instead of a silent default.
    model_config = ConfigDict(frozen=True, extra="forbid")


class Reviewed(Spec):
    """Native-speaker content. Only a native-speaker review sets `approved`."""

    status: Literal["draft", "approved"] = "draft"
    reviewed_by: list[str] = []

    @model_validator(mode="after")
    def _approved_needs_reviewer(self) -> Self:
        if self.status == "approved" and not self.reviewed_by:
            raise ValueError("status 'approved' needs at least one name in reviewed_by")
        return self


# --- Capability catalog -------------------------------------------------------------------


class ArgSpec(Spec):
    type: Literal["string", "integer", "enum", "money_pkr", "date", "phone_pk", "cnic"]
    required: bool
    values: list[str] | None = None
    pattern: str | None = None
    date_direction: Literal["past", "future"] | None = None

    @model_validator(mode="after")
    def _fits_type(self) -> Self:
        if (self.type == "enum") != bool(self.values):
            raise ValueError("enum args need non-empty 'values'; other types must not have them")
        if (self.type == "date") != (self.date_direction is not None):
            raise ValueError(
                "date args need 'date_direction' (past | future); other types must not have it"
            )
        if self.pattern is not None:
            if self.type != "string":
                raise ValueError("'pattern' is only for string args")
            try:
                re.compile(self.pattern)
            except re.error as error:
                raise ValueError(f"'pattern' is not a valid regex: {error}") from None
        return self


class Capability(Spec):
    id: CapabilityId
    description: str
    kind: Literal["read", "write", "auth"]
    args: dict[str, ArgSpec] = {}
    side_effects: list[str] = []
    sensitive: bool = False


class CapabilityCatalog(Spec):
    kind: Literal["CapabilityCatalog"]
    spec_version: Literal[1]
    domain: Id
    version: SemVer
    capabilities: list[Capability] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        _no_duplicates("capability id", (c.id for c in self.capabilities))
        return self


# --- Agent manifest -----------------------------------------------------------------------


class ArgMapping(Spec):
    from_: str = Field(alias="from")
    map: dict[str, str | int] | None = None
    transform: Literal["paisa_to_rupees"] | None = None

    @model_validator(mode="after")
    def _one_change(self) -> Self:
        if self.map is not None and self.transform is not None:
            raise ValueError("use either 'map' or 'transform', not both")
        return self


ArgTarget = Annotated[
    Annotated[ArgMapping, Tag("mapping")] | Annotated[str, Tag("rename")],
    Discriminator(_by_shape("mapping", "rename")),
]


class ToolMapping(Spec):
    capability: CapabilityId
    tool: str | None = None
    tools: Annotated[list[str], Field(min_length=1)] | None = None
    args: dict[str, ArgTarget] = {}

    @model_validator(mode="after")
    def _one_tool_field(self) -> Self:
        if (self.tool is None) == (self.tools is None):
            raise ValueError("set exactly one of 'tool' or 'tools'")
        return self

    @property
    def tool_names(self) -> list[str]:
        return [self.tool] if self.tool is not None else list(self.tools or [])


class AgentManifest(Spec):
    kind: Literal["AgentManifest"]
    spec_version: Literal[1]
    name: Id
    catalog: Ref
    mappings: list[ToolMapping] = Field(min_length=1)
    unmapped_tools: Literal["ignore", "record", "fail"]

    @model_validator(mode="after")
    def _one_capability_per_tool(self) -> Self:
        names = [name for mapping in self.mappings for name in mapping.tool_names]
        _no_duplicates("tool (mapped to more than one capability)", names)
        return self


# --- Persona and behavior -----------------------------------------------------------------


class LanguageStyle(Spec):
    primary: Literal["urdu", "roman_urdu", "english", "mixed"]
    script: Literal["latin", "arabic"]
    english_mixing: Literal["none", "low", "medium", "high"]
    switches_mid_sentence: bool


class Persona(Reviewed):
    kind: Literal["Persona"]
    spec_version: Literal[1]
    id: Id
    version: SemVer
    label: str
    language_style: LanguageStyle
    literacy: Literal["low_formal", "medium", "high"]
    # Aliased: a field named `register` would shadow ABCMeta.register on the model class.
    register_: Literal["informal", "polite", "formal"] = Field(alias="register")
    noise_profile: Ref
    amount_styles: list[str] = Field(min_length=1)
    date_styles: list[str] = Field(min_length=1)
    seed_lines: list[str]
    forbidden: list[str] = []


class Behavior(Spec):
    kind: Literal["Behavior"]
    spec_version: Literal[1]
    id: Id
    description: str
    rules: list[str] = Field(min_length=1)
    # Used by changes_mind; where the wrong value comes from is still open (deferred gap).
    correction_slot_required: bool = False


# --- Noise profile, lexicon, number words -------------------------------------------------

AMOUNT_PLACEHOLDERS = {"k", "n", "n_comma", "urdu_words"}
DATE_PLACEHOLDERS = {"relative", "d", "m", "mon", "yyyy"}


class NoiseOp(Spec):
    op: Literal[
        "spelling_variant", "vowel_drop", "abbreviation", "drop_punctuation", "lowercase", "typo"
    ]
    probability: float = Field(ge=0, le=1)
    min_len: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _min_len_only_for_vowel_drop(self) -> Self:
        if self.min_len is not None and self.op != "vowel_drop":
            raise ValueError("'min_len' is only for vowel_drop")
        return self


class NoiseProfile(Spec):
    kind: Literal["NoiseProfile"]
    spec_version: Literal[1]
    id: Id
    version: SemVer
    lexicon: Ref
    operations: list[NoiseOp]
    protected_slots: bool = True

    @field_validator("id")
    @classmethod
    def _not_reserved(cls, value: str) -> str:
        if value == "none":
            raise ValueError("'none' is reserved for the built-in no-noise profile")
        return value


Templates = Annotated[list[str], Field(min_length=1)]


class LexiconEntry(Spec):
    canonical: str = Field(min_length=1)
    variants: dict[str, Annotated[float, Field(gt=0)]] = Field(min_length=1)


class Lexicon(Reviewed):
    kind: Literal["Lexicon"]
    spec_version: Literal[1]
    id: Id
    version: SemVer
    entries: list[LexiconEntry]
    amount_renderings: dict[str, Templates] = {}
    date_renderings: dict[str, Templates] = {}

    @model_validator(mode="after")
    def _check(self) -> Self:
        _no_duplicates("canonical word", (e.canonical for e in self.entries))
        for renderings, allowed in (
            (self.amount_renderings, AMOUNT_PLACEHOLDERS),
            (self.date_renderings, DATE_PLACEHOLDERS),
        ):
            for style, templates in renderings.items():
                for template in templates:
                    unknown = _placeholders(template) - allowed
                    if unknown:
                        raise ValueError(
                            f"style '{style}' uses unknown placeholder {sorted(unknown)}; "
                            f"allowed: {sorted(allowed)}"
                        )
        return self


class Spellings(Spec):
    roman: list[str] = []
    urdu: list[str] = []

    def words(self) -> list[str]:
        return [*self.roman, *self.urdu]

    @model_validator(mode="after")
    def _has_a_spelling(self) -> Self:
        if not self.words():
            raise ValueError("needs at least one spelling")
        return self


class NumberWord(Spellings):
    value: int = Field(ge=0, le=99)


class CountWord(Spellings):
    value: float = Field(gt=0)


class ModifierWord(Spellings):
    add: float


class MultiplierWord(Spellings):
    value: int = Field(ge=10)


class RelativeDay(Spellings):
    days: int = Field(ge=0)
    direction: Literal["past", "future", "either"]
    english: list[str] = []

    def words(self) -> list[str]:
        return [*self.roman, *self.urdu, *self.english]


class NumberWords(Reviewed):
    kind: Literal["NumberWords"]
    spec_version: Literal[1]
    id: Id
    version: SemVer
    digits: str = Field(min_length=10, max_length=10)  # script digits for 0-9, in order
    numbers: list[NumberWord] = Field(min_length=1)
    counts: list[CountWord] = []
    modifiers: list[ModifierWord] = []
    multipliers: list[MultiplierWord] = Field(min_length=1)
    relative_days: list[RelativeDay] = []

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(set(self.digits)) != 10:
            raise ValueError("digits must be 10 different characters")
        _no_duplicates("number value", (str(n.value) for n in self.numbers))
        # A spelling may mean only one thing, otherwise an amount reads two ways.
        amount_words: list[Spellings] = [
            *self.numbers,
            *self.counts,
            *self.modifiers,
            *self.multipliers,
        ]
        _no_duplicates("amount spelling", (w.casefold() for e in amount_words for w in e.words()))
        _no_duplicates(
            "relative-day spelling", (w.casefold() for d in self.relative_days for w in d.words())
        )
        return self


# --- Scenario -----------------------------------------------------------------------------

CANONICAL_FORM = {
    "money_pkr": "a positive whole number of rupees, e.g. 5000",
    "date": "an ISO date, e.g. 2026-11-09",
    "phone_pk": "E.164, e.g. +923001234567",
    "cnic": "13 digits without dashes",
}


def _is_canonical(kind: str, value: str | int) -> bool:
    if kind == "money_pkr":
        return isinstance(value, int) and not isinstance(value, bool) and value > 0
    if not isinstance(value, str):
        return False
    if kind == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if kind == "phone_pk":
        return re.fullmatch(r"\+92\d{10}", value) is not None
    return re.fullmatch(r"\d{13}", value) is not None  # cnic


class TypedFact(Spec):
    value: str | int
    type: Literal["money_pkr", "date", "phone_pk", "cnic"]

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        if not _is_canonical(self.type, self.value):
            raise ValueError(
                f"{self.type} fact must be {CANONICAL_FORM[self.type]}, got {self.value!r}"
            )
        return self


def _quoted(value: Any) -> Any:
    # An unquoted number in YAML would silently change (0417 loses its zero), so plain facts
    # must be strings.
    if not isinstance(value, str):
        raise ValueError(
            "plain facts must be quoted strings; use {value, type} for amounts, dates, "
            "phone numbers and CNICs"
        )
    return value


Fact = Annotated[
    Annotated[TypedFact, Tag("typed")] | Annotated[str, BeforeValidator(_quoted), Tag("plain")],
    Discriminator(_by_shape("typed", "plain")),
]


class Customer(Spec):
    goal: str
    known_facts: dict[FactKey, Fact] = {}
    hidden_facts: dict[FactKey, Fact] = {}
    give_up_after_unhelpful_turns: int = Field(ge=1)
    opening_intent: str
    seed_lines: list[str] = []

    @model_validator(mode="after")
    def _facts_consistent(self) -> Self:
        both = sorted(self.known_facts.keys() & self.hidden_facts.keys())
        if both:
            raise ValueError(f"facts in both known_facts and hidden_facts: {', '.join(both)}")
        facts = self.known_facts.keys() | self.hidden_facts.keys()
        for line in self.seed_lines:
            unknown = _placeholders(line) - facts
            if unknown:
                raise ValueError(f"seed line {line!r} uses unknown fact {sorted(unknown)}")
        return self


STATE_CHECKS = {"exists", "not_exists", "field_equals"}


class Assertion(Spec):
    assert_: str = Field(
        alias="assert",
        pattern=(
            r"^([a-z_]+\.(exists|not_exists|field_equals)"
            r"|complaint\.reference_shared_with_customer|customer\.goal_satisfied)$"
        ),
    )
    where: dict[str, Any] | None = None
    field: str | None = None
    value: Any = None

    @property
    def is_state_check(self) -> bool:
        return self.assert_.rsplit(".", 1)[1] in STATE_CHECKS

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.is_state_check != (self.where is not None):
            raise ValueError("'where' is required for exists, not_exists and field_equals only")
        if self.assert_.endswith(".field_equals"):
            if self.field is None or "value" not in self.model_fields_set:
                raise ValueError("field_equals needs 'field' and 'value'")
        elif self.field is not None or "value" in self.model_fields_set:
            raise ValueError("'field' and 'value' are only for field_equals")
        return self


class AnyOf(Spec):
    """A capability group: a call to any member satisfies it."""

    any_of: list[CapabilityId] = Field(min_length=2)


CapabilityRef = Annotated[
    Annotated[AnyOf, Tag("group")] | Annotated[CapabilityId, Tag("capability")],
    Discriminator(_by_shape("group", "capability")),
]
Scalar = str | int | float | bool


class AnyOfMatcher(Spec):
    any_of: list[Scalar] = Field(min_length=1)


class PresentMatcher(Spec):
    present: Literal[True]


class RangeMatcher(Spec):
    range: tuple[float, float] | tuple[str, str]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        match self.range:
            case (float() as low, float() as high) if low > high:
                raise ValueError("range start is after its end")
            case (str() as low, str() as high) if low > high:
                raise ValueError("range start is after its end")
        return self


MATCHER_KEYS = ("any_of", "present", "range")


def _matcher_tag(value: Any) -> str | None:
    if isinstance(value, BaseModel):
        return next(key for key in MATCHER_KEYS if key in type(value).model_fields)
    if isinstance(value, dict):
        return next((key for key in MATCHER_KEYS if key in value), None)
    return "exact"


Matcher = Annotated[
    Annotated[AnyOfMatcher, Tag("any_of")]
    | Annotated[PresentMatcher, Tag("present")]
    | Annotated[RangeMatcher, Tag("range")]
    | Annotated[Scalar, Tag("exact")],
    Discriminator(
        _matcher_tag,
        custom_error_type="invalid_matcher",
        custom_error_message="an arg matcher is a value, {any_of: [...]}, {present: true} "
        "or {range: [low, high]}",
    ),
]


class RequiredAction(Spec):
    capability: CapabilityRef
    args: dict[str, Matcher] = {}


class ForbiddenAction(Spec):
    capability: CapabilityId


class OrderRule(Spec):
    before: tuple[CapabilityRef, CapabilityRef]


def capability_members(ref: CapabilityRef) -> list[str]:
    """The capability ids a reference covers: one, or every member of a group."""
    return ref.any_of if isinstance(ref, AnyOf) else [ref]


class ActionExpectations(Spec):
    required: list[RequiredAction] = []
    forbidden: list[ForbiddenAction] = []
    order: list[OrderRule] = []
    allow_extra_read_only_calls: bool = False
    allowed: list[CapabilityId] = []

    @model_validator(mode="after")
    def _no_contradictions(self) -> Self:
        forbidden = {f.capability for f in self.forbidden}
        required = {c for r in self.required for c in capability_members(r.capability)}
        for what, names in (("required", required), ("allowed", set(self.allowed))):
            clash = sorted(names & forbidden)
            if clash:
                raise ValueError(f"capabilities both {what} and forbidden: {', '.join(clash)}")
        return self


class Compliance(Spec):
    rules: list[Id] = []


class Escalation(Spec):
    expected: bool


class Expectations(Spec):
    outcome: list[Assertion] = Field(min_length=1)
    action: ActionExpectations
    compliance: Compliance
    escalation: Escalation
    max_turns: int = Field(ge=1)

    @model_validator(mode="after")
    def _goal_needs_state(self) -> Self:
        asks_goal = any(a.assert_ == "customer.goal_satisfied" for a in self.outcome)
        if asks_goal and not any(a.is_state_check for a in self.outcome):
            raise ValueError("customer.goal_satisfied needs a state assertion alongside it")
        return self


class Scenario(Reviewed):
    kind: Literal["Scenario"]
    spec_version: Literal[1]
    id: Id
    pack: Id
    version: SemVer
    split: Literal["public", "holdout"]
    tags: list[str] = []
    title: str
    clock: AwareDatetime
    customer: Customer
    fixtures: dict[str, Any]  # shape is owned by the domain's mock backend
    expectations: Expectations


# --- Pack ---------------------------------------------------------------------------------


class Pack(Spec):
    kind: Literal["Pack"]
    spec_version: Literal[1]
    name: Id
    version: SemVer
    catalog: Ref
    mock_backend: Ref
    number_words: Ref
    scenarios: list[str] = Field(min_length=1)  # glob patterns, relative to the pack file
    personas: list[Id] = Field(min_length=1)
    behaviors: list[Id] = Field(min_length=1)


SpecDoc = Annotated[
    CapabilityCatalog
    | AgentManifest
    | Persona
    | Behavior
    | NoiseProfile
    | Lexicon
    | NumberWords
    | Scenario
    | Pack,
    Field(discriminator="kind"),
]
_SPEC_DOC: TypeAdapter[SpecDoc] = TypeAdapter(SpecDoc, config=ConfigDict(title="spec file"))


def parse_spec(data: Any) -> SpecDoc:
    """Validate one parsed YAML document; its `kind` picks the model."""
    return _SPEC_DOC.validate_python(data)
