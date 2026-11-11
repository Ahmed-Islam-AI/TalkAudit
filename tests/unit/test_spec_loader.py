"""Spec loader: packs/ resolves fully, examples/ loads file by file, hashes are stable, and
reference problems name the files involved. Edits happen on a temp copy of packs/."""

import shutil
from pathlib import Path

import pytest

from talkaudit.core.errors import PackNotFoundError, SpecError
from talkaudit.core.models.specs import Scenario, TypedFact
from talkaudit.core.specs.loader import Library, ResolvedPack, load_file, resolve_pack

ROOT = Path(__file__).parents[2]
PACKS = ROOT / "packs"
EXAMPLES = ROOT / "examples"
LOST_CARD = "scenarios/banking-core/lost_card_01.yaml"
FAILED_TRANSFER = "scenarios/banking-core/failed_transfer_01.yaml"


@pytest.fixture
def packs(tmp_path: Path) -> Path:
    return Path(shutil.copytree(PACKS, tmp_path / "packs"))


def resolve(root: Path, name: str = "banking-core") -> ResolvedPack:
    return resolve_pack(Library.scan(root), name)


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def problems(root: Path) -> str:
    with pytest.raises(SpecError) as error:
        resolve(root)
    return str(error.value)


# --- packs/ and examples/ ------------------------------------------------------------------


def test_every_pack_in_packs_resolves() -> None:
    library = Library.scan(PACKS)
    assert [pack.name for pack in library.packs()] == ["banking-core"]
    pack = resolve_pack(library, "banking-core")
    assert [s.id for s in pack.scenarios] == [
        "atm_cash_not_dispensed_01",
        "failed_transfer_01",
        "lost_card_01",
    ]
    assert [p.id for p in pack.personas] == [
        "urdu_script",
        "roman_clean",
        "roman_messy",
        "code_switch",
        "english",
        "voice_note",
    ]
    assert [b.id for b in pack.behaviors] == ["default", "impatient", "vague"]
    profile = pack.noise_profiles["roman_messy"]
    lexicon = pack.lexicons["english"]
    assert profile is not None and profile.id == "sms_heavy"
    assert lexicon is not None and lexicon.id == "english_basic"
    assert pack.ref == "banking-core@0.1.0"


@pytest.mark.parametrize(
    "path", sorted(EXAMPLES.rglob("*.yaml")), ids=lambda p: p.relative_to(EXAMPLES).as_posix()
)
def test_every_example_loads_on_its_own(path: Path) -> None:
    assert load_file(path)


# --- content hashes ------------------------------------------------------------------------


def test_hashes_are_sha256() -> None:
    hashes = resolve(PACKS).hashes
    assert all(h.startswith("sha256:") for h in (hashes.pack, hashes.personas, hashes.noise))


def test_same_content_same_hash(packs: Path) -> None:
    before = resolve(packs).hashes
    edit(packs / LOST_CARD, "kind: Scenario", "# a comment\nkind:    Scenario")
    assert resolve(packs).hashes == before


def test_changed_scenario_changes_only_the_pack_hash(packs: Path) -> None:
    before = resolve(packs).hashes
    edit(packs / LOST_CARD, "balance_pkr: 61200", "balance_pkr: 61300")
    after = resolve(packs).hashes
    assert after.pack != before.pack
    assert (after.personas, after.noise) == (before.personas, before.noise)


def test_changed_persona_and_lexicon_change_their_hashes(packs: Path) -> None:
    before = resolve(packs).hashes
    edit(packs / "personas/personas.yaml", "kb tk ho jaega ye", "kb tak ho jaega")
    edit(packs / "noise/roman_urdu_variants.yaml", "abhe: 0.1", "abhe: 0.2")
    after = resolve(packs).hashes
    assert after.pack == before.pack
    assert after.personas != before.personas
    assert after.noise != before.noise


# --- reference problems --------------------------------------------------------------------


def test_missing_reference_names_referring_file_and_missing_id(packs: Path) -> None:
    (packs / "noise/light_roman.yaml").unlink()
    message = problems(packs)
    assert "personas.yaml" in message and "'light_roman' not found" in message


def test_style_missing_from_lexicon_names_both_files(packs: Path) -> None:
    edit(packs / "noise/english_basic.yaml", '  day_month: ["{d} {mon}"]\n', "")
    message = problems(packs)
    assert "personas.yaml" in message and "english_basic.yaml" in message
    assert "date style 'day_month'" in message


def test_unknown_capability_names_scenario_and_catalog(packs: Path) -> None:
    edit(packs / LOST_CARD, "capability: transfer.create", "capability: transfer.send")
    message = problems(packs)
    assert "lost_card_01.yaml" in message and "banking.yaml" in message
    assert "'transfer.send'" in message


def test_group_matcher_needs_the_arg_on_every_member(packs: Path) -> None:
    group = "      - capability: { any_of: [transaction.find, transaction.list] }"
    edit(packs / FAILED_TRANSFER, group, group + "\n        args: { amount_pkr: 5000 }")
    message = problems(packs)
    assert "arg 'amount_pkr'" in message and "transaction.list" in message


def test_allowed_must_be_a_write_capability(packs: Path) -> None:
    edit(packs / LOST_CARD, "allowed: []", "allowed: [card.status.get]")
    assert "only write capabilities need allowing" in problems(packs)


def test_scenario_must_name_its_pack(packs: Path) -> None:
    edit(packs / LOST_CARD, "pack: banking-core", "pack: other-pack")
    assert "says pack 'other-pack'" in problems(packs)


def test_every_problem_is_reported_at_once(packs: Path) -> None:
    (packs / "noise/light_roman.yaml").unlink()
    (packs / "noise/light_urdu.yaml").unlink()
    with pytest.raises(SpecError) as error:
        resolve(packs)
    message = str(error.value)
    assert "'light_roman' not found" in message and "'light_urdu' not found" in message
    assert len(error.value.problems) >= 2


def test_bare_reference_to_several_versions_must_be_pinned(packs: Path) -> None:
    newer = packs / "noise/light_roman_v2.yaml"
    shutil.copy(packs / "noise/light_roman.yaml", newer)
    edit(newer, "version: 0.1.0", "version: 0.2.0")
    assert "matches versions 0.1.0, 0.2.0; pin one with @version" in problems(packs)


def test_same_document_in_two_files_names_both(packs: Path) -> None:
    shutil.copy(packs / "noise/light_roman.yaml", packs / "noise/copy.yaml")
    with pytest.raises(SpecError) as error:
        Library.scan(packs)
    message = str(error.value)
    assert "light_roman.yaml" in message and "copy.yaml" in message


def test_unknown_pack(packs: Path) -> None:
    with pytest.raises(PackNotFoundError):
        resolve(packs, "telecom-core")


# --- YAML reading --------------------------------------------------------------------------


def test_duplicate_yaml_key_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "behavior.yaml"
    path.write_text(
        "kind: Behavior\nspec_version: 1\nid: a\nid: b\ndescription: x\nrules: [y]\n",
        encoding="utf-8",
    )
    with pytest.raises(SpecError, match="duplicate key 'id'"):
        load_file(path)


def test_unquoted_dates_stay_strings(packs: Path) -> None:
    path = packs / FAILED_TRANSFER
    edit(path, 'value: "2026-11-09"', "value: 2026-11-09")
    scenario = load_file(path)[0].spec
    assert isinstance(scenario, Scenario)
    when = scenario.customer.known_facts["when"]
    assert isinstance(when, TypedFact) and when.value == "2026-11-09"


def test_invalid_yaml_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("kind: [Scenario\n", encoding="utf-8")
    with pytest.raises(SpecError, match="broken.yaml: invalid YAML"):
        load_file(path)


def test_holdout_directories_are_not_scanned(packs: Path) -> None:
    (packs / "holdout").mkdir()
    (packs / "holdout" / "unreadable.yaml").write_text("kind: NotASpec\n", encoding="utf-8")
    assert Library.scan(packs).packs()
