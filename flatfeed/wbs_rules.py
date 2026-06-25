from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


NO_WBS_VALUE = "NO_WBS"
ANY_WBS_VALUE = "ANY_WBS"
GENERIC_WBS_REQUIREMENT = "WBS"
SUPPORTED_WBS_PERCENTAGES = (100, 140, 160, 180, 220)
PERCENT_VALUE_PATTERN = r"\d{2,3}(?:[,.]\d{1,2})?"

WBS_KEYWORD_RE = re.compile(
    r"\b(?:wbs|wohnberechtigungsschein|wohnberechtigungschein)\b"
    r"|§\s*5\s*-?\s*schein"
    r"|\b(?:paragraph|paragraf)\s*5\b",
    flags=re.IGNORECASE,
)
GENERIC_WBS_REQUIRED_PATTERNS = (
    re.compile(r"\bwbs\s*[:\-]?\s*(?:ja|yes|true)\b", flags=re.IGNORECASE),
    re.compile(
        r"\b(?:nur\s+)?mit\s+(?:einem\s+)?"
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein|§\s*5\s*-?\s*schein)\b"
        r"(?![^\n.!?]{0,40}\b(?:nicht|unmöglich|unmoeglich)\b)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein|§\s*5\s*-?\s*schein)"
        r"[^\n.!?]{0,100}?"
        r"(?:erforderlich|notwendig|required|needed|benötigt|benoetigt)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:erforderlich|notwendig|required|needed|benötigt|benoetigt)"
        r"[^\n.!?]{0,100}?"
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein|§\s*5\s*-?\s*schein)",
        flags=re.IGNORECASE,
    ),
)
NO_WBS_PATTERNS = (
    re.compile(r"\bwbs\s*[:\-]?\s*(?:nein|no|false)\b", flags=re.IGNORECASE),
    re.compile(
        r"\b(?:ohne|kein(?:e|en|er|es|em)?|no)\s+"
        r"(?:\S+\s+){0,4}?"
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein|§\s*5\s*-?\s*schein)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein|§\s*5\s*-?\s*schein)"
        r"(?:\s+\S+){0,4}?\s+(?:nicht|not)\s+"
        r"(?:erforderlich|notwendig|required|needed|benötigt|benoetigt)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein|§\s*5\s*-?\s*schein)"
        r"(?:\s+\S+){0,4}?\s+"
        r"(?:entfällt|entfaellt|frei|irrelevant|optional)",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\bwbs\s*-?\s*frei\b", flags=re.IGNORECASE),
)
WBS_RANGE_PATTERNS = (
    re.compile(
        rf"\b(?:wbs|wohnberechtigungsschein|wohnberechtigungschein)\b"
        rf"\s*(?:[-:]|\(|\[)?\s*({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\s*"
        rf"(?:-|–|—|bis|to)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\b\s*[\])>]*",
        flags=re.IGNORECASE,
    ),
    re.compile(
        rf"\b({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\s*"
        rf"(?:-|–|—|bis|to)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\s*"
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein)\b",
        flags=re.IGNORECASE,
    ),
)
WBS_EXCLUSIVE_LOWER_RANGE_PATTERNS = (
    re.compile(
        rf"\bwbs\b\s*(?:größer\s*als|groesser\s*als|größer|groesser|über|ueber|>)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\s*"
        rf"(?:-|–|—|bis|to)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\b",
        flags=re.IGNORECASE,
    ),
)
WBS_LOWER_BOUND_PATTERNS = (
    re.compile(
        rf"\bwbs\s*(?:ab|from|mindestens|min\.?|minimum)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:ab|from|mindestens|min\.?|minimum)\s*wbs\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:ab|from|mindestens|min\.?|minimum)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\s*wbs\b",
        flags=re.IGNORECASE,
    ),
)
WBS_LIMIT_PATTERNS = (
    re.compile(
        r"\b(?:bis(?:\s+einschließlich|\s+einschl\.?)?|max\.?|maximal|höchstens|hoechstens|up to)\s+"
        rf"(?:wbs\s*)?({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bwbs\s*(?:bis(?:\s+einschließlich|\s+einschl\.?)?|max\.?|maximal|höchstens|hoechstens|up to)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:bis(?:\s+einschließlich|\s+einschl\.?)?|max\.?|maximal|höchstens|hoechstens|up to)\s*"
        rf"({PERCENT_VALUE_PATTERN})(?:\s*%|\s*prozent)?\s*wbs\b",
        flags=re.IGNORECASE,
    ),
)
WBS_LIST_AFTER_KEYWORD_RE = re.compile(
    r"\bwbs\s*[-:]?\s*"
    r"((?:\d{2,3}\s*(?:%|prozent)?\s*(?:,|/|oder|und|or|and|\+)\s*)+"
    r"\d{2,3}\s*(?:%|prozent)?)",
    flags=re.IGNORECASE,
)
WBS_LIST_BEFORE_KEYWORD_RE = re.compile(
    r"\b((?:\d{2,3}\s*(?:%|prozent)?\s*(?:,|/|oder|und|or|and|\+)\s*)+"
    r"\d{2,3}\s*(?:%|prozent)?)\s*"
    r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein)\b",
    flags=re.IGNORECASE,
)
WBS_NUMERIC_PATTERNS = (
    re.compile(r"\bwbs\s*[-:]?\s*(\d{2,3})(?:\s*%|\s*prozent)?\b", flags=re.IGNORECASE),
    re.compile(
        r"\b(\d{2,3})(?:\s*%|\s*prozent)?\s*"
        r"(?:wbs|wohnberechtigungsschein|wohnberechtigungschein)\b",
        flags=re.IGNORECASE,
    ),
)
WBS_REPEATED_NUMERIC_RE = re.compile(
    r"\bwbs\s*[-:]?\s*(\d{2,3})(?:\s*%|\s*prozent)?\b",
    flags=re.IGNORECASE,
)
INCOME_LIMIT_PATTERNS = (
    re.compile(
        r"\b(?:einkommensgrenze|einkommensgrenzen|einkommensgrenzwert|förderweg|foerderweg)"
        rf"[^\n]{{0,50}}?({PERCENT_VALUE_PATTERN})\s*(?:%|prozent)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        rf"\b({PERCENT_VALUE_PATTERN})\s*(?:%|prozent)[^\n]{{0,50}}?"
        r"(?:einkommensgrenze|einkommensgrenzen|einkommensgrenzwert|förderweg|foerderweg)\b",
        flags=re.IGNORECASE,
    ),
)
INCOME_RANGE_PATTERNS = (
    re.compile(
        r"\b(?:einkommensgrenze|einkommensgrenzen|einkommensgrenzwert|förderweg|foerderweg)"
        rf"[^\n]{{0,80}}?({PERCENT_VALUE_PATTERN})\s*(?:%|prozent)?\s*"
        rf"(?:-|–|—|bis|to)\s*({PERCENT_VALUE_PATTERN})\s*(?:%|prozent)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        rf"\b({PERCENT_VALUE_PATTERN})\s*(?:%|prozent)?\s*"
        rf"(?:-|–|—|bis|to)\s*({PERCENT_VALUE_PATTERN})\s*(?:%|prozent)"
        r"[^\n]{0,80}?"
        r"(?:einkommensgrenze|einkommensgrenzen|einkommensgrenzwert|förderweg|foerderweg)\b",
        flags=re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class WBSRequirement:
    requires_wbs: bool
    required_wbs: Optional[str]
    allowed_percentages: Tuple[int, ...]
    rule_type: str
    evidence: Optional[str] = None


def _clean_evidence(value: str) -> str:
    return " ".join(value.split())


def _parse_percent(value: str) -> Optional[float]:
    percent = float(value.replace(",", "."))
    if percent < 50 or percent > 260:
        return None
    return percent


def _format_wbs_percent(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value).replace(".", ",")


def _valid_percent(value: str) -> Optional[int]:
    percent = _parse_percent(value)
    if percent is None:
        return None
    return int(percent)


def _supported_up_to(upper_bound: float) -> Tuple[int, ...]:
    values = tuple(percent for percent in SUPPORTED_WBS_PERCENTAGES if percent <= upper_bound)
    if values:
        return values
    return (int(upper_bound),)


def _supported_from(lower_bound: float) -> Tuple[int, ...]:
    values = tuple(percent for percent in SUPPORTED_WBS_PERCENTAGES if percent >= lower_bound)
    if values:
        return values
    return (int(lower_bound),)


def _supported_between(lower_bound: float, upper_bound: float) -> Tuple[int, ...]:
    lower, upper = sorted((lower_bound, upper_bound))
    values = tuple(
        percent for percent in SUPPORTED_WBS_PERCENTAGES
        if lower <= percent <= upper
    )
    if values:
        return values
    return (int(lower), int(upper))


def _supported_between_exclusive_lower(lower_bound: float, upper_bound: float) -> Tuple[int, ...]:
    lower, upper = sorted((lower_bound, upper_bound))
    values = tuple(
        percent for percent in SUPPORTED_WBS_PERCENTAGES
        if lower < percent <= upper
    )
    if values:
        return values
    return (int(upper),)


def _extract_supported_numbers(value: str) -> Tuple[int, ...]:
    numbers = []
    for raw_number in re.findall(r"\b(\d{2,3})\b", value):
        percent = _valid_percent(raw_number)
        if percent is not None and percent not in numbers:
            numbers.append(percent)
    return tuple(numbers)


def _has_explicit_no_wbs(text: str) -> Optional[str]:
    for pattern in NO_WBS_PATTERNS:
        match = pattern.search(text)
        if match:
            return _clean_evidence(match.group(0))
    return None


def _find_generic_required_wbs(text: str) -> Optional[str]:
    for pattern in GENERIC_WBS_REQUIRED_PATTERNS:
        match = pattern.search(text)
        if match:
            return _clean_evidence(match.group(0))
    return None


def _requirement_from_allowed(
    *,
    allowed: Tuple[int, ...],
    rule_type: str,
    evidence: str,
    upper_bound: Optional[float] = None,
) -> WBSRequirement:
    required_percent = max(allowed) if allowed else int(upper_bound or 0)
    return WBSRequirement(
        requires_wbs=True,
        required_wbs=f"WBS {_format_wbs_percent(float(required_percent))}",
        allowed_percentages=allowed,
        rule_type=rule_type,
        evidence=_clean_evidence(evidence),
    )


def _specific_wbs_requirements(text: str) -> Tuple[WBSRequirement, ...]:
    requirements = []

    for pattern in WBS_EXCLUSIVE_LOWER_RANGE_PATTERNS:
        for match in pattern.finditer(text):
            lower_bound = _parse_percent(match.group(1))
            upper_bound = _parse_percent(match.group(2))
            if lower_bound is None or upper_bound is None:
                continue
            requirements.append(
                _requirement_from_allowed(
                    allowed=_supported_between_exclusive_lower(lower_bound, upper_bound),
                    rule_type="exclusive_lower_range",
                    evidence=match.group(0),
                    upper_bound=max(lower_bound, upper_bound),
                )
            )

    for pattern in WBS_RANGE_PATTERNS:
        for match in pattern.finditer(text):
            lower_bound = _parse_percent(match.group(1))
            upper_bound = _parse_percent(match.group(2))
            if lower_bound is None or upper_bound is None:
                continue
            requirements.append(
                _requirement_from_allowed(
                    allowed=_supported_between(lower_bound, upper_bound),
                    rule_type="range",
                    evidence=match.group(0),
                    upper_bound=max(lower_bound, upper_bound),
                )
            )

    for pattern in (WBS_LIST_AFTER_KEYWORD_RE, WBS_LIST_BEFORE_KEYWORD_RE):
        for match in pattern.finditer(text):
            numbers = _extract_supported_numbers(match.group(1))
            if len(numbers) >= 2:
                requirements.append(
                    _requirement_from_allowed(
                        allowed=tuple(sorted(numbers)),
                        rule_type="list",
                        evidence=match.group(0),
                    )
                )

    if not requirements:
        repeated_numbers = tuple(
            dict.fromkeys(
                number
                for number in (
                    _valid_percent(match.group(1))
                    for match in WBS_REPEATED_NUMERIC_RE.finditer(text)
                )
                if number is not None
            )
        )
        if len(repeated_numbers) >= 2:
            requirements.append(
                _requirement_from_allowed(
                    allowed=tuple(sorted(repeated_numbers)),
                    rule_type="repeated_numeric",
                    evidence=", ".join(f"WBS {number}" for number in repeated_numbers),
                )
            )

    for pattern in WBS_LOWER_BOUND_PATTERNS:
        for match in pattern.finditer(text):
            lower_bound = _parse_percent(match.group(1))
            if lower_bound is None:
                continue
            requirements.append(
                _requirement_from_allowed(
                    allowed=_supported_from(lower_bound),
                    rule_type="lower_bound",
                    evidence=match.group(0),
                )
            )

    for pattern in WBS_LIMIT_PATTERNS:
        for match in pattern.finditer(text):
            if not WBS_KEYWORD_RE.search(match.group(0)):
                continue
            upper_bound = _parse_percent(match.group(1))
            if upper_bound is None:
                continue
            requirements.append(
                _requirement_from_allowed(
                    allowed=_supported_up_to(upper_bound),
                    rule_type="upper_bound",
                    evidence=match.group(0),
                    upper_bound=upper_bound,
                )
            )

    income_range_found = False
    for pattern in INCOME_RANGE_PATTERNS:
        for match in pattern.finditer(text):
            lower_bound = _parse_percent(match.group(1))
            upper_bound = _parse_percent(match.group(2))
            if lower_bound is None or upper_bound is None:
                continue
            income_range_found = True
            requirements.append(
                _requirement_from_allowed(
                    allowed=_supported_between(lower_bound, upper_bound),
                    rule_type="income_range",
                    evidence=match.group(0),
                    upper_bound=max(lower_bound, upper_bound),
                )
            )

    if not income_range_found:
        for pattern in INCOME_LIMIT_PATTERNS:
            for match in pattern.finditer(text):
                upper_bound = _parse_percent(match.group(1))
                if upper_bound is None:
                    continue
                requirements.append(
                    _requirement_from_allowed(
                        allowed=_supported_up_to(upper_bound),
                        rule_type="income_limit",
                        evidence=match.group(0),
                        upper_bound=upper_bound,
                    )
                )

    if not requirements:
        for pattern in WBS_NUMERIC_PATTERNS:
            for match in pattern.finditer(text):
                upper_bound = _parse_percent(match.group(1))
                if upper_bound is None:
                    continue
                requirements.append(
                    _requirement_from_allowed(
                        allowed=_supported_up_to(upper_bound),
                        rule_type="numeric",
                        evidence=match.group(0),
                        upper_bound=upper_bound,
                    )
                )

    return tuple(requirements)


def _merge_specific_requirements(
    requirements: Tuple[WBSRequirement, ...],
) -> Optional[WBSRequirement]:
    if not requirements:
        return None

    allowed_sets = [
        set(requirement.allowed_percentages)
        for requirement in requirements
        if requirement.allowed_percentages
    ]
    if allowed_sets:
        intersection = set.intersection(*allowed_sets)
        if intersection:
            allowed = tuple(
                percent for percent in SUPPORTED_WBS_PERCENTAGES
                if percent in intersection
            )
            strictest = min(requirements, key=lambda item: len(item.allowed_percentages) or 99)
            return _requirement_from_allowed(
                allowed=allowed,
                rule_type=(
                    "combined_specific"
                    if len(requirements) > 1
                    else strictest.rule_type
                ),
                evidence=strictest.evidence or "",
            )

    return min(requirements, key=lambda item: len(item.allowed_percentages) or 99)


def extract_wbs_requirement(text: str) -> WBSRequirement:
    text = text or ""
    specific_requirement = _merge_specific_requirements(_specific_wbs_requirements(text))
    if specific_requirement is not None:
        return specific_requirement

    no_wbs_evidence = _has_explicit_no_wbs(text)
    if no_wbs_evidence is not None:
        return WBSRequirement(
            requires_wbs=False,
            required_wbs=None,
            allowed_percentages=(),
            rule_type="explicit_no_wbs",
            evidence=no_wbs_evidence,
        )

    generic_evidence = _find_generic_required_wbs(text)
    if generic_evidence is not None:
        return WBSRequirement(
            requires_wbs=True,
            required_wbs=GENERIC_WBS_REQUIREMENT,
            allowed_percentages=(),
            rule_type="generic",
            evidence=generic_evidence,
        )

    return WBSRequirement(
        requires_wbs=False,
        required_wbs=None,
        allowed_percentages=(),
        rule_type="not_mentioned",
        evidence=None,
    )


def display_wbs_value(value: Optional[str]) -> str:
    if value == ANY_WBS_VALUE:
        return "Any WBS"
    if value == NO_WBS_VALUE:
        return "No WBS required"
    if value is None:
        return "No WBS required"
    if value == GENERIC_WBS_REQUIREMENT:
        return "WBS required, type unknown"

    numbers = _extract_supported_numbers(value)
    if numbers:
        return ", ".join(str(number) for number in sorted(numbers))
    return value


def display_wbs_requirement(requirement: WBSRequirement) -> str:
    if not requirement.requires_wbs:
        return "No WBS required"
    if requirement.allowed_percentages:
        return ", ".join(str(percent) for percent in requirement.allowed_percentages)
    return "WBS required, type unknown"
