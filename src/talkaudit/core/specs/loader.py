"""Load spec files and resolve packs (docs/07-SCENARIO-SPEC.md §0 and §8).

Loading is synchronous on purpose: it runs once before a run starts, never inside the async
conversation loop.
"""

import glob
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from talkaudit.core.errors import PackNotFoundError, SpecError
from talkaudit.core.models.specs import (
    AgentManifest,
    Behavior,
    CapabilityCatalog,
    Lexicon,
    NoiseProfile,
    NumberWords,
    Pack,
    Persona,
    Scenario,
    SpecDoc,
    capability_members,
    parse_spec,
)

# --- YAML ----------------------------------------------------------------------------------


class _YamlLoader(yaml.SafeLoader):
    """Safe YAML with two changes: unquoted dates stay strings (so they validate like quoted
    ones), and a duplicate key is an error instead of silently keeping the last value."""


_YamlLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _mapping_without_duplicates(loader: yaml.SafeLoader, node: yaml.Node) -> dict[Any, Any]:
    if not isinstance(node, yaml.MappingNode):
        raise yaml.constructor.ConstructorError(None, None, "expected a mapping", node.start_mark)
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return loader.construct_mapping(node, deep=True)


_YamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_without_duplicates
)


# --- Files and the library -----------------------------------------------------------------


@dataclass(frozen=True)
class Document:
    path: Path
    data: Any  # the parsed YAML; hashed for the run manifest
    spec: SpecDoc


def _ident(spec: SpecDoc) -> str:
    if isinstance(spec, CapabilityCatalog):
        return spec.domain
    if isinstance(spec, AgentManifest | Pack):
        return spec.name
    return spec.id


def _version(spec: SpecDoc) -> str:
    return "" if isinstance(spec, Behavior | AgentManifest) else spec.version


def _key(spec: SpecDoc) -> tuple[str, str, str]:
    return spec.kind, _ident(spec), _version(spec)


def load_file(path: Path) -> list[Document]:
    """Read one spec file (a document or a list of documents) and validate each document."""
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_YamlLoader)
    except yaml.YAMLError as error:
        raise SpecError([f"{path}: invalid YAML: {error}"]) from None
    if data is None:
        raise SpecError([f"{path}: file is empty"])
    items = data if isinstance(data, list) else [data]
    documents: list[Document] = []
    problems: list[str] = []
    for number, item in enumerate(items, start=1):
        where = f"{path} (document {number})" if isinstance(data, list) else str(path)
        try:
            documents.append(Document(path, item, parse_spec(item)))
        except ValidationError as error:
            # Messages only, no input values: they could carry holdout content into logs.
            for e in error.errors(include_url=False, include_input=False):
                problems.append(f"{where}: {'.'.join(map(str, e['loc']))}: {e['msg']}")
    if problems:
        raise SpecError(problems)
    return documents


class Library:
    """Every spec document under a root, indexed by kind, id and version."""

    def __init__(self, documents: Iterable[Document]) -> None:
        self._documents: dict[tuple[str, str, str], Document] = {}
        problems = []
        for doc in documents:
            key = _key(doc.spec)
            if key in self._documents:
                kind, ident, version = key
                problems.append(
                    f"{kind} '{ident}{'@' + version if version else ''}' is defined in both "
                    f"{self._documents[key].path} and {doc.path}"
                )
            self._documents.setdefault(key, doc)
        if problems:
            raise SpecError(problems)

    @classmethod
    def scan(cls, root: Path) -> "Library":
        """Load every *.yaml under root. Directories named holdout/ are skipped: holdout
        scenarios are read only through a pack's scenario globs."""
        documents: list[Document] = []
        problems: list[str] = []
        for path in sorted(root.rglob("*.yaml")):
            if "holdout" in path.relative_to(root).parts:
                continue
            try:
                documents += load_file(path)
            except SpecError as error:
                problems += error.problems
        if problems:
            raise SpecError(problems)
        return cls(documents)

    def packs(self) -> list[Pack]:
        return [doc.spec for doc in self._documents.values() if isinstance(doc.spec, Pack)]

    def find[T: BaseModel](self, kind: type[T], ref: str) -> tuple[Document, T]:
        """Resolve `id` or `id@1.2.3`. Raises LookupError saying why it doesn't resolve."""
        ident, _, version = ref.partition("@")
        if version and version.count(".") != 2:
            raise LookupError(f"'{ref}' needs a full version, e.g. {ident}@1.0.0")
        matches = [
            doc
            for (k, i, v), doc in self._documents.items()
            if k == kind.__name__ and i == ident and (not version or v == version)
        ]
        if not matches:
            raise LookupError(f"{kind.__name__} '{ref}' not found")
        if len(matches) > 1:
            versions = ", ".join(sorted(_version(doc.spec) for doc in matches))
            raise LookupError(
                f"{kind.__name__} '{ref}' matches versions {versions}; pin one with @version"
            )
        spec = matches[0].spec
        if not isinstance(spec, kind):  # kind names equal class names, so this can't happen
            raise LookupError(f"{kind.__name__} '{ref}' is a {spec.kind}")
        return matches[0], spec


# --- Packs ---------------------------------------------------------------------------------


class PackHashes(BaseModel):
    """SHA-256 over the parsed YAML, so comments and formatting don't change a hash."""

    model_config = ConfigDict(frozen=True)

    pack: str  # pack file, catalog, number words, scenarios
    personas: str  # personas, behaviors
    noise: str  # noise profiles, lexicons


class ResolvedPack(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack: Pack
    catalog: CapabilityCatalog
    number_words: NumberWords
    scenarios: list[Scenario]  # sorted by id
    personas: list[Persona]  # in pack order
    behaviors: list[Behavior]
    noise_profiles: dict[str, NoiseProfile | None]  # by persona id; None for reserved "none"
    lexicons: dict[str, Lexicon | None]  # by persona id
    hashes: PackHashes

    @property
    def ref(self) -> str:
        return f"{self.pack.name}@{self.pack.version}"


def resolve_pack(library: Library, ref: str) -> ResolvedPack:
    """Resolve a pack and everything it uses. Every problem is reported at once."""
    try:
        pack_doc, pack = library.find(Pack, ref)
    except LookupError as error:
        raise PackNotFoundError(str(error)) from None
    return _Resolver(library, pack_doc, pack).resolve()


def _hash(data: Iterable[Any]) -> str:
    text = json.dumps(list(data), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Resolver:
    """Resolves one pack, collecting problems instead of stopping at the first."""

    def __init__(self, library: Library, pack_doc: Document, pack: Pack) -> None:
        self.library = library
        self.pack_doc = pack_doc
        self.pack = pack
        self.problems: list[str] = []
        self.used: dict[str, dict[tuple[str, str, str], Document]] = {}

    def use(self, group: str, doc: Document) -> None:
        self.used.setdefault(group, {})[_key(doc.spec)] = doc

    def hash(self, group: str) -> str:
        docs = self.used.get(group, {})
        return _hash(docs[key].data for key in sorted(docs))

    def need[T: BaseModel](
        self, kind: type[T], ref: str, referrer: Document, what: str, group: str
    ) -> tuple[Document, T] | None:
        try:
            doc, spec = self.library.find(kind, ref)
        except LookupError as error:
            self.problems.append(f"{referrer.path}: {what}: {error}")
            return None
        self.use(group, doc)
        return doc, spec

    def resolve(self) -> ResolvedPack:
        pack_doc, pack = self.pack_doc, self.pack
        self.use("pack", pack_doc)
        catalog = self.need(CapabilityCatalog, pack.catalog, pack_doc, "catalog", "pack")
        numbers = self.need(NumberWords, pack.number_words, pack_doc, "number_words", "pack")
        personas = [
            found
            for persona_id in pack.personas
            if (found := self.need(Persona, persona_id, pack_doc, "persona", "personas"))
        ]
        behaviors = [
            found_behavior
            for behavior_id in pack.behaviors
            if (
                found_behavior := self.need(Behavior, behavior_id, pack_doc, "behavior", "personas")
            )
        ]
        noise = {persona.id: self.noise_for(doc, persona) for doc, persona in personas}
        scenarios = self.scenarios(catalog)
        # The mock_backend ref names code, not a file; the runner checks it.
        if self.problems or catalog is None or numbers is None:
            raise SpecError(self.problems)
        return ResolvedPack(
            pack=pack,
            catalog=catalog[1],
            number_words=numbers[1],
            scenarios=sorted(scenarios, key=lambda s: s.id),
            personas=[persona for _, persona in personas],
            behaviors=[behavior for _, behavior in behaviors],
            noise_profiles={pid: profile for pid, (profile, _) in noise.items()},
            lexicons={pid: lexicon for pid, (_, lexicon) in noise.items()},
            hashes=PackHashes(
                pack=self.hash("pack"), personas=self.hash("personas"), noise=self.hash("noise")
            ),
        )

    def noise_for(
        self, doc: Document, persona: Persona
    ) -> tuple[NoiseProfile | None, Lexicon | None]:
        if persona.noise_profile == "none":
            return None, None
        what = f"persona '{persona.id}' noise_profile"
        found_profile = self.need(NoiseProfile, persona.noise_profile, doc, what, "noise")
        if found_profile is None:
            return None, None
        profile_doc, profile = found_profile
        what = f"noise profile '{profile.id}' lexicon"
        found_lexicon = self.need(Lexicon, profile.lexicon, profile_doc, what, "noise")
        if found_lexicon is None:
            return profile, None
        lexicon_doc, lexicon = found_lexicon
        for style_kind, styles, defined in (
            ("amount", persona.amount_styles, lexicon.amount_renderings),
            ("date", persona.date_styles, lexicon.date_renderings),
        ):
            for style in styles:
                if style not in defined:
                    self.problems.append(
                        f"{doc.path}: persona '{persona.id}' uses {style_kind} style '{style}', "
                        f"which lexicon '{lexicon.id}' in {lexicon_doc.path} does not define"
                    )
        return profile, lexicon

    def scenarios(self, catalog: tuple[Document, CapabilityCatalog] | None) -> list[Scenario]:
        found: list[Scenario] = []
        seen: dict[str, Path] = {}
        for pattern in self.pack.scenarios:
            # stdlib glob, not Path.glob: patterns may climb out of the pack dir with "..".
            paths = sorted(Path(p) for p in glob.glob(str(self.pack_doc.path.parent / pattern)))
            if not paths:
                self.problems.append(
                    f"{self.pack_doc.path}: scenarios pattern '{pattern}' matches no files"
                )
            for path in paths:
                try:
                    documents = load_file(path)
                except SpecError as error:
                    self.problems += error.problems
                    continue
                for doc in documents:
                    scenario = doc.spec
                    if not isinstance(scenario, Scenario):
                        self.problems.append(f"{path}: expected a Scenario, found {scenario.kind}")
                        continue
                    if scenario.id in seen:
                        self.problems.append(
                            f"scenario '{scenario.id}' is defined in both {seen[scenario.id]} "
                            f"and {path}"
                        )
                        continue
                    seen[scenario.id] = path
                    self.use("pack", doc)
                    self.check_scenario(doc, scenario, catalog)
                    found.append(scenario)
        return found

    def check_scenario(
        self,
        doc: Document,
        scenario: Scenario,
        catalog: tuple[Document, CapabilityCatalog] | None,
    ) -> None:
        where = f"{doc.path}: scenario '{scenario.id}'"
        if scenario.pack != self.pack.name:
            self.problems.append(
                f"{where} says pack '{scenario.pack}', but pack '{self.pack.name}' "
                f"({self.pack_doc.path}) loads it"
            )
        if catalog is None:
            return
        catalog_doc, catalog_spec = catalog
        source = f"catalog '{catalog_spec.domain}@{catalog_spec.version}' in {catalog_doc.path}"
        capabilities = {c.id: c for c in catalog_spec.capabilities}
        action = scenario.expectations.action
        named = [
            *(m for r in action.required for m in capability_members(r.capability)),
            *(f.capability for f in action.forbidden),
            *(m for rule in action.order for ref in rule.before for m in capability_members(ref)),
            *action.allowed,
        ]
        for name in dict.fromkeys(named):
            if name not in capabilities:
                self.problems.append(
                    f"{where} uses capability '{name}', which {source} does not define"
                )
        for required in action.required:
            members = [m for m in capability_members(required.capability) if m in capabilities]
            for arg in required.args:
                lacking = [m for m in members if arg not in capabilities[m].args]
                if lacking:
                    self.problems.append(
                        f"{where} matches arg '{arg}', which {', '.join(lacking)} "
                        f"in {source} does not have"
                    )
        for name in action.allowed:
            if name in capabilities and capabilities[name].kind != "write":
                self.problems.append(
                    f"{where} allows '{name}', but only write capabilities need allowing "
                    f"('{name}' is {capabilities[name].kind} in {source})"
                )
