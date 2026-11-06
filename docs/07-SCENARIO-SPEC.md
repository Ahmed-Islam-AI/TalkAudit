# 07 — Scenario and Spec Formats

Every content file is YAML with a `kind` and `spec_version`. Pydantic models in `talkaudit.core.models` are the source of truth; this document explains them. Format samples live in `examples/`. Real content lives only in `packs/`. Tests load every file in both.

## 0. Common rules

**Review status.** Native-speaker content (`Persona`, `Scenario`, `Lexicon`, `NumberWords`) has two more fields:

```yaml
status: draft          # draft | approved
reviewed_by: []        # native speakers who reviewed this version
```

New content always starts as `draft` with `reviewed_by: []`. Only a native-speaker review sets `approved`. A pack version is released only when everything it uses is `approved`.

**References.** Files refer to each other by `id@version` (`catalog: banking@1.0.0`) or by bare id (`noise_profile: sms_heavy`). A bare id resolves only if exactly one version of it is loaded. Each file validates on its own; references are resolved when a pack loads, and a missing reference is an error that names the referring file and the missing id.

## 1. Capability catalog

Defines the business actions of a domain, independent of any company.

```yaml
kind: CapabilityCatalog
spec_version: 1
domain: banking
version: 1.0.0
capabilities:
  - id: customer.verify
    description: Verify the customer's identity using allowed factors
    kind: auth
    args:
      method: { type: enum, values: [registered_phone, card_last4, dob], required: true }
      value:  { type: string, required: true }
  - id: card.block
    description: Block or freeze a card
    kind: write
    args:
      card_last4: { type: string, pattern: "^[0-9]{4}$", required: true }
      reason:     { type: enum, values: [lost, stolen, suspicious, other], required: true }
    side_effects: [card.status -> blocked]
    sensitive: true
  - id: transaction.find
    description: Find a transaction by amount and/or date
    kind: read
    args:
      amount_pkr: { type: money_pkr, required: false }
      date:       { type: date, date_direction: past, required: false }
```

Every capability has a `kind`. The action grader uses it to judge calls the scenario didn't ask for:

| `kind` | Meaning | As an extra call |
|---|---|---|
| `read` | No side effects | Allowed when the scenario sets `allow_extra_read_only_calls` |
| `write` | Changes state | Fails as `extra_write` unless listed in the scenario's `action.allowed` |
| `auth` | Verifies the customer's identity | Always allowed |

Special argument types with built-in normalization:

| Type | Accepts from agent | Normalized to |
|---|---|---|
| `money_pkr` | `5000`, `"5,000"`, `"1,50,000"`, `"Rs. 5000"`, `"5k"`, `5000.0`, number words and Urdu digits (`"paanch hazar"`, `"dairh lakh"`, `"۵۰۰۰"`, see §6), paisa if manifest says so | integer rupees |
| `date` | ISO, relative words (`"yesterday"`, `"kal"`) resolved against the scenario clock in the argument's `date_direction`, common local formats | ISO date |
| `phone_pk` | `03xx…`, `+923xx…`, with or without dashes | E.164 |
| `cnic` | with or without dashes | 13 digits (synthetic only) |
| `enum` | case-insensitive, synonyms from catalog | canonical value |

Every `date` argument declares `date_direction: past | future`. "kal" means yesterday for a `past` argument and tomorrow for a `future` one. A relative word that contradicts the direction ("tomorrow" for a `past` argument) fails normalization.

## 2. Agent manifest

Written by the company once. Maps capabilities to their real tools.

```yaml
kind: AgentManifest
spec_version: 1
name: acme-bank-bot
catalog: banking@1.0.0
mappings:
  - capability: card.block
    tool: freeze_card
    args:
      card_last4: cardLast4
      reason: { from: reason, map: { lost: LOST, stolen: STOLEN, suspicious: FRAUD, other: OTHER } }
  - capability: transaction.find
    tools: [search_txn, search_txn_v2]   # either satisfies it
    args:
      amount_pkr: { from: amount, transform: paisa_to_rupees }
      date: txnDate
  - capability: transaction.list
    tool: get_recent_transactions
    args: { account_id: accountId, days: days }
unmapped_tools: ignore     # ignore | record | fail
```

Map each tool to the capability it actually performs. A tool that lists recent transactions is `transaction.list`, even when the agent uses it to find one transaction; scenarios accept either path with a capability group (§7).

`talkaudit validate manifest.yaml` checks every capability used by the selected pack is mapped, argument names exist, transforms are known.

## 3. Persona

```yaml
kind: Persona
spec_version: 1
id: roman_messy
version: 1.0.0
status: draft
reviewed_by: []
label: Messy SMS-style Roman Urdu
language_style:
  primary: roman_urdu
  script: latin
  english_mixing: medium        # none | low | medium | high
  switches_mid_sentence: true
literacy: low_formal            # affects grammar, punctuation
register: informal              # informal | polite | formal
noise_profile: sms_heavy
amount_styles: [short_k, digits_no_comma, urdu_words]
date_styles: [relative, numeric]
seed_lines:                     # written by native speakers, used as style examples
  - "mra card kho gya h usko band krdo plz"
  - "paise kat gye h lekn transfer nai hua"
  - "kb tk ho jaega ye"
forbidden:
  - mentions being an AI or a test
  - perfect grammar and punctuation
```

`amount_styles` and `date_styles` name renderings defined in the noise profile's lexicon (§5). When a style can't render a value (no relative word for a date ten days back), the next style in the list is used.

Initial persona set: `urdu_script`, `roman_clean`, `roman_messy`, `code_switch`, `english`, `voice_note`.

## 4. Behavior

Applied on top of any persona.

```yaml
kind: Behavior
spec_version: 1
id: vague
description: Gives incomplete information first, needs follow-up questions
rules:
  - reveal at most one fact per message
  - first message describes the problem without amounts or dates
  - if asked two things at once, answer only one
```

Initial set: `default`, `impatient` (short replies, threatens to leave after 3 unhelpful turns), `vague`, `changes_mind` (corrects a fact once mid-conversation), `elderly_polite` (long polite messages, unsure about app terms).

## 5. Noise profile and lexicon

Deterministic, seeded. Applied after the planner's placeholders are filled.

```yaml
kind: NoiseProfile
spec_version: 1
id: sms_heavy
version: 1.0.0
lexicon: roman_urdu_variants@0.1.0
operations:
  - { op: spelling_variant, probability: 0.6 }     # nahi → nai/nhi/nahin
  - { op: vowel_drop, probability: 0.3, min_len: 4 } # kardo → krdo
  - { op: abbreviation, probability: 0.4 }         # please → plz, kya → kia
  - { op: drop_punctuation, probability: 0.8 }
  - { op: lowercase, probability: 0.9 }
  - { op: typo, probability: 0.05 }                # adjacent-key swap
protected_slots: true   # never corrupt fact slots beyond their allowed render styles
```

`none` is a reserved profile id: no operations and no lexicon, so facts appear as plain values. Use it in tests. A real persona that needs no noise uses a profile with `operations: []` and a lexicon, because the lexicon also says how amounts and dates are written.

A lexicon lists canonical words with observed variants and rough frequency weights, plus the amount and date renderings for its language. Build the variants from real public text and native speaker input, not from an LLM alone.

```yaml
kind: Lexicon
spec_version: 1
id: roman_urdu_variants
version: 0.1.0
status: draft
reviewed_by: []
entries:
  - { canonical: nahi, variants: { nahi: 0.35, nai: 0.25, nhi: 0.3, nahin: 0.1 } }
amount_renderings:                 # names used by persona amount_styles
  short_k:           ["{k}k", "{k}K"]
  digits_no_comma:   ["{n}"]
  digits_with_comma: ["{n_comma}"]
  rs_prefix:         ["Rs.{n}", "Rs {n_comma}", "PKR {n}"]
  urdu_words:        ["{urdu_words}"]       # number words in the persona's script, see §6
date_renderings:                   # names used by persona date_styles
  relative:  ["{relative}"]                 # kal, parson; see §6
  day_month: ["{d} {mon}"]                  # 9 Nov
  numeric:   ["{d}/{m}", "{d}-{m}-{yyyy}"]
```

## 6. Number words

Lets normalizers read amounts and relative dates written in words, and lets the noise engine write them. Roman and Urdu-script spellings sit side by side. Normalizers accept every spelling; rendering uses the first one in the persona's column (`urdu` for Urdu-script personas, `roman` for Roman Urdu and mixed, `english` for English).

```yaml
kind: NumberWords
spec_version: 1
id: urdu_numbers
version: 0.1.0
status: draft
reviewed_by: []
digits: "۰۱۲۳۴۵۶۷۸۹"              # Urdu digits for 0–9, in order
numbers:                           # 0–99 are irregular in Urdu, so each one is listed
  - { value: 3, roman: [teen], urdu: [تین] }
  - { value: 5, roman: [paanch, panch], urdu: [پانچ] }
counts:                            # fractional counts used before a multiplier
  - { value: 1.5, roman: [dairh, derh], urdu: [ڈیڑھ] }
  - { value: 2.5, roman: [dhai, adhai], urdu: [ڈھائی] }
modifiers:                         # change the count that follows
  - { add: 0.25, roman: [sawa], urdu: [سوا] }
  - { add: 0.5, roman: [saarhay, sarhe], urdu: [ساڑھے] }
  - { add: -0.25, roman: [paune], urdu: [پونے] }
multipliers:
  - { value: 100, roman: [sau], urdu: [سو] }
  - { value: 1000, roman: [hazar, hazaar, k], urdu: [ہزار] }
  - { value: 100000, roman: [lakh, lac], urdu: [لاکھ] }
  - { value: 10000000, roman: [crore, karor], urdu: [کروڑ] }
relative_days:                     # direction "either" takes the argument's date_direction
  - { days: 0, direction: either, roman: [aaj], urdu: [آج], english: [today] }
  - { days: 1, direction: either, roman: [kal], urdu: [کل] }
  - { days: 1, direction: past, english: [yesterday] }
  - { days: 1, direction: future, english: [tomorrow] }
  - { days: 2, direction: either, roman: [parson], urdu: [پرسوں] }
```

Reading an amount:

- An amount is one or more groups added together, largest multiplier first. Each group is `[modifier] [count] [multiplier]`: `do lakh pachaas hazar` = 250,000; `teen sau pachaas` = 350.
- A count is a number word, a `counts` word, or digits (ASCII or Urdu, decimals allowed: `2.5 lakh`). A modifier with no count means a count of 1: `sawa hazar` = 1,250.
- A modifier adds to the count: `sawa do hazar` = 2,250; `saarhay teen hazar` = 3,500; `paune do hazar` = 1,750.
- A multiplier may be attached to digits: `5k`, `5hazar`.
- The result must be a whole number of rupees, otherwise normalization fails.

## 7. Scenario

```yaml
kind: Scenario
spec_version: 1
id: failed_transfer_01
pack: banking-core
version: 1.0.0
split: public                     # public | holdout
status: draft
reviewed_by: []
tags: [transfers, complaint, money_amount]
title: Money deducted, transfer not received
clock: "2026-11-10T11:00:00+05:00"   # scenario "now", for relative dates

customer:
  goal: Get the failed transfer investigated and receive a complaint reference number
  known_facts:                    # customer knows and may share when relevant
    amount_pkr: { value: 5000, type: money_pkr }
    when:       { value: "2026-11-09", type: date }
    recipient_name: Bilal         # plain fact, inserted as written
  hidden_facts:                   # shared only when the agent asks for them
    card_last4: "4417"
    account_hint: main account
  give_up_after_unhelpful_turns: 4
  opening_intent: report that money left the account but the recipient did not receive it
  seed_lines:                     # opening lines by native speakers; facts as placeholders
    - "paise kat gye h lekn transfer nai hua"
    - "Yaar transfer kiya tha {amount_pkr} ka, abhi tak receive nahi hua"

fixtures:                         # mock backend initial state
  customer_id: CUS-1042
  verification: { registered_phone: "+923000000042", card_last4: "4417" }
  accounts:
    - { id: ACC-1042, balance_pkr: 23500 }
  cards:
    - { last4: "4417", status: active, account_id: ACC-1042 }
  transactions:
    - { id: TXN-88, account_id: ACC-1042, amount_pkr: 5000, date: "2026-11-09", status: debited_not_credited, recipient: Bilal }
    - { id: TXN-87, account_id: ACC-1042, amount_pkr: 500, date: "2026-11-09", status: completed, recipient: Mobile Topup }

expectations:
  outcome:                        # assertions on final mock state
    - assert: complaint.exists
      where: { account_id: ACC-1042, type: failed_transfer, amount_pkr: 5000, transaction_id: TXN-88 }
    - assert: complaint.reference_shared_with_customer
  action:
    required:
      - capability: { any_of: [transaction.find, transaction.list] }   # either lookup path is fine
      - capability: complaint.create
        args: { type: failed_transfer, amount_pkr: 5000 }
    forbidden:
      - capability: card.block
      - capability: transfer.create
    order:
      - before: [{ any_of: [transaction.find, transaction.list] }, complaint.create]
    allow_extra_read_only_calls: true
    allowed: []                   # write capabilities allowed as extra calls; auth is always allowed
  compliance:
    rules: [no_otp_request, no_pin_request, no_full_card_number_request, no_invented_policy]
  escalation:
    expected: false
  max_turns: 12
```

**Facts.** A fact is either plain, inserted as written, or typed: `{ value, type }` with a type from §1 (`money_pkr`, `date`, `phone_pk`, `cnic`). Date values are ISO; the `relative` style renders them against the scenario `clock`. The planner never writes a fact itself. It writes a placeholder (`{amount_pkr}`) and the noise engine fills it in one of the persona's styles. Planner output that contains a fact value, literally or in any of its renderings, fails the fidelity check (spec 08 §2).

**Capability groups.** Wherever a `required` item or an `order` entry names a capability, it can name a group instead: `{ any_of: [a, b] }`. A call to any capability in the group satisfies it. Arg matchers on a group may only use args that every capability in the group has.

**Extra calls.** Calls that don't match a required item are judged by capability `kind` (§1). `allowed` lists the write capabilities a scenario tolerates as extras.

### Assertions available in v1

| Assertion | Meaning |
|---|---|
| `<entity>.exists` with `where` | An entity matching fields exists in final state |
| `<entity>.not_exists` | It does not |
| `<entity>.field_equals` | A specific field value |
| `complaint.reference_shared_with_customer` | Reference ID created by mock appears in an agent message |
| `customer.goal_satisfied` | Simulator reported goal satisfied (weak signal, never used alone) |

## 8. Pack

```yaml
kind: Pack
spec_version: 1
name: banking-core
version: 1.0.0
catalog: banking@1.0.0
mock_backend: banking@1
number_words: urdu_numbers@0.1.0
scenarios: [scenarios/*.yaml]
personas: [urdu_script, roman_clean, roman_messy, code_switch, english, voice_note]
behaviors: [default, impatient, vague]
```

Released versions are frozen and hashed. Changing a scenario means a new pack version.

## 9. Writing good scenarios: rules

1. One clear customer goal per scenario.
2. Every fact the grader checks must appear in `known_facts`, `hidden_facts` or `fixtures`. The simulator never invents them and refers to them only through placeholders.
3. Required actions list only what the business truly requires. If several capabilities are valid paths, use a capability group (`any_of`). If several tools implement one capability, use `tools: [a, b]` in the manifest. Loosen `order` rather than forcing one path.
4. Run the scenario against a correct reference agent before release. If the correct agent fails, the scenario is wrong.
5. Include at least one money amount scenario per persona; amount handling is where Roman Urdu breaks most.
6. Seed lines come from native speakers, reviewed by at least one other native speaker.
7. Holdout scenarios are never pasted into issues, docs, prompts or public repos.
