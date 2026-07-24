from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, replace
from typing import Callable, Literal, Sequence

from eval.ai_qa_clean_generator import CleanAIQACase, ParserSnapshot
from flatfeed.listing_metadata import BERLIN_DISTRICTS


CONTROLLED_ERROR_SEED = 20260721

CORRUPTION_FIELDS = (
    "wbs",
    "rent_kalt",
    "rooms",
    "address_postal_code",
    "district",
    "floor",
    "rent_warm",
)

MODEL_PARSER_SNAPSHOT_FIELDS = (
    "display_wbs",
    "rooms",
    "floor",
    "address",
    "postal_code",
    "district",
    "rent_kalt",
    "rent_warm",
)

_DISPLAY_WBS_VALUES = (
    "No WBS required",
    "WBS required, type unknown",
    "100",
    "100, 140",
    "100, 140, 160, 180",
    "100, 140, 160, 180, 220",
    "140, 160, 180, 220",
    "160, 180, 220",
)
_WBS_NEIGHBORS = {
    "No WBS required": ("WBS required, type unknown", "100"),
    "WBS required, type unknown": ("No WBS required", "100"),
    "100": ("No WBS required", "100, 140"),
    "100, 140": ("100", "140, 160, 180, 220"),
    "100, 140, 160, 180": (
        "100, 140",
        "100, 140, 160, 180, 220",
    ),
    "100, 140, 160, 180, 220": (
        "100, 140, 160, 180",
        "140, 160, 180, 220",
    ),
    "140, 160, 180, 220": ("100, 140", "160, 180, 220"),
    "160, 180, 220": ("100, 140", "140, 160, 180, 220"),
}
_BERLIN_POSTAL_CODES = (
    "10245",
    "10319",
    "10557",
    "10585",
    "10827",
    "10961",
    "12043",
    "12099",
    "12163",
    "12207",
    "12353",
    "12459",
    "12489",
    "12627",
    "12681",
    "13088",
    "13187",
    "13353",
    "13435",
    "13437",
    "13585",
    "13593",
    "14197",
)
_DISTRICT_NEIGHBORS = {
    "Mitte": (
        "Friedrichshain-Kreuzberg",
        "Pankow",
        "Charlottenburg-Wilmersdorf",
        "Reinickendorf",
        "Tempelhof-Schöneberg",
    ),
    "Friedrichshain-Kreuzberg": (
        "Mitte",
        "Pankow",
        "Lichtenberg",
        "Treptow-Köpenick",
        "Neukölln",
        "Tempelhof-Schöneberg",
    ),
    "Pankow": (
        "Mitte",
        "Friedrichshain-Kreuzberg",
        "Lichtenberg",
        "Reinickendorf",
    ),
    "Charlottenburg-Wilmersdorf": (
        "Mitte",
        "Spandau",
        "Steglitz-Zehlendorf",
        "Tempelhof-Schöneberg",
    ),
    "Spandau": (
        "Charlottenburg-Wilmersdorf",
        "Steglitz-Zehlendorf",
        "Reinickendorf",
    ),
    "Steglitz-Zehlendorf": (
        "Charlottenburg-Wilmersdorf",
        "Spandau",
        "Tempelhof-Schöneberg",
    ),
    "Tempelhof-Schöneberg": (
        "Mitte",
        "Friedrichshain-Kreuzberg",
        "Charlottenburg-Wilmersdorf",
        "Steglitz-Zehlendorf",
        "Neukölln",
        "Treptow-Köpenick",
    ),
    "Neukölln": (
        "Friedrichshain-Kreuzberg",
        "Tempelhof-Schöneberg",
        "Treptow-Köpenick",
    ),
    "Treptow-Köpenick": (
        "Friedrichshain-Kreuzberg",
        "Tempelhof-Schöneberg",
        "Neukölln",
        "Lichtenberg",
        "Marzahn-Hellersdorf",
    ),
    "Marzahn-Hellersdorf": (
        "Treptow-Köpenick",
        "Lichtenberg",
    ),
    "Lichtenberg": (
        "Pankow",
        "Friedrichshain-Kreuzberg",
        "Treptow-Köpenick",
        "Marzahn-Hellersdorf",
    ),
    "Reinickendorf": (
        "Mitte",
        "Pankow",
        "Charlottenburg-Wilmersdorf",
        "Spandau",
    ),
}
_FLOOR_NEIGHBORS = {
    "EG": ("Hochparterre", "1"),
    "Hochparterre": ("EG", "1"),
    "1": ("EG", "2"),
    "2": ("1", "3"),
    "3": ("2", "4"),
    "4": ("3", "5"),
    "5": ("4", "6"),
    "6": ("5", "7"),
    "7": ("6", "DG"),
    "DG": ("6", "7"),
}
_MONEY_RE = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+),(\d{2}) EUR$")
_HOUSE_NUMBER_RE = re.compile(r"(?P<number>\d+)(?P<suffix>[a-zA-Z]?)$")

CaseType = Literal["clean", "corrupted"]
CorruptionResult = tuple[str, object, str]


@dataclass(frozen=True)
class AIQAModelInput:
    """The only payload surface that may be sent to the model."""

    raw_text: str
    parser_snapshot: ParserSnapshot

    def as_dict(self) -> dict[str, object]:
        snapshot = self.parser_snapshot.as_dict()
        return {
            "raw_text": self.raw_text,
            "parser_snapshot": {
                field: snapshot[field]
                for field in MODEL_PARSER_SNAPSHOT_FIELDS
            },
        }


@dataclass(frozen=True)
class AIQAAnswerKey:
    """Hidden scoring data stored separately from ``AIQAModelInput``."""

    case_id: str
    case_type: CaseType
    corrupted_field: str | None
    expected_value: object | None
    corrupted_value: object | None
    corruption_type: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "corrupted_field": self.corrupted_field,
            "expected_value": self.expected_value,
            "corrupted_value": self.corrupted_value,
            "corruption_type": self.corruption_type,
        }


@dataclass(frozen=True)
class OfflineAIQACase:
    """A model input paired with a separate, hidden answer key.

    This container intentionally has no combined serializer. Callers preparing
    a model request must serialize ``model_input`` only.
    """

    model_input: AIQAModelInput
    answer_key: AIQAAnswerKey


def _validate_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")


def _money_to_cents(value: str) -> int:
    match = _MONEY_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"Unsupported parser snapshot money value: {value}")
    euros = int(match.group(1).replace(".", ""))
    return euros * 100 + int(match.group(2))


def _format_money(cents: int) -> str:
    euros, remainder = divmod(cents, 100)
    grouped_euros = f"{euros:,}".replace(",", ".")
    return f"{grouped_euros},{remainder:02d} EUR"


def _different_choice(
    candidates: Sequence[object],
    *,
    expected: object,
    rng: random.Random,
) -> object:
    available = [candidate for candidate in candidates if candidate != expected]
    if not available:
        raise ValueError("corruption requires at least one different candidate")
    return rng.choice(available)


def _wbs_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    expected = snapshot.display_wbs
    candidates = _WBS_NEIGHBORS.get(expected, _DISPLAY_WBS_VALUES)
    corrupted = str(_different_choice(candidates, expected=expected, rng=rng))
    if expected == "No WBS required":
        corruption_type = "wbs_requirement_added"
    elif corrupted == "No WBS required":
        corruption_type = "wbs_requirement_dropped"
    elif "type unknown" in expected or "type unknown" in corrupted:
        corruption_type = "wbs_specificity_confusion"
    else:
        corruption_type = "wbs_range_boundary_shift"
    return "display_wbs", corrupted, corruption_type


def _rent_amount_shift(
    *,
    expected_cents: int,
    lower_bound: int,
    upper_bound: int,
    rng: random.Random,
) -> int:
    deltas = (-17_500, -12_500, -9_900, 9_900, 12_500, 17_500)
    candidates = [
        expected_cents + delta
        for delta in deltas
        if lower_bound <= expected_cents + delta <= upper_bound
    ]
    return int(_different_choice(candidates, expected=expected_cents, rng=rng))


def _rent_kalt_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    if rng.choice((True, False)):
        return "rent_kalt", snapshot.rent_warm, "kaltmiete_label_swap"

    expected_cents = _money_to_cents(snapshot.rent_kalt)
    warm_cents = _money_to_cents(snapshot.rent_warm)
    corrupted_cents = _rent_amount_shift(
        expected_cents=expected_cents,
        lower_bound=30_000,
        upper_bound=max(30_000, warm_cents - 1_000),
        rng=rng,
    )
    return "rent_kalt", _format_money(corrupted_cents), "kaltmiete_amount_shift"


def _rooms_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    expected = snapshot.rooms
    candidates = tuple(
        value
        for value in (expected - 1.0, expected - 0.5, expected + 0.5, expected + 1.0)
        if 1.0 <= value <= 5.0
    )
    corrupted = float(_different_choice(candidates, expected=expected, rng=rng))
    return "rooms", corrupted, "rooms_neighbor_value"


def _address_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    match = _HOUSE_NUMBER_RE.search(snapshot.address)
    if match is None:
        raise ValueError(f"Address has no house number: {snapshot.address}")
    current_number = int(match.group("number"))
    delta = rng.choice((-10, -4, 2, 6, 12))
    corrupted_number = max(1, min(240, current_number + delta))
    if corrupted_number == current_number:
        corrupted_number = current_number + 2
    corrupted = (
        snapshot.address[: match.start("number")]
        + str(corrupted_number)
        + match.group("suffix")
    )
    return "address", corrupted, "address_house_number_shift"


def _postal_code_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    corrupted = str(
        _different_choice(
            _BERLIN_POSTAL_CODES,
            expected=snapshot.postal_code,
            rng=rng,
        )
    )
    return "postal_code", corrupted, "postal_code_substitution"


def _address_postal_code_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    if rng.choice((True, False)):
        return _address_corruption(snapshot, rng)
    return _postal_code_corruption(snapshot, rng)


def _district_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    candidates = _DISTRICT_NEIGHBORS.get(snapshot.district, BERLIN_DISTRICTS)
    corrupted = str(
        _different_choice(
            candidates,
            expected=snapshot.district,
            rng=rng,
        )
    )
    return "district", corrupted, "district_neighbor_substitution"


def _floor_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    candidates = _FLOOR_NEIGHBORS.get(
        snapshot.floor,
        ("EG", "1", "2", "3", "4", "5", "6", "7", "DG"),
    )
    corrupted = str(
        _different_choice(
            candidates,
            expected=snapshot.floor,
            rng=rng,
        )
    )
    return "floor", corrupted, "floor_neighbor_value"


def _rent_warm_corruption(
    snapshot: ParserSnapshot,
    rng: random.Random,
) -> CorruptionResult:
    if rng.choice((True, False)):
        return "rent_warm", snapshot.rent_kalt, "warmmiete_label_swap"

    expected_cents = _money_to_cents(snapshot.rent_warm)
    kalt_cents = _money_to_cents(snapshot.rent_kalt)
    corrupted_cents = _rent_amount_shift(
        expected_cents=expected_cents,
        lower_bound=kalt_cents + 5_000,
        upper_bound=200_000,
        rng=rng,
    )
    return "rent_warm", _format_money(corrupted_cents), "warmmiete_amount_shift"


_CORRUPTION_BUILDERS: dict[
    str,
    Callable[[ParserSnapshot, random.Random], CorruptionResult],
] = {
    "wbs": _wbs_corruption,
    "rent_kalt": _rent_kalt_corruption,
    "rooms": _rooms_corruption,
    "address_postal_code": _address_postal_code_corruption,
    "district": _district_corruption,
    "floor": _floor_corruption,
    "rent_warm": _rent_warm_corruption,
}


def _corrupted_case_id(
    *,
    clean_case_id: str,
    corrupted_field: str,
    corrupted_value: object,
    corruption_type: str,
) -> str:
    payload = (
        f"{clean_case_id}\n{corrupted_field}\n"
        f"{corrupted_value}\n{corruption_type}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{clean_case_id}-x-{digest}"


def build_clean_ai_qa_eval_case(clean_case: CleanAIQACase) -> OfflineAIQACase:
    """Pair an unchanged clean model input with a clean answer key."""

    return OfflineAIQACase(
        model_input=AIQAModelInput(
            raw_text=clean_case.raw_text,
            parser_snapshot=clean_case.parser_snapshot,
        ),
        answer_key=AIQAAnswerKey(
            case_id=clean_case.case_id,
            case_type="clean",
            corrupted_field=None,
            expected_value=None,
            corrupted_value=None,
            corruption_type=None,
        ),
    )


def build_corrupted_ai_qa_eval_case(
    clean_case: CleanAIQACase,
    *,
    corruption_field: str,
    seed: int = CONTROLLED_ERROR_SEED,
) -> OfflineAIQACase:
    """Create one plausible, single-field parser-snapshot corruption."""

    _validate_seed(seed)
    builder = _CORRUPTION_BUILDERS.get(corruption_field)
    if builder is None:
        supported = ", ".join(CORRUPTION_FIELDS)
        raise ValueError(
            f"unsupported corruption_field={corruption_field!r}; "
            f"expected one of: {supported}"
        )

    rng = random.Random(seed)
    snapshot_field, corrupted_value, corruption_type = builder(
        clean_case.parser_snapshot,
        rng,
    )
    clean_snapshot = clean_case.parser_snapshot.as_dict()
    expected_value = clean_snapshot[snapshot_field]
    if corrupted_value == expected_value:
        raise RuntimeError("corruption did not change the selected field")

    corrupted_snapshot = replace(
        clean_case.parser_snapshot,
        **{snapshot_field: corrupted_value},
    )
    changed_fields = {
        field
        for field, clean_value in clean_snapshot.items()
        if corrupted_snapshot.as_dict()[field] != clean_value
    }
    if changed_fields != {snapshot_field}:
        raise RuntimeError(
            "corruption must change exactly one parser snapshot field; "
            f"changed={sorted(changed_fields)}"
        )

    case_id = _corrupted_case_id(
        clean_case_id=clean_case.case_id,
        corrupted_field=snapshot_field,
        corrupted_value=corrupted_value,
        corruption_type=corruption_type,
    )
    return OfflineAIQACase(
        model_input=AIQAModelInput(
            raw_text=clean_case.raw_text,
            parser_snapshot=corrupted_snapshot,
        ),
        answer_key=AIQAAnswerKey(
            case_id=case_id,
            case_type="corrupted",
            corrupted_field=snapshot_field,
            expected_value=expected_value,
            corrupted_value=corrupted_value,
            corruption_type=corruption_type,
        ),
    )


def generate_controlled_ai_qa_cases(
    clean_cases: Sequence[CleanAIQACase],
    *,
    corruption_fields: Sequence[str | None],
    seed: int = CONTROLLED_ERROR_SEED,
) -> list[OfflineAIQACase]:
    """Build clean/corrupted in-memory cases without creating a dataset.

    Each ``None`` entry creates a clean case. Every named entry creates one
    corruption in the corresponding clean case. The answer key remains a
    separate object and is never added to ``AIQAModelInput``.
    """

    _validate_seed(seed)
    if len(clean_cases) != len(corruption_fields):
        raise ValueError("clean_cases and corruption_fields must have equal length")

    rng = random.Random(seed)
    generated: list[OfflineAIQACase] = []
    for clean_case, corruption_field in zip(clean_cases, corruption_fields):
        case_seed = rng.getrandbits(64)
        if corruption_field is None:
            generated.append(build_clean_ai_qa_eval_case(clean_case))
        else:
            generated.append(
                build_corrupted_ai_qa_eval_case(
                    clean_case,
                    corruption_field=corruption_field,
                    seed=case_seed,
                )
            )
    return generated
