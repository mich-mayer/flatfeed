from __future__ import annotations

import json
from collections.abc import Mapping

from eval.ai_qa_scorer import ERROR_FIELDS


EVAL_PROMPT_VERSION = "dev-v2"
LUNA_PROMPT_VERSION = "luna-v1"
LUNA_V2_PROMPT_VERSION = "luna-v2"
LUNA_V3_PROMPT_VERSION = "luna-v3"
LUNA_V4_PROMPT_VERSION = "luna-v4"
LUNA_V5_PROMPT_VERSION = "luna-v5"
TERRA_V1_PROMPT_VERSION = "terra-v1"
TERRA_V2_PROMPT_VERSION = "terra-v2"
OUTPUT_SCHEMA_NAME = "flatfeed_parser_error_check"

SYSTEM_INSTRUCTIONS = """\
You are reviewing a deterministic parser snapshot for one synthetic German
Berlin apartment listing. Compare only the raw listing text with the supplied
parser snapshot.

Report a material parser error when one of these fields contradicts information
that is explicit in the listing text:
- wbs: the WBS requirement represented by display_wbs;
- rent_kalt: Kaltmiete, Grundmiete, or Nettokaltmiete;
- rooms: the apartment's room count, not household size;
- address_postal_code: street, house number, or Berlin postal code;
- district: the Berlin Bezirk, including normalization from an Ortsteil;
- floor: the apartment floor, not the building's total number of floors;
- rent_warm: Warmmiete, Bruttowarmmiete, or Gesamtmiete.

Check all seven fields before deciding. Close values are still material
mismatches. For WBS, compare presence, specificity, and the exact allowed-tier
set. Compare the explicit apartment room count exactly.

Formatting differences alone are not errors. German decimal commas, EUR/€,
floor abbreviations, and equivalent WBS range wording are acceptable when the
meaning is the same. Under the current FlatFeed convention, no WBS mention
means no WBS is required. Do not infer hidden facts and do not flag genuinely
ambiguous wording.

Set has_error to false and error_field to null when the snapshot is materially
consistent with the listing. Set has_error to true and name exactly one field
when there is a material contradiction. Return only the structured result.
"""

LUNA_SYSTEM_INSTRUCTIONS = """\
You are reviewing a deterministic parser snapshot for one synthetic German
Berlin apartment listing. Compare only the raw listing text with the supplied
parser snapshot.

Report a material parser error when one of these fields contradicts information
that is explicit in the listing text:
- wbs: the WBS requirement represented by display_wbs;
- rent_kalt: Kaltmiete, Grundmiete, or Nettokaltmiete;
- rooms: the apartment's explicit room count, not household size;
- address_postal_code: street, house number, or Berlin postal code;
- district: the Berlin Bezirk;
- floor: the apartment floor, not the building's total number of floors;
- rent_warm: Warmmiete, Bruttowarmmiete, or Gesamtmiete.

Check all seven fields before deciding. Close numeric values are still material
mismatches. Compare explicit apartment room counts exactly.

Use these exact FlatFeed WBS normalization rules. The supported tiers are
100, 140, 160, 180, and 220:
- "bis WBS N" means every supported tier less than or equal to N;
- "WBS ab N" means every supported tier greater than or equal to N;
- a numeric range A-B means every supported tier inside the inclusive bounds;
- therefore "WBS ab 160" means 160, 180, 220;
- "bis WBS 180" means 100, 140, 160, 180;
- "WBS 141-220" means 160, 180, 220 and excludes 140;
- a generic WBS requirement with no number means type unknown;
- no WBS mention means no WBS is required.
Equivalent range wording and an equivalent allowed-tier set are correct, not
errors.

For district, first compare an explicit "Bezirk" or "Verwaltungsbezirk" in the
listing with parser_snapshot.district. Only normalize an Ortsteil or locality
to its Berlin Bezirk when no explicit Bezirk is present. An explicit Bezirk
contradiction is material.

Formatting differences alone are not errors. German decimal commas, EUR/€,
floor abbreviations, and semantically equivalent wording are acceptable. Do
not infer hidden facts and do not flag genuinely ambiguous wording. Do not
choose wbs as a distractor when its normalized value is correct; identify the
one actual material contradiction, if any.

Set has_error to false and error_field to null when the snapshot is materially
consistent with the listing. Set has_error to true and name exactly one field
when there is a material contradiction. Return only the structured result.
"""

LUNA_V2_SYSTEM_INSTRUCTIONS = """\
You are reviewing a deterministic parser snapshot for one synthetic German
Berlin apartment listing. Compare only the raw listing text with the supplied
parser snapshot.

Report a material parser error when one of these fields contradicts information
that is explicit in the listing text:
- wbs: the WBS requirement represented by display_wbs;
- rent_kalt: Kaltmiete, Grundmiete, or Nettokaltmiete;
- rooms: the apartment's explicit room count, not household size;
- address_postal_code: street, house number, or Berlin postal code;
- district: the Berlin Bezirk;
- floor: the apartment floor, not the building's total number of floors;
- rent_warm: Warmmiete, Bruttowarmmiete, or Gesamtmiete.

Check all seven fields before deciding. Close numeric values are still material
mismatches. Compare explicit apartment room counts exactly. Floor labels such
as Hochparterre, Erdgeschoss, and Souterrain are distinct values and must not be
silently treated as numeric floors.

Use these exact FlatFeed WBS normalization rules. The supported tiers are
100, 140, 160, 180, and 220:
- a single "WBS N" means exactly tier N;
- "bis WBS N" means every supported tier less than or equal to N;
- "WBS ab N" means every supported tier greater than or equal to N;
- a numeric range A-B means every supported tier inside the inclusive bounds;
- therefore "WBS 100" means only 100;
- "WBS 100-140" means 100, 140;
- "WBS ab 160" means 160, 180, 220;
- "bis WBS 180" means 100, 140, 160, 180;
- "WBS 141-220" means 160, 180, 220 and excludes 140;
- a generic WBS requirement with no number means type unknown, which is not
  equivalent to any specific numeric tier;
- no WBS mention means no WBS is required.
Equivalent range wording and an exactly equivalent allowed-tier set are
correct, not errors.

For district, first compare an explicit "Bezirk" or "Verwaltungsbezirk" in the
listing with parser_snapshot.district. Only normalize an Ortsteil or locality
to its Berlin Bezirk when no explicit Bezirk is present. An explicit Bezirk
contradiction is material.

Formatting differences alone are not errors. German decimal commas, EUR/€,
floor abbreviations, and semantically equivalent wording are acceptable. Do
not infer hidden facts and do not flag genuinely ambiguous wording. After
confirming that WBS normalization is correct, continue checking all other
fields and identify the one actual material contradiction, if any.

Set has_error to false and error_field to null when the snapshot is materially
consistent with the listing. Set has_error to true and name exactly one field
when there is a material contradiction. Return only the structured result.
"""

LUNA_V3_SYSTEM_INSTRUCTIONS = LUNA_V2_SYSTEM_INSTRUCTIONS.replace(
    "Formatting differences alone are not errors.",
    """For rent localization, bind each explicit label to exactly one field:
- Kaltmiete, Grundmiete, and Nettokaltmiete map only to rent_kalt;
- Warmmiete, Bruttowarmmiete, and Gesamtmiete map only to rent_warm.
Compare each labeled amount directly and independently with its matching
snapshot field. Do not use a plausible relationship between the two rents to
override an explicit mismatch. An explicit Kaltmiete mismatch is rent_kalt,
even when the Warmmiete remains plausible or correct; the reverse rule applies
to an explicit Warmmiete mismatch.

Formatting differences alone are not errors.""",
    1,
)

LUNA_V4_SYSTEM_INSTRUCTIONS = LUNA_V3_SYSTEM_INSTRUCTIONS.replace(
    "For district, first compare",
    """Before moving to the other fields, perform a literal WBS boundary check:
- preserve every stated lower and upper numeric boundary; never round or snap a
  boundary to the nearest supported tier;
- for an inclusive interval [L, U], include a supported tier T exactly when
  L <= T <= U;
- "above" or "greater than L" means T > L, while "from", "at least", or
  "minimum L" means T >= L;
- compare the resulting exact set with parser_snapshot.display_wbs; one extra
  or missing tier is a material wbs error;
- therefore 141-220 or greater than 140 means 160, 180, 220 and excludes 140,
  while 140-220 or from 140 includes 140, 160, 180, 220.
This WBS check is mandatory even when every rent, room, address, district, and
floor value looks plausible.

For district, first compare""",
    1,
)

LUNA_V5_SYSTEM_INSTRUCTIONS = LUNA_V3_SYSTEM_INSTRUCTIONS.replace(
    "Equivalent range wording and an exactly equivalent allowed-tier set are\ncorrect, not errors.",
    """Equivalent range wording and an exactly equivalent allowed-tier set are
correct, not errors. display_wbs is a normalized set of supported tiers, not a
literal transcription of every number in the listing. A numeric boundary that
is not a supported tier must not appear in display_wbs.

Use these boundary controls:
- listing 141-220 with display_wbs 160, 180, 220 is correct;
- listing 141-220 with display_wbs 140, 160, 180, 220 is a wbs error;
- listing 140-220 with display_wbs 140, 160, 180, 220 is correct;
- listing greater than 140 through 220 with display_wbs 160, 180, 220 is correct.
Unusual but semantically explicit WBS wording is not itself a contradiction.""",
    1,
).replace(
    "Set has_error to false and error_field to null when the snapshot is materially",
    """Compare every field independently and form a candidate mismatch only from a
direct contradiction between the listing and that snapshot field. Do not stop
after a difficult WBS phrase, and do not prefer wbs over a clearer mismatch in
another field. These evaluation cases contain at most one material parser
error.

Set has_error to false and error_field to null when the snapshot is materially""",
    1,
)

TERRA_V1_SYSTEM_INSTRUCTIONS = LUNA_V5_SYSTEM_INSTRUCTIONS.replace(
    "Check all seven fields before deciding.",
    """Use a mandatory seven-field inspection pass before deciding. For each field,
read the explicit source value first, then compare only that value with the
matching parser_snapshot field. Do not treat an otherwise plausible snapshot
as evidence that a field matches.

Check all seven fields before deciding.""",
    1,
).replace(
    "For district, first compare",
    """For address_postal_code, compare the street, house number, and Berlin postal
code independently. A different explicit postal code is a material
address_postal_code error even when the street, district, or complete address
still looks plausible.

For WBS, complete three independent checks before leaving the field: whether a
WBS is required at all, whether the requirement is generic or specific, and
whether the complete normalized supported-tier set matches. Do not let a
plausible numeric tier override a presence, specificity, or set mismatch.

For district, first compare""",
    1,
)

TERRA_V2_SYSTEM_INSTRUCTIONS = TERRA_V1_SYSTEM_INSTRUCTIONS.replace(
    "Set has_error to false and error_field to null when the snapshot is materially",
    """Before the final decision, complete an internal source equality ledger in
this fixed order: wbs, district, rent_kalt, rooms, address_postal_code, floor,
rent_warm. For every row, identify the explicit source value, identify the
matching snapshot value, and mark only equal or contradiction.

For the rooms row, preserve half-room values and compare the explicit apartment
room number exactly, without rounding or treating a nearby value as equal. For
the wbs row, let explicit no-WBS wording such as freifinanziert or nicht
erforderlich determine that no WBS is required; then separately compare
generic-versus-specific status and the complete supported-tier set.

Apply a final contradiction veto: has_error may be false only when every ledger
row is equal. Immediately before returning false, re-read the rooms and wbs
rows once. A match in other fields cannot cancel a direct rooms or wbs
contradiction.

Set has_error to false and error_field to null when the snapshot is materially""",
    1,
)

PROMPT_INSTRUCTIONS: dict[str, str] = {
    EVAL_PROMPT_VERSION: SYSTEM_INSTRUCTIONS,
    LUNA_PROMPT_VERSION: LUNA_SYSTEM_INSTRUCTIONS,
    LUNA_V2_PROMPT_VERSION: LUNA_V2_SYSTEM_INSTRUCTIONS,
    LUNA_V3_PROMPT_VERSION: LUNA_V3_SYSTEM_INSTRUCTIONS,
    LUNA_V4_PROMPT_VERSION: LUNA_V4_SYSTEM_INSTRUCTIONS,
    LUNA_V5_PROMPT_VERSION: LUNA_V5_SYSTEM_INSTRUCTIONS,
    TERRA_V1_PROMPT_VERSION: TERRA_V1_SYSTEM_INSTRUCTIONS,
    TERRA_V2_PROMPT_VERSION: TERRA_V2_SYSTEM_INSTRUCTIONS,
}


def get_system_instructions(prompt_version: str) -> str:
    """Return an immutable, versioned prompt profile."""

    try:
        return PROMPT_INSTRUCTIONS[prompt_version]
    except KeyError:
        raise ValueError(
            f"unknown prompt version: {prompt_version}"
        ) from None

MODEL_OUTPUT_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "has_error": {"type": "boolean"},
        "error_field": {
            "anyOf": [
                {
                    "type": "string",
                    "enum": list(ERROR_FIELDS),
                },
                {"type": "null"},
            ]
        },
    },
    "required": ["has_error", "error_field"],
    "additionalProperties": False,
}

RESPONSES_TEXT_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "name": OUTPUT_SCHEMA_NAME,
    "strict": True,
    "schema": MODEL_OUTPUT_JSON_SCHEMA,
}


def render_case_input(case: Mapping[str, object]) -> str:
    """Render only model-visible fields; never include case ID or truth."""

    payload = {
        "raw_listing_text": case["raw_text"],
        "parser_snapshot": case["parser_snapshot"],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
