"""Spec models: every example file validates on its own, and broken files fail with errors that
say what is wrong. Broken files are made by changing one field of a valid example."""

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from talkaudit.core.models.specs import AnyOf, Scenario, TypedFact, parse_spec

EXAMPLES = Path(__file__).parents[2] / "examples"
DELETE = object()


def documents(path: Path) -> list[Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def example(name: str, index: int = 0) -> Any:
    return copy.deepcopy(documents(EXAMPLES / name)[index])


def changed(doc: Any, path: str, value: Any) -> Any:
    *parents, last = path.split(".")
    node = doc
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    key: Any = int(last) if isinstance(node, list) else last
    if value is DELETE:
        del node[key]
    else:
        node[key] = value
    return doc


SCENARIO = "scenarios/banking/failed_transfer_01.yaml"
LOST_CARD = "scenarios/banking/lost_card_01.yaml"
CATALOG = "capabilities/banking.yaml"
MANIFEST = "manifests/acme-bank-bot.yaml"
PERSONAS = "personas/personas.yaml"
NOISE = "noise/sms_heavy.yaml"
LEXICON = "noise/roman_urdu_variants.sample.yaml"
NUMBERS = "numbers/urdu_numbers.sample.yaml"

BROKEN = [
    # (file, change at path, new value, fragment the error must contain)
    (SCENARIO, "kind", "Scenaro", "'Scenaro'"),
    (SCENARIO, "spec_version", 2, "spec_version"),
    (SCENARIO, "expectation", {}, "Extra inputs are not permitted"),
    (SCENARIO, "expectations.max_turns", DELETE, "max_turns"),
    (SCENARIO, "clock", "2026-11-10T11:00:00", "timezone"),
    (SCENARIO, "status", "approved", "needs at least one name in reviewed_by"),
    (SCENARIO, "customer.known_facts.amount_pkr.value", "5k", "positive whole number of rupees"),
    (SCENARIO, "customer.known_facts.when.value", "kal", "ISO date"),
    (SCENARIO, "customer.hidden_facts.card_last4", 4417, "plain facts must be quoted strings"),
    (
        SCENARIO,
        "expectations.action.required.1.args.amount_pkr",
        {"between": [1, 2]},
        "an arg matcher is a value",
    ),
    (SCENARIO, "customer.hidden_facts.amount_pkr", "5000", "both known_facts and hidden_facts"),
    (SCENARIO, "customer.seed_lines.1", "transfer kiya tha {amount} ka", "unknown fact"),
    (
        SCENARIO,
        "expectations.action.forbidden.0.capability",
        "complaint.create",
        "both required and forbidden",
    ),
    (SCENARIO, "expectations.action.allowed", ["card.block"], "both allowed and forbidden"),
    (
        SCENARIO,
        "expectations.action.required.0.capability",
        {"any_of": ["transaction.find"]},
        "at least 2 items",
    ),
    (
        SCENARIO,
        "expectations.action.required.1.args.amount_pkr",
        {"range": [6000, 4000]},
        "range start is after its end",
    ),
    (
        SCENARIO,
        "expectations.outcome",
        [{"assert": "customer.goal_satisfied"}],
        "needs a state assertion",
    ),
    (SCENARIO, "expectations.outcome.0.assert", "complaint.made", "String should match pattern"),
    (LOST_CARD, "expectations.outcome.0.value", DELETE, "field_equals needs"),
    (
        LOST_CARD,
        "customer.hidden_facts.registered_phone.value",
        "03000000077",
        "E.164",
    ),
    (CATALOG, "capabilities.3.args.date.date_direction", DELETE, "date_direction"),
    (CATALOG, "capabilities.0.args.method.values", DELETE, "need non-empty 'values'"),
    (CATALOG, "capabilities.1.id", "customer.verify", "duplicate capability id"),
    (CATALOG, "capabilities.7.args.card_last4.pattern", "^[0-9{4}$", "not a valid regex"),
    (CATALOG, "capabilities.1.kind", "query", "capabilities.1.kind"),
    (MANIFEST, "mappings.0.tools", ["verify_v2"], "exactly one of 'tool' or 'tools'"),
    (MANIFEST, "mappings.1.tool", "verify_customer", "mapped to more than one capability"),
    (
        MANIFEST,
        "mappings.2.args.amount_pkr.transform",
        "rupees_to_dollars",
        "Input should be 'paisa_to_rupees'",
    ),
    (NOISE, "id", "none", "reserved"),
    (NOISE, "operations.0.op", "shout", "operations.0.op"),
    (NOISE, "operations.0.probability", 1.5, "less than or equal to 1"),
    (LEXICON, "amount_renderings.short_k", ["{amount}k"], "unknown placeholder"),
    (LEXICON, "entries.1.canonical", "nahi", "duplicate canonical word"),
    (NUMBERS, "numbers.1.roman", ["ek"], "duplicate amount spelling"),
    (NUMBERS, "digits", "0123", "at least 10 characters"),
]


@pytest.mark.parametrize(
    ("name", "path", "value", "fragment"), BROKEN, ids=[f"{c[0]}:{c[1]}" for c in BROKEN]
)
def test_broken_file_gives_clear_error(name: str, path: str, value: Any, fragment: str) -> None:
    with pytest.raises(ValidationError) as error:
        parse_spec(changed(example(name), path, value))
    assert fragment in str(error.value)


def test_persona_needs_date_styles() -> None:
    persona = changed(example(PERSONAS, 2), "date_styles", DELETE)
    with pytest.raises(ValidationError, match="date_styles"):
        parse_spec(persona)


def test_typed_facts_and_groups_parse() -> None:
    scenario = parse_spec(example(SCENARIO))
    assert isinstance(scenario, Scenario)
    amount = scenario.customer.known_facts["amount_pkr"]
    assert isinstance(amount, TypedFact) and amount.value == 5000
    group = scenario.expectations.action.required[0].capability
    assert isinstance(group, AnyOf) and group.any_of == ["transaction.find", "transaction.list"]
