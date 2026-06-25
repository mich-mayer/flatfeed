from __future__ import annotations

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flatfeed.config import get_settings
from flatfeed.db.models import AIQAReview, APILog, Listing
from flatfeed.listing_metadata import address_diagnostics, extract_rooms
from flatfeed.matching import (
    KALT_RENT_LABELS,
    WARM_RENT_LABELS,
    display_wbs_options_for_listing_text,
    effective_required_wbs,
    effective_wbs_requirement,
    extract_rent_display,
)
from flatfeed.nlp.cost import calculate_openai_cost_usd
from flatfeed.schemas import ListingConstraints
from flatfeed.wbs_rules import GENERIC_WBS_REQUIREMENT


logger = logging.getLogger(__name__)

AI_QA_FEEDBACK_PENDING = "pending"
AI_QA_FEEDBACK_PARSER_ERROR = "parser_error"
AI_QA_FEEDBACK_PARSER_CORRECT = "parser_correct"
AI_QA_FEEDBACK_UNSURE = "unsure"

AI_QA_TRIGGER_INITIAL_BACKFILL = "initial_backfill"
AI_QA_TRIGGER_NEW_LISTING = "new_listing"
AI_QA_TRIGGER_DEMO_FAULT = "demo_fault_injection"

AI_QA_ENDPOINT_TYPE = "ai_qa"
CURRENT_AI_QA_PROMPT_VERSION = "v8"
AI_QA_DEMO_FAULT_TYPES = ("wbs", "rooms", "rent_kalt", "rent_warm")

AI_QA_SYSTEM_MESSAGE = (
    "You are an AI QA validator for a Berlin rental listing parser. "
    "Your task is to compare raw public-housing listing text with parser_snapshot. "
    "Do not rewrite listing data. Do not decide user matching. "
    "Only assess whether the deterministic parser likely made a mistake.\n\n"
    "Return only a strict JSON object with keys: "
    "parser_result_correct, risk_score, confidence, issues, suggested_values, "
    "wbs_source_interpretation, should_alert_admin. The issues key must be an "
    "array of objects. Each issue object must contain field, parser_value, "
    "ai_value, reason, and severity.\n\n"
    "For every listing, always fill wbs_source_interpretation as an object with "
    "keys: kind, evidence, specific_values_found, explanation. kind must be one "
    "of: no_wbs_mentioned, no_wbs_required, generic_wbs_required, "
    "specific_wbs_values, ambiguous. specific_values_found must be an array of "
    "supported WBS numbers found in the raw listing text, for example [100, 140]. "
    "evidence must be a short exact fragment from the raw listing text.\n\n"
    "risk_score means: how likely it is that the parser result is materially wrong. "
    "confidence means: how confident you are in your own interpretation. "
    "Set should_alert_admin=true only when risk_score >= 75.\n\n"
    "Focus fields in this priority: WBS, rooms, rent_kalt/rent_warm, floor, "
    "address, postal_code, district. Supported WBS values are 100, 140, 160, 180, 220. "
    "If WBS range starts above 140, WBS 140 must not be included.\n\n"
    "Important product semantics:\n"
    "- The user-facing WBS value is parser_snapshot.display_wbs. Validate display_wbs, "
    "not internal required_wbs. Do not create issues for required_wbs when display_wbs "
    "is correct.\n"
    "- If the raw text does not mention WBS at all, display_wbs='No WBS required' or "
    "'no WBS required' is correct for this product. This must have risk_score 0-20.\n"
    "- If the raw text says WBS is required but does not specify any WBS percentage "
    "or income range, display_wbs='WBS required, type unknown' or 'WBS required, type "
    "unspecified' is correct. This is common in Berlin public-housing listings and must not be treated "
    "as a parser error. In this case wbs_source_interpretation.kind must be "
    "generic_wbs_required and specific_values_found must be empty.\n"
    "- If the raw text says 'ohne WBS', 'kein WBS', 'freifinanziert', "
    "'Bewerbung mit WBS nicht möglich', or similar, no WBS is required. This must not "
    "be treated as WBS required.\n"
    "- If the title/text says 'WBS 100-140', valid display_wbs values are 100 and 140. "
    "If it says 'WBS 140-220', valid values are 140, 160, 180, 220. If it says "
    "'WBS 141-220' or an income boundary above 140, WBS 140 is not valid.\n"
    "- The product district field is a Berlin borough, not a neighborhood. "
    "Examples: Alt-Hohenschönhausen and Neu-Hohenschönhausen are neighborhoods inside "
    "Lichtenberg. Do not flag district=Lichtenberg as wrong for those neighborhoods.\n\n"
    "Calibration rules:\n"
    "- Use high risk only for clear contradictions that can affect matching or user trust.\n"
    "- If parser_snapshot and raw text agree in meaning, risk_score should be 0-30.\n"
    "- Missing optional fields such as floor or district are not high risk by themselves.\n"
    "- Do not mark high risk just because you would format a value differently.\n"
    "- For WBS, high risk is appropriate when the parser says no WBS but the text clearly "
    "requires WBS, or when display_wbs includes a WBS value that the text explicitly excludes.\n"
    "- For rent and rooms, high risk is appropriate only when the parsed number clearly "
    "contradicts a nearby labelled value in the title or listing text.\n"
    "- If risk_score is 75 or higher, issues must contain at least one concrete issue "
    "with a field name, parser value, AI value, and source-based reason."
)


@dataclass(frozen=True)
class AIQARunResult:
    checked_count: int
    alert_review_ids: tuple[int, ...]
    skipped_reason: Optional[str] = None
    stop_reason: str = "completed"
    total_unreviewed_before: int = 0
    remaining_unreviewed_count: int = 0
    total_cost_usd: float = 0.0
    limit_reached: bool = False


@dataclass(frozen=True)
class AIQAStatus:
    qa_prompt_version: str
    enabled: bool
    model: str
    daily_max_cost_usd: float
    checks_today: int
    cost_today_usd: float
    active_listings_count: int
    reviewed_active_count: int
    unreviewed_active_count: int
    pending_alerts_count: int
    parser_error_feedback_count: int
    parser_correct_feedback_count: int
    unsure_feedback_count: int
    total_reviews_count: int
    latest_review_at: Optional[datetime]


@dataclass(frozen=True)
class _AIQACallResult:
    listing: Listing
    parser_snapshot: Dict[str, Any]
    ai_result: Dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float


@dataclass(frozen=True)
class AIQADemoResult:
    listing: Listing
    parser_snapshot: Dict[str, Any]
    ai_result: Dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    fault: Dict[str, Any]


def _safe_usage_value(usage: Any, field_name: str) -> int:
    value = getattr(usage, field_name, 0) if usage is not None else 0
    return int(value or 0)


def _hash_payload(value: Any) -> str:
    if isinstance(value, str):
        raw = value
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_json_payload(content: str) -> Dict[str, Any]:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("AI QA response must be a JSON object.")
    return payload


def _listing_constraints(listing: Listing) -> ListingConstraints:
    if not listing.parsed_constraints:
        return ListingConstraints()
    return ListingConstraints.model_validate(listing.parsed_constraints)


def build_parser_snapshot(listing: Listing) -> Dict[str, Any]:
    constraints = _listing_constraints(listing)
    address_diag = address_diagnostics(
        f"{listing.raw_text or ''}\n{listing.title or ''}",
        listing.address,
    )
    return {
        "required_wbs": effective_required_wbs(
            parsed_required_wbs=constraints.required_wbs,
            listing_title=listing.title,
            listing_text=listing.raw_text,
        ),
        "display_wbs": display_wbs_options_for_listing_text(
            parsed_required_wbs=constraints.required_wbs,
            listing_title=listing.title,
            listing_text=listing.raw_text,
        ),
        "rooms": listing.rooms,
        "floor": listing.floor,
        "address": listing.address,
        "postal_code": listing.postal_code,
        "address_source": address_diag.source,
        "address_sanity": {
            "status": address_diag.sanity_status,
            "details": address_diag.sanity_details,
        },
        "district": listing.district,
        "rent_kalt": extract_rent_display(
            listing.raw_text,
            KALT_RENT_LABELS,
        ) or listing.rent_kalt,
        "rent_warm": extract_rent_display(
            listing.raw_text,
            WARM_RENT_LABELS,
        ) or listing.rent_warm,
    }


def _numeric_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d{1,3}(?:\.\d{3})*(?:[,.]\d+)?|\d+(?:[,.]\d+)?", str(value))
    if not match:
        return None
    raw = match.group(0)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif re.search(r"\.\d{3}(?:\D|$)", raw):
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _values_match(left: Any, right: Any, *, tolerance: float = 0.01) -> bool:
    left_number = _numeric_value(left)
    right_number = _numeric_value(right)
    if left_number is not None and right_number is not None:
        return abs(left_number - right_number) <= tolerance
    return str(left or "").strip().lower() == str(right or "").strip().lower()


def _bump_numeric_value(value: Any, *, delta: float) -> float:
    number = _numeric_value(value)
    if number is None:
        return delta
    bumped = number + delta
    if bumped <= 0:
        bumped = number + abs(delta)
    return bumped


def _format_demo_rent(value: Any) -> str:
    bumped = round(_bump_numeric_value(value, delta=111), 2)
    if float(bumped).is_integer():
        return f"{int(bumped)} EUR"
    return f"{bumped:.2f}".replace(".", ",") + " EUR"


def build_demo_fault_parser_snapshot(
    listing: Listing,
    *,
    fault_type: str = "auto",
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Return a parser snapshot with one explicit demo-only mistake injected."""
    snapshot = build_parser_snapshot(listing)
    requested = (fault_type or "auto").strip().lower()
    candidates = AI_QA_DEMO_FAULT_TYPES if requested == "auto" else (requested,)
    applied = None

    for candidate in candidates:
        if candidate not in AI_QA_DEMO_FAULT_TYPES:
            continue
        if candidate == "wbs":
            original = snapshot.get("display_wbs")
            injected = "No WBS required" if not _is_no_wbs_display(original) else "100, 140"
            snapshot["display_wbs"] = injected
            snapshot["required_wbs"] = None if injected == "No WBS required" else "WBS 100-140"
        elif candidate == "rooms":
            original = snapshot.get("rooms")
            if original is None:
                continue
            injected = _bump_numeric_value(original, delta=1)
            if float(injected).is_integer():
                injected = int(injected)
            snapshot["rooms"] = injected
        elif candidate in {"rent_kalt", "rent_warm"}:
            original = snapshot.get(candidate)
            if original is None:
                continue
            injected = _format_demo_rent(original)
            snapshot[candidate] = injected
        else:
            continue

        applied = {
            "field": candidate,
            "original_value": original,
            "injected_value": injected,
        }
        break

    if applied is None:
        original = snapshot.get("display_wbs")
        injected = "100, 140" if _is_no_wbs_display(original) else "No WBS required"
        snapshot["display_wbs"] = injected
        snapshot["required_wbs"] = None if injected == "No WBS required" else "WBS 100-140"
        applied = {
            "field": "wbs",
            "original_value": original,
            "injected_value": injected,
        }

    fault = {
        "demo_fault_injection": True,
        "fault_type": applied["field"],
        "field": applied["field"],
        "original_value": applied["original_value"],
        "injected_value": applied["injected_value"],
        "note": "Synthetic demo only. The listing and saved parser output were not changed.",
    }
    return snapshot, fault


def _user_message(listing: Listing, parser_snapshot: Dict[str, Any]) -> str:
    settings = get_settings()
    clipped_text = listing.raw_text[: settings.ai_qa_max_listing_chars]
    return (
        f"Source: {listing.source_company}\n"
        f"URL: {listing.url}\n"
        f"Title: {listing.title or ''}\n\n"
        "Parser snapshot JSON:\n"
        f"{json.dumps(parser_snapshot, ensure_ascii=False, sort_keys=True)}\n\n"
        "Raw listing text:\n"
        f"{clipped_text}"
    )


def _normalize_ai_result(payload: Dict[str, Any], *, alert_threshold: int) -> Dict[str, Any]:
    risk_score = int(max(0, min(100, payload.get("risk_score") or 0)))
    confidence = float(max(0.0, min(1.0, payload.get("confidence") or 0.0)))
    raw_issues = payload.get("issues")
    if isinstance(raw_issues, list):
        issues = raw_issues
    elif raw_issues:
        issues = [raw_issues]
    else:
        issues = []
    suggested_values = payload.get("suggested_values")
    if not isinstance(suggested_values, dict):
        suggested_values = {}
    wbs_source_interpretation = payload.get("wbs_source_interpretation")
    if not isinstance(wbs_source_interpretation, dict):
        wbs_source_interpretation = {}
    specific_values = wbs_source_interpretation.get("specific_values_found")
    if not isinstance(specific_values, list):
        specific_values = []
    normalized_wbs_interpretation = {
        "kind": str(wbs_source_interpretation.get("kind") or "ambiguous"),
        "evidence": str(wbs_source_interpretation.get("evidence") or ""),
        "specific_values_found": specific_values,
        "explanation": str(wbs_source_interpretation.get("explanation") or ""),
    }
    parser_result_correct = bool(payload.get("parser_result_correct", risk_score < alert_threshold))
    should_alert_admin = bool(payload.get("should_alert_admin", False)) or risk_score >= alert_threshold
    if risk_score >= alert_threshold:
        parser_result_correct = False
    return {
        "parser_result_correct": parser_result_correct,
        "risk_score": risk_score,
        "confidence": confidence,
        "issues": issues,
        "suggested_values": suggested_values,
        "wbs_source_interpretation": normalized_wbs_interpretation,
        "should_alert_admin": should_alert_admin,
    }


def _issue_field(issue: Any) -> str:
    if isinstance(issue, dict):
        return str(issue.get("field") or "").strip().lower()
    return ""


def _display_wbs_numbers(value: Any) -> tuple[int, ...]:
    numbers = []
    for raw_number in re.findall(r"\b(\d{2,3})\b", str(value or "")):
        number = int(raw_number)
        if number not in numbers:
            numbers.append(number)
    return tuple(numbers)


def _is_no_wbs_display(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {
        "",
        "none",
        "null",
        "no wbs required",
        "wbs not required",
        "not required",
    }


def _is_generic_wbs_display(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {
        "wbs",
        "generic_wbs",
        "wbs required",
        "wbs required, type unspecified",
        "wbs required, type unknown",
        "required, type unspecified",
        "required, type unknown",
    }


def _suppress_invalid_wbs_issue(
    *,
    issue: Any,
    listing: Listing,
    parser_snapshot: Dict[str, Any],
) -> bool:
    field = _issue_field(issue)
    if "wbs" not in field:
        return False

    requirement = effective_wbs_requirement(
        parsed_required_wbs=_listing_constraints(listing).required_wbs,
        listing_title=listing.title,
        listing_text=listing.raw_text,
    )
    parser_display = parser_snapshot.get("display_wbs")

    if not requirement.requires_wbs:
        return _is_no_wbs_display(parser_display)

    if requirement.allowed_percentages:
        return _display_wbs_numbers(parser_display) == tuple(requirement.allowed_percentages)

    if requirement.required_wbs == GENERIC_WBS_REQUIREMENT:
        return _is_generic_wbs_display(parser_display)

    return False


def _apply_deterministic_guardrails(
    *,
    listing: Listing,
    parser_snapshot: Dict[str, Any],
    ai_result: Dict[str, Any],
    alert_threshold: int,
) -> Dict[str, Any]:
    issues = ai_result.get("issues")
    if not isinstance(issues, list) or not issues:
        return ai_result

    kept_issues = [
        issue
        for issue in issues
        if not _suppress_invalid_wbs_issue(
            issue=issue,
            listing=listing,
            parser_snapshot=parser_snapshot,
        )
    ]
    if len(kept_issues) == len(issues):
        return ai_result

    result = dict(ai_result)
    result["issues"] = kept_issues
    result["guardrails"] = {
        "suppressed_wbs_issues": len(issues) - len(kept_issues),
    }
    if not kept_issues:
        result["risk_score"] = min(int(result.get("risk_score") or 0), 20)
        result["parser_result_correct"] = True
        result["should_alert_admin"] = False
    else:
        result["should_alert_admin"] = int(result.get("risk_score") or 0) >= alert_threshold
    return result


def _issue(
    *,
    field: str,
    parser_value: Any,
    ai_value: Any,
    reason: str,
    severity: str = "medium",
    evidence: str = "",
) -> Dict[str, Any]:
    return {
        "field": field,
        "parser_value": parser_value,
        "ai_value": ai_value,
        "reason": reason,
        "severity": severity,
        "evidence": evidence,
    }


def _mock_ai_qa_result(
    *,
    listing: Listing,
    parser_snapshot: Dict[str, Any],
    alert_threshold: int,
) -> Dict[str, Any]:
    text = f"{listing.title or ''}\n{listing.raw_text or ''}".strip()
    expected_wbs = display_wbs_options_for_listing_text(
        parsed_required_wbs=None,
        listing_title=listing.title,
        listing_text=listing.raw_text,
    )
    expected_requirement = effective_wbs_requirement(
        parsed_required_wbs=None,
        listing_title=listing.title,
        listing_text=listing.raw_text,
    )
    address_diag = address_diagnostics(text, parser_snapshot.get("address"))
    issues: list[Dict[str, Any]] = []

    if str(parser_snapshot.get("display_wbs") or "") != expected_wbs:
        issues.append(
            _issue(
                field="display_wbs",
                parser_value=parser_snapshot.get("display_wbs"),
                ai_value=expected_wbs,
                reason="The text states a different WBS condition.",
                severity="high",
                evidence=expected_requirement.evidence or "",
            )
        )
    expected_rooms = extract_rooms(text)
    if expected_rooms is not None and not _values_match(
        parser_snapshot.get("rooms"),
        expected_rooms,
    ):
        issues.append(
            _issue(
                field="rooms",
                parser_value=parser_snapshot.get("rooms"),
                ai_value=expected_rooms,
                reason="The text states a different room count.",
                severity="high",
                evidence=str(expected_rooms),
            )
        )
    expected_rent_kalt = extract_rent_display(listing.raw_text, KALT_RENT_LABELS)
    if expected_rent_kalt is not None and not _values_match(
        parser_snapshot.get("rent_kalt"),
        expected_rent_kalt,
    ):
        issues.append(
            _issue(
                field="rent_kalt",
                parser_value=parser_snapshot.get("rent_kalt"),
                ai_value=expected_rent_kalt,
                reason="The text states a different Kaltmiete.",
                severity="high",
                evidence=expected_rent_kalt,
            )
        )
    expected_rent_warm = extract_rent_display(listing.raw_text, WARM_RENT_LABELS)
    if expected_rent_warm is not None and not _values_match(
        parser_snapshot.get("rent_warm"),
        expected_rent_warm,
    ):
        issues.append(
            _issue(
                field="rent_warm",
                parser_value=parser_snapshot.get("rent_warm"),
                ai_value=expected_rent_warm,
                reason="The text states a different Warmmiete/Gesamtmiete.",
                severity="high",
                evidence=expected_rent_warm,
            )
        )
    if address_diag.sanity_status == "warning" and address_diag.source == "missing":
        issues.append(
            _issue(
                field="address",
                parser_value=parser_snapshot.get("address"),
                ai_value=None,
                reason=address_diag.sanity_details,
                severity="low",
            )
        )

    high_issue_count = sum(
        1 for issue in issues if str(issue.get("severity")).lower() == "high"
    )
    risk_score = 85 if high_issue_count else (45 if issues else 10)
    result = {
        "parser_result_correct": not issues,
        "risk_score": risk_score,
        "confidence": 0.7 if issues else 0.8,
        "issues": issues,
        "suggested_values": {},
        "wbs_source_interpretation": {
            "kind": (
                "specific_wbs_values"
                if expected_requirement.allowed_percentages
                else (
                    "generic_wbs_required"
                    if expected_requirement.requires_wbs
                    else (
                        "no_wbs_required"
                        if expected_requirement.rule_type == "explicit_no_wbs"
                        else "no_wbs_mentioned"
                    )
                )
            ),
            "evidence": expected_requirement.evidence or "",
            "specific_values_found": list(expected_requirement.allowed_percentages),
            "explanation": "Deterministic mock QA interpretation for local demos.",
        },
        "should_alert_admin": risk_score >= alert_threshold,
        "provider": "mock",
    }
    return _apply_deterministic_guardrails(
        listing=listing,
        parser_snapshot=parser_snapshot,
        ai_result=result,
        alert_threshold=alert_threshold,
    )


def _call_openai_ai_qa(
    *,
    listing: Listing,
    parser_snapshot: Dict[str, Any],
) -> tuple[Dict[str, Any], int, int, float]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured for AI QA.")

    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.chat.completions.create(
        model=settings.ai_qa_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": AI_QA_SYSTEM_MESSAGE},
            {"role": "user", "content": _user_message(listing, parser_snapshot)},
        ],
    )
    content = completion.choices[0].message.content or "{}"
    payload = _normalize_ai_result(
        _extract_json_payload(content),
        alert_threshold=settings.ai_qa_alert_risk_threshold,
    )
    payload = _apply_deterministic_guardrails(
        listing=listing,
        parser_snapshot=parser_snapshot,
        ai_result=payload,
        alert_threshold=settings.ai_qa_alert_risk_threshold,
    )
    prompt_tokens = _safe_usage_value(completion.usage, "prompt_tokens")
    completion_tokens = _safe_usage_value(completion.usage, "completion_tokens")
    total_cost_usd = calculate_openai_cost_usd(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return payload, prompt_tokens, completion_tokens, total_cost_usd


def run_ai_qa_check_for_listing(
    listing: Listing,
    *,
    provider: Optional[str] = None,
) -> tuple[Dict[str, Any], int, int, float]:
    settings = get_settings()
    qa_provider = (provider or settings.ai_qa_provider or "mock").strip().lower()
    parser_snapshot = build_parser_snapshot(listing)
    if qa_provider == "mock":
        return (
            _mock_ai_qa_result(
                listing=listing,
                parser_snapshot=parser_snapshot,
                alert_threshold=settings.ai_qa_alert_risk_threshold,
            ),
            0,
            0,
            0.0,
        )
    if qa_provider == "openai":
        return _call_openai_ai_qa(
            listing=listing,
            parser_snapshot=parser_snapshot,
        )
    raise ValueError(f"Unsupported AI_QA_PROVIDER={qa_provider!r}.")


def run_ai_qa_demo_check_for_listing(
    listing: Listing,
    *,
    provider: Optional[str] = None,
    fault_type: str = "auto",
) -> AIQADemoResult:
    settings = get_settings()
    qa_provider = (provider or settings.ai_qa_provider or "mock").strip().lower()
    parser_snapshot, fault = build_demo_fault_parser_snapshot(
        listing,
        fault_type=fault_type,
    )
    if qa_provider == "mock":
        ai_result, prompt_tokens, completion_tokens, total_cost_usd = (
            _mock_ai_qa_result(
                listing=listing,
                parser_snapshot=parser_snapshot,
                alert_threshold=settings.ai_qa_alert_risk_threshold,
            ),
            0,
            0,
            0.0,
        )
    elif qa_provider == "openai":
        ai_result, prompt_tokens, completion_tokens, total_cost_usd = _call_openai_ai_qa(
            listing=listing,
            parser_snapshot=parser_snapshot,
        )
    else:
        raise ValueError(f"Unsupported AI_QA_PROVIDER={qa_provider!r}.")

    ai_result = dict(ai_result)
    ai_result["demo_fault_injection"] = fault
    return AIQADemoResult(
        listing=listing,
        parser_snapshot=parser_snapshot,
        ai_result=ai_result,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd,
        fault=fault,
    )


def _call_configured_ai_qa(
    *,
    listing: Listing,
    parser_snapshot: Dict[str, Any],
) -> tuple[Dict[str, Any], int, int, float]:
    settings = get_settings()
    qa_provider = settings.ai_qa_provider
    if qa_provider == "mock":
        return (
            _mock_ai_qa_result(
                listing=listing,
                parser_snapshot=parser_snapshot,
                alert_threshold=settings.ai_qa_alert_risk_threshold,
            ),
            0,
            0,
            0.0,
        )
    if qa_provider == "openai":
        return _call_openai_ai_qa(
            listing=listing,
            parser_snapshot=parser_snapshot,
        )
    raise ValueError(f"Unsupported AI_QA_PROVIDER={qa_provider!r}.")


def _daily_ai_qa_usage(session: Session) -> tuple[int, float]:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    checks = session.scalar(
        select(func.count(AIQAReview.review_id)).where(AIQAReview.created_at >= today)
    )
    cost = session.scalar(
        select(func.coalesce(func.sum(AIQAReview.total_cost_usd), 0.0)).where(
            AIQAReview.created_at >= today
        )
    )
    return int(checks or 0), float(cost or 0.0)


def _active_listing_statement(
    *,
    source_company: str,
    removed_status: str,
) -> Any:
    return (
        select(Listing)
        .where(Listing.source_company == source_company)
        .where(Listing.source_active.is_(True))
        .where(Listing.status != removed_status)
    )


def _current_version_review_exists() -> Any:
    return (
        select(AIQAReview.review_id)
        .where(AIQAReview.listing_id == Listing.listing_id)
        .where(AIQAReview.qa_prompt_version == CURRENT_AI_QA_PROMPT_VERSION)
        .exists()
    )


def get_ai_qa_status(
    session: Session,
    *,
    source_company: str,
    removed_status: str,
) -> AIQAStatus:
    settings = get_settings()
    checks_today, cost_today = _daily_ai_qa_usage(session)
    version_filter = AIQAReview.qa_prompt_version == CURRENT_AI_QA_PROMPT_VERSION
    active_statement = _active_listing_statement(
        source_company=source_company,
        removed_status=removed_status,
    )
    review_exists = _current_version_review_exists()
    active_listings_count = int(
        session.scalar(select(func.count()).select_from(active_statement.subquery())) or 0
    )
    reviewed_active_count = int(
        session.scalar(
            select(func.count()).select_from(
                active_statement.where(review_exists).subquery()
            )
        )
        or 0
    )
    unreviewed_active_count = int(
        session.scalar(
            select(func.count()).select_from(
                active_statement.where(~review_exists).subquery()
            )
        )
        or 0
    )
    total_reviews_count = int(
        session.scalar(
            select(func.count(AIQAReview.review_id)).where(version_filter)
        )
        or 0
    )
    pending_alerts_count = int(
        session.scalar(
            select(func.count(AIQAReview.review_id))
            .where(version_filter)
            .where(AIQAReview.should_alert_admin.is_(True))
            .where(AIQAReview.feedback_status == AI_QA_FEEDBACK_PENDING)
        )
        or 0
    )
    parser_error_feedback_count = int(
        session.scalar(
            select(func.count(AIQAReview.review_id))
            .where(version_filter)
            .where(AIQAReview.feedback_status == AI_QA_FEEDBACK_PARSER_ERROR)
        )
        or 0
    )
    parser_correct_feedback_count = int(
        session.scalar(
            select(func.count(AIQAReview.review_id))
            .where(version_filter)
            .where(AIQAReview.feedback_status == AI_QA_FEEDBACK_PARSER_CORRECT)
        )
        or 0
    )
    unsure_feedback_count = int(
        session.scalar(
            select(func.count(AIQAReview.review_id))
            .where(version_filter)
            .where(AIQAReview.feedback_status == AI_QA_FEEDBACK_UNSURE)
        )
        or 0
    )
    latest_review_at = session.scalar(
        select(func.max(AIQAReview.created_at)).where(version_filter)
    )
    return AIQAStatus(
        qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
        enabled=settings.ai_qa_enabled,
        model=settings.ai_qa_model,
        daily_max_cost_usd=settings.ai_qa_daily_max_cost_usd,
        checks_today=checks_today,
        cost_today_usd=cost_today,
        active_listings_count=active_listings_count,
        reviewed_active_count=reviewed_active_count,
        unreviewed_active_count=unreviewed_active_count,
        pending_alerts_count=pending_alerts_count,
        parser_error_feedback_count=parser_error_feedback_count,
        parser_correct_feedback_count=parser_correct_feedback_count,
        unsure_feedback_count=unsure_feedback_count,
        total_reviews_count=total_reviews_count,
        latest_review_at=latest_review_at,
    )


def _can_run_ai_qa(session: Session) -> Optional[str]:
    settings = get_settings()
    if not settings.ai_qa_enabled:
        return "disabled"
    if settings.ai_qa_provider == "openai" and not settings.openai_api_key:
        return "missing_openai_api_key"
    _, cost_today = _daily_ai_qa_usage(session)
    if cost_today >= settings.ai_qa_daily_max_cost_usd:
        return "daily_cost_limit_reached"
    return None


def _record_api_log(
    session: Session,
    *,
    listing_id: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_cost_usd: float,
) -> None:
    session.add(
        APILog(
            target_id=listing_id,
            endpoint_type=AI_QA_ENDPOINT_TYPE,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost_usd=total_cost_usd,
        )
    )


def create_ai_qa_review_for_listing(
    session: Session,
    *,
    listing: Listing,
    trigger_type: str,
) -> Optional[AIQAReview]:
    if session.scalar(
        select(AIQAReview.review_id)
        .where(AIQAReview.listing_id == listing.listing_id)
        .where(AIQAReview.qa_prompt_version == CURRENT_AI_QA_PROMPT_VERSION)
    ):
        return None

    skip_reason = _can_run_ai_qa(session)
    if skip_reason is not None:
        logger.info("AI QA skipped reason=%s listing_id=%s", skip_reason, listing.listing_id)
        return None

    settings = get_settings()
    parser_snapshot = build_parser_snapshot(listing)
    ai_result, prompt_tokens, completion_tokens, total_cost_usd = _call_configured_ai_qa(
        listing=listing,
        parser_snapshot=parser_snapshot,
    )
    review = AIQAReview(
        listing_id=listing.listing_id,
        listing_url=listing.url,
        source_company=listing.source_company,
        trigger_type=trigger_type,
        qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
        raw_text_hash=_hash_payload(listing.raw_text),
        parser_snapshot_hash=_hash_payload(parser_snapshot),
        parser_snapshot=parser_snapshot,
        ai_result=ai_result,
        risk_score=int(ai_result["risk_score"]),
        confidence=float(ai_result["confidence"]),
        parser_result_correct=bool(ai_result["parser_result_correct"]),
        should_alert_admin=bool(ai_result["should_alert_admin"])
        or int(ai_result["risk_score"]) >= settings.ai_qa_alert_risk_threshold,
        alert_sent=False,
        feedback_status=AI_QA_FEEDBACK_PENDING,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd,
    )
    session.add(review)
    _record_api_log(
        session,
        listing_id=listing.listing_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd,
    )
    session.flush()
    return review


def _create_review_from_ai_result(
    session: Session,
    *,
    listing: Listing,
    trigger_type: str,
    parser_snapshot: Dict[str, Any],
    ai_result: Dict[str, Any],
    prompt_tokens: int,
    completion_tokens: int,
    total_cost_usd: float,
) -> Optional[AIQAReview]:
    if session.scalar(
        select(AIQAReview.review_id)
        .where(AIQAReview.listing_id == listing.listing_id)
        .where(AIQAReview.qa_prompt_version == CURRENT_AI_QA_PROMPT_VERSION)
    ):
        return None

    settings = get_settings()
    review = AIQAReview(
        listing_id=listing.listing_id,
        listing_url=listing.url,
        source_company=listing.source_company,
        trigger_type=trigger_type,
        qa_prompt_version=CURRENT_AI_QA_PROMPT_VERSION,
        raw_text_hash=_hash_payload(listing.raw_text),
        parser_snapshot_hash=_hash_payload(parser_snapshot),
        parser_snapshot=parser_snapshot,
        ai_result=ai_result,
        risk_score=int(ai_result["risk_score"]),
        confidence=float(ai_result["confidence"]),
        parser_result_correct=bool(ai_result["parser_result_correct"]),
        should_alert_admin=bool(ai_result["should_alert_admin"])
        or int(ai_result["risk_score"]) >= settings.ai_qa_alert_risk_threshold,
        alert_sent=False,
        feedback_status=AI_QA_FEEDBACK_PENDING,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd,
    )
    session.add(review)
    _record_api_log(
        session,
        listing_id=listing.listing_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd,
    )
    session.flush()
    return review


def _run_ai_qa_call(listing: Listing) -> _AIQACallResult:
    parser_snapshot = build_parser_snapshot(listing)
    ai_result, prompt_tokens, completion_tokens, total_cost_usd = _call_configured_ai_qa(
        listing=listing,
        parser_snapshot=parser_snapshot,
    )
    return _AIQACallResult(
        listing=listing,
        parser_snapshot=parser_snapshot,
        ai_result=ai_result,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd,
    )


def run_ai_qa_for_unreviewed_active_listings(
    session: Session,
    *,
    source_company: str,
    removed_status: str,
    trigger_type: str,
    listing_urls: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
) -> AIQARunResult:
    skip_reason = _can_run_ai_qa(session)
    if skip_reason is not None:
        return AIQARunResult(
            checked_count=0,
            alert_review_ids=(),
            skipped_reason=skip_reason,
            stop_reason=skip_reason,
        )

    review_exists = _current_version_review_exists()
    statement = (
        _active_listing_statement(
            source_company=source_company,
            removed_status=removed_status,
        )
        .where(~review_exists)
        .order_by(Listing.first_seen_at.asc(), Listing.listing_id.asc())
    )
    if listing_urls is not None:
        url_tuple = tuple(listing_urls)
        if not url_tuple:
            return AIQARunResult(checked_count=0, alert_review_ids=(), stop_reason="no_urls")
        statement = statement.where(Listing.url.in_(url_tuple))

    total_unreviewed_before = int(
        session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        or 0
    )
    if limit is not None:
        statement = statement.limit(limit)

    checked_count = 0
    alert_review_ids: List[int] = []
    total_cost = 0.0
    limit_reached = False
    stop_reason = "completed"
    settings = get_settings()
    concurrency = max(1, settings.ai_qa_concurrency)
    listings = list(session.scalars(statement))
    for offset in range(0, len(listings), concurrency):
        skip_reason = _can_run_ai_qa(session)
        if skip_reason is not None:
            limit_reached = skip_reason in {
                "daily_cost_limit_reached",
            }
            stop_reason = skip_reason
            break

        batch = listings[offset : offset + concurrency]
        call_results: List[_AIQACallResult] = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_listing = {
                executor.submit(_run_ai_qa_call, listing): listing for listing in batch
            }
            for future in as_completed(future_to_listing):
                listing = future_to_listing[future]
                try:
                    call_results.append(future.result())
                except Exception:
                    logger.exception("AI QA failed listing_id=%s", listing.listing_id)

        call_results.sort(key=lambda item: item.listing.listing_id)
        for call_result in call_results:
            review = _create_review_from_ai_result(
                session,
                listing=call_result.listing,
                trigger_type=trigger_type,
                parser_snapshot=call_result.parser_snapshot,
                ai_result=call_result.ai_result,
                prompt_tokens=call_result.prompt_tokens,
                completion_tokens=call_result.completion_tokens,
                total_cost_usd=call_result.total_cost_usd,
            )
            if review is None:
                continue
            checked_count += 1
            total_cost += float(review.total_cost_usd or 0.0)
            if review.should_alert_admin:
                alert_review_ids.append(review.review_id)
            session.commit()

    remaining_statement = (
        _active_listing_statement(
            source_company=source_company,
            removed_status=removed_status,
        )
        .where(~review_exists)
    )
    if listing_urls is not None:
        remaining_statement = remaining_statement.where(Listing.url.in_(url_tuple))
    remaining_unreviewed_count = int(
        session.scalar(
            select(func.count()).select_from(remaining_statement.subquery())
        )
        or 0
    )
    if stop_reason == "completed" and remaining_unreviewed_count > 0:
        stop_reason = "batch_limit_reached" if limit is not None else "remaining_unreviewed"

    return AIQARunResult(
        checked_count=checked_count,
        alert_review_ids=tuple(alert_review_ids),
        stop_reason=stop_reason,
        total_unreviewed_before=total_unreviewed_before,
        remaining_unreviewed_count=remaining_unreviewed_count,
        total_cost_usd=total_cost,
        limit_reached=limit_reached,
    )


def load_ai_qa_reviews_for_alert(
    session: Session,
    review_ids: Sequence[int],
) -> List[AIQAReview]:
    if not review_ids:
        return []
    return list(
        session.scalars(
            select(AIQAReview)
            .where(AIQAReview.review_id.in_(tuple(review_ids)))
            .order_by(AIQAReview.risk_score.desc(), AIQAReview.review_id.asc())
        )
    )


def load_flagged_ai_qa_reviews(
    session: Session,
    *,
    limit: int = 10,
    qa_prompt_version: str = CURRENT_AI_QA_PROMPT_VERSION,
) -> List[AIQAReview]:
    flagged_reviews = list(
        session.scalars(
            select(AIQAReview)
            .where(AIQAReview.qa_prompt_version == qa_prompt_version)
            .where(AIQAReview.should_alert_admin.is_(True))
            .where(AIQAReview.feedback_status == AI_QA_FEEDBACK_PENDING)
            .order_by(AIQAReview.risk_score.desc(), AIQAReview.review_id.asc())
            .limit(limit)
        )
    )
    if flagged_reviews:
        return flagged_reviews

    return list(
        session.scalars(
            select(AIQAReview)
            .where(AIQAReview.qa_prompt_version == qa_prompt_version)
            .where(AIQAReview.feedback_status == AI_QA_FEEDBACK_PENDING)
            .order_by(AIQAReview.risk_score.desc(), AIQAReview.review_id.asc())
            .limit(limit)
        )
    )


def update_ai_qa_feedback(
    session: Session,
    *,
    review_id: int,
    feedback_status: str,
    admin_user_id: int,
) -> bool:
    if feedback_status not in {
        AI_QA_FEEDBACK_PARSER_ERROR,
        AI_QA_FEEDBACK_PARSER_CORRECT,
        AI_QA_FEEDBACK_UNSURE,
    }:
        raise ValueError(f"Unsupported AI QA feedback status: {feedback_status}")
    review = session.get(AIQAReview, review_id)
    if review is None:
        return False
    review.feedback_status = feedback_status
    review.feedback_by = admin_user_id
    review.feedback_at = datetime.utcnow()
    return True
