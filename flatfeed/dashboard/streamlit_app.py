from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.run_eval import run_eval  # noqa: E402
from flatfeed.ai_qa import (  # noqa: E402
    AI_QA_FEEDBACK_PARSER_CORRECT,
    AI_QA_FEEDBACK_PARSER_ERROR,
    AI_QA_FEEDBACK_PENDING,
    AI_QA_FEEDBACK_UNSURE,
    AI_QA_DEMO_FAULT_TYPES,
    AI_QA_HISTORY_SOURCE_CAPTION,
    CURRENT_AI_QA_PROMPT_VERSION,
    build_parser_snapshot,
    get_ai_qa_status,
    run_ai_qa_demo_check_for_listing,
)
from flatfeed.config import get_settings  # noqa: E402
from flatfeed.db.models import AIQAReview, Listing, SentListingNotification  # noqa: E402
from flatfeed.db.session import SessionLocal, init_db  # noqa: E402
from flatfeed.ingestion import ENABLED_SOURCE_COMPANIES, REMOVED_STATUS  # noqa: E402
from flatfeed.matching import effective_wbs_requirement  # noqa: E402
from flatfeed.monitoring import (  # noqa: E402
    INGESTION_STATUS_PARTIAL_SUCCESS,
    load_ingestion_health_summary,
)
from flatfeed.schemas import ListingConstraints  # noqa: E402


FIELD_LABELS = {
    "wbs": "WBS",
    "display_wbs": "WBS",
    "required_wbs": "WBS",
    "rooms": "Rooms",
    "room_count": "Rooms",
    "floor": "Floor",
    "address": "Address",
    "postal_code": "Postal code",
    "district": "District",
    "rent_kalt": "Kalt",
    "kalt": "Kalt",
    "rent_warm": "Warm",
    "warm": "Warm",
}

FEEDBACK_LABELS = {
    AI_QA_FEEDBACK_PENDING: "Pending review",
    AI_QA_FEEDBACK_PARSER_ERROR: "Confirmed error",
    AI_QA_FEEDBACK_PARSER_CORRECT: "False alarm",
    AI_QA_FEEDBACK_UNSURE: "Borderline / unsure",
}

# Reviews written under a "<version>-demo" prompt version are ephemeral,
# non-persisted-in-spirit demo artifacts (see main.py's guided tour, Variant
# B). Nothing in the product currently writes rows shaped this way, but every
# query here excludes them anyway as defense in depth: the dashboard must
# only ever report a curated evaluation history, never something a visitor
# could influence by tapping a demo button.
_DEMO_VERSION_SUFFIX = "-demo"


def fmt_share(numerator: int, denominator: int) -> str:
    """Percent once the sample is large enough to mean something (>= 20),
    otherwise the raw count — a 2-of-3 stated as "66.7%" reads as more
    precise than it is."""
    if denominator <= 0:
        return "no data"
    if denominator >= 20:
        return f"{numerator / denominator:.1%}"
    return f"{numerator} of {denominator}"


def _money(value: Optional[float]) -> str:
    return f"${float(value or 0):,.4f}"


def _price_per_1m(value: Optional[float]) -> str:
    # Escaped: two unescaped "$...$" amounts in one st.caption/markdown
    # string make Streamlit render the text between them as LaTeX math
    # instead of plain text (pre-existing bug, fixed here since this
    # helper's only caption call site combines two of these).
    return f"\\${float(value or 0):,.2f} / 1M"


def _format_time(value: object) -> str:
    if value is None:
        return "no data"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _no_data() -> str:
    return "no data"


def _safe_issues(ai_result: object) -> List[Dict[str, Any]]:
    if not isinstance(ai_result, dict):
        return []
    issues = ai_result.get("issues") or []
    if not isinstance(issues, list):
        return []
    return [issue for issue in issues if isinstance(issue, dict)]


def _issue_fields(ai_result: object) -> List[str]:
    labels: List[str] = []
    for issue in _safe_issues(ai_result):
        field = str(issue.get("field") or "").strip().lower()
        labels.append(FIELD_LABELS.get(field, field or "Other"))
    return labels or ["Other"]


def _issue_summary(ai_result: object, *, limit: int = 2) -> str:
    parts: List[str] = []
    for issue in _safe_issues(ai_result)[:limit]:
        field = str(issue.get("field") or "").strip().lower()
        label = FIELD_LABELS.get(field, field or "Other")
        parser_value = issue.get("parser_value")
        ai_value = issue.get("ai_value")
        reason = str(issue.get("reason") or "").strip()
        if parser_value is not None or ai_value is not None:
            parts.append(f"{label}: parser={parser_value}; AI={ai_value}. {reason[:120]}")
        else:
            parts.append(f"{label}: {reason[:160]}")
    return " | ".join(parts)


def _load_active_ai_qa_coverage() -> Dict[str, int]:
    with SessionLocal() as session:
        statuses = [
            get_ai_qa_status(
                session,
                source_company=source_company,
                removed_status=REMOVED_STATUS,
            )
            for source_company in ENABLED_SOURCE_COMPANIES
        ]
    return {
        "active": sum(status.active_listings_count for status in statuses),
        "reviewed_active": sum(status.reviewed_active_count for status in statuses),
        "unreviewed_active": sum(status.unreviewed_active_count for status in statuses),
    }


def _load_review_rows() -> pd.DataFrame:
    with SessionLocal() as session:
        rows = session.execute(
            select(
                AIQAReview.review_id,
                AIQAReview.created_at,
                AIQAReview.qa_prompt_version,
                AIQAReview.source_company,
                AIQAReview.listing_url,
                AIQAReview.risk_score,
                AIQAReview.confidence,
                AIQAReview.should_alert_admin,
                AIQAReview.feedback_status,
                AIQAReview.total_cost_usd,
                AIQAReview.ai_result,
            )
            # Defense in depth (see _DEMO_VERSION_SUFFIX above): even a
            # future non-persisting-in-spirit demo path must not surface here.
            .where(~AIQAReview.qa_prompt_version.like(f"%{_DEMO_VERSION_SUFFIX}"))
            .order_by(AIQAReview.created_at.desc(), AIQAReview.review_id.desc())
        ).all()

    frame = pd.DataFrame(
        rows,
        columns=[
            "review_id",
            "created_at",
            "qa_prompt_version",
            "source_company",
            "listing_url",
            "risk_score",
            "confidence",
            "should_alert_admin",
            "feedback_status",
            "total_cost_usd",
            "ai_result",
        ],
    )
    if frame.empty:
        return frame
    frame["feedback_label"] = frame["feedback_status"].map(
        lambda value: FEEDBACK_LABELS.get(str(value), str(value))
    )
    frame["issue_fields"] = frame["ai_result"].map(_issue_fields)
    frame["issue_summary"] = frame["ai_result"].map(_issue_summary)
    frame["created_at_label"] = frame["created_at"].map(_format_time)
    return frame


def _current_version(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[frame["qa_prompt_version"] == CURRENT_AI_QA_PROMPT_VERSION].copy()


def _reviewed_feedback(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[
        frame["feedback_status"].isin(
            [
                AI_QA_FEEDBACK_PARSER_ERROR,
                AI_QA_FEEDBACK_PARSER_CORRECT,
                AI_QA_FEEDBACK_UNSURE,
            ]
        )
    ]


def _confirmed_or_false_feedback(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[
        frame["feedback_status"].isin(
            [AI_QA_FEEDBACK_PARSER_ERROR, AI_QA_FEEDBACK_PARSER_CORRECT]
        )
    ]


def _render_metric_guide() -> None:
    with st.expander("How to read this dashboard", expanded=False):
        st.markdown(
            """
            - **Active catalog coverage** shows how much of the current synthetic catalog has been reviewed by the current AI QA version.
            - **AI risk signals** are checks the model flagged as a possible material parser error for admin review. A flag is a prediction, not a confirmed error.
            - **Useful signal rate** shows how often reviewed AI signals became confirmed parser errors. Higher is better. Shown as a share only once at least 20 decisive reviews exist; below that, a raw "N of D" count is more honest than a precise-looking percentage.
            - **False alarm rate** shows how often AI distracted the admin without a real parser error. Lower is better.
            - **Cost per confirmed error** shows model cost per admin-confirmed parser error. Lower is better.
            """
        )


# ---------------------------------------------------------------------------
# Section 1 — pipeline readiness
# ---------------------------------------------------------------------------


def _load_delivery_count() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count(SentListingNotification.notification_id))) or 0


def _render_pipeline_readiness(coverage_counts: Dict[str, int]) -> None:
    st.subheader("Is the demo pipeline ready to deliver trusted matches?")
    st.caption(
        "Collect → Normalize → Verify → Match → Notify. Every listing goes through all "
        "five steps before a renter ever sees it; AI QA is a separate check on step 2, "
        "described in its own section below."
    )

    active_count = coverage_counts["active"]
    reviewed_active_count = coverage_counts["reviewed_active"]
    delivery_count = _load_delivery_count()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Active listings",
        f"{active_count:,}",
        help="How many listings are currently active in the bot database.",
    )
    c2.metric(
        "AI QA coverage",
        fmt_share(reviewed_active_count, active_count),
        help="Share of active listings reviewed by the current AI QA version.",
    )
    c3.metric(
        "One-time deliveries recorded",
        f"{delivery_count:,}",
        help="Notification records — proves each match is sent to a renter at most once, ever.",
    )
    c4.metric(
        "Golden-set listings",
        f"{_golden_set_size():,}",
        help="Size of the fixed synthetic evaluation set the parser is regression-tested against.",
    )
    st.caption(f"Current AI QA version: {CURRENT_AI_QA_PROMPT_VERSION}.")


def _golden_set_size() -> int:
    from synthetic.golden_set import load_golden_set

    return len(load_golden_set())


# ---------------------------------------------------------------------------
# Section 2 — source trust
# ---------------------------------------------------------------------------


def _render_source_trust() -> None:
    st.subheader("Can FlatFeed trust and deliver what it collected?")
    summaries = {
        source_company: load_ingestion_health_summary(source_company=source_company)
        for source_company in ENABLED_SOURCE_COMPANIES
    }

    statuses = [summary.latest_status for summary in summaries.values()]
    if statuses and all(status == "success" for status in statuses):
        st.success("The synthetic catalog is refreshing successfully.")
    elif any(status in {INGESTION_STATUS_PARTIAL_SUCCESS, "failed"} for status in statuses):
        st.warning("The synthetic catalog has a partial or failed refresh.")
    elif all(status is None for status in statuses):
        st.info("The synthetic catalog has not been refreshed yet.")
    else:
        st.info("The synthetic catalog still has incomplete refresh history.")

    health_rows = pd.DataFrame(
        [
            {
                "Source": source_company,
                "Status": summary.latest_status or "no data",
                "Latest success": _format_time(summary.last_success_at),
                "Consecutive failures": summary.consecutive_failures,
            }
            for source_company, summary in summaries.items()
        ]
    )
    st.dataframe(health_rows, width="stretch", hide_index=True)
    st.caption(
        "Only `FlatFeed Synthetic` is implemented today. The source-adapter registry, "
        "activity re-checks, and this health table are built to hold more sources; live "
        "collection from real housing sites is explicitly out of scope for this demo "
        "(no scraping, no terms-of-service review has been done)."
    )


# ---------------------------------------------------------------------------
# Section 3 — parsing accuracy
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _load_golden_set_eval() -> Dict[str, Any]:
    return run_eval(provider="mock")


def _select_example_listing() -> Optional[Listing]:
    """The same selection heuristic as the bot's guided tour (main.py
    _select_tour_listing): 2 rooms, a WBS requirement including 140, a WBS
    phrase in the raw text, and transit data — so a visitor who did the tour
    sees the identical worked example here, not a different cherry-pick."""
    with SessionLocal() as session:
        candidates = list(
            session.scalars(
                select(Listing)
                .where(Listing.source_company.in_(ENABLED_SOURCE_COMPANIES))
                .where(Listing.source_active.is_(True))
                .where(Listing.status != REMOVED_STATUS)
                .order_by(Listing.first_seen_at.asc(), Listing.listing_id.asc())
            )
        )
    for listing in candidates:
        if listing.rooms != 2:
            continue
        if "wbs" not in (listing.raw_text or "").lower():
            continue
        transport_walk = listing.transport_walk or {}
        if (
            transport_walk.get("s_bahn_minutes") is None
            and transport_walk.get("u_bahn_minutes") is None
        ):
            continue
        constraints = (
            ListingConstraints.model_validate(listing.parsed_constraints)
            if listing.parsed_constraints
            else ListingConstraints()
        )
        requirement = effective_wbs_requirement(
            parsed_required_wbs=constraints.required_wbs,
            listing_title=listing.title,
            listing_text=listing.raw_text,
        )
        if 140 in (requirement.allowed_percentages or ()):
            return listing
    return candidates[0] if candidates else None


def _render_parsing_accuracy() -> None:
    st.subheader("How accurate is deterministic parsing?")
    result = _load_golden_set_eval()
    parser = result["parser"]

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Field accuracy",
        f"{parser['field_accuracy']:.1%}",
        help="Correct fields / total fields across the golden set, computed live from eval.run_eval.",
    )
    c2.metric(
        "Exact listing accuracy",
        f"{parser['exact_listing_accuracy']:.1%}",
        help="Share of listings where every field matched the hidden ground truth.",
    )
    c3.metric(
        "Golden-set size",
        f"{result['listing_count']:,}",
        help="Fixed synthetic cases with hidden ground truth (synthetic/golden_set.py).",
    )
    st.caption(
        "These numbers are not hand-typed — this page runs the same "
        "`eval.run_eval` harness used in CI and the README on every load."
    )

    example = _select_example_listing()
    if example is not None:
        snapshot = build_parser_snapshot(example)
        with st.expander("Worked example: raw text → parsed fields", expanded=False):
            st.markdown("Raw listing text:")
            st.code(example.raw_text or "", language="text")
            st.markdown("Parser output:")
            st.json(
                {
                    "WBS": snapshot.get("display_wbs"),
                    "Rooms": snapshot.get("rooms"),
                    "Floor": snapshot.get("floor"),
                    "District": snapshot.get("district"),
                    "Kalt": snapshot.get("rent_kalt"),
                    "Warm": snapshot.get("rent_warm"),
                }
            )
    st.caption(
        "Fail-closed rule: an unknown Kaltmiete or room count never matches a "
        "specific filter value — the bot never guesses on a renter's behalf."
    )


# ---------------------------------------------------------------------------
# Section 4 — AI QA usefulness
# ---------------------------------------------------------------------------


def _render_ai_qa_quality(current_reviews: pd.DataFrame) -> None:
    total_checks = len(current_reviews)
    alerts = int(current_reviews["should_alert_admin"].sum()) if not current_reviews.empty else 0
    reviewed = _reviewed_feedback(current_reviews)
    decisive = _confirmed_or_false_feedback(current_reviews)
    confirmed = int(
        (current_reviews["feedback_status"] == AI_QA_FEEDBACK_PARSER_ERROR).sum()
    ) if not current_reviews.empty else 0
    false_alarms = int(
        (current_reviews["feedback_status"] == AI_QA_FEEDBACK_PARSER_CORRECT).sum()
    ) if not current_reviews.empty else 0
    pending_alerts = int(
        (
            current_reviews["should_alert_admin"]
            & (current_reviews["feedback_status"] == AI_QA_FEEDBACK_PENDING)
        ).sum()
    ) if not current_reviews.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total AI checks", f"{total_checks:,}", help="Listings checked by the current AI QA version.")
    c2.metric("AI risk signals", f"{alerts:,}", help="Checks AI flagged as a possible parser error and sent to the admin.")
    c3.metric("Human reviewed", f"{len(reviewed):,}", help="AI reports that received admin feedback.")
    c4.metric("Pending review", f"{pending_alerts:,}", help="Flagged reports still neither confirmed nor rejected.")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Confirmed errors", f"{confirmed:,}", help="AI alerts the admin confirmed as real parser errors.")
    c6.metric("False alarms", f"{false_alarms:,}", help="AI alerts the admin marked as correct parser behavior.")
    c7.metric(
        "Useful signal rate",
        fmt_share(confirmed, len(decisive)),
        help="Confirmed errors among reports where the admin gave a clear decision.",
    )
    c8.metric(
        "False alarm rate",
        fmt_share(false_alarms, len(decisive)),
        help="False alarms among reports where the admin gave a clear decision.",
    )


def _render_ai_qa_cost(current_reviews: pd.DataFrame) -> None:
    total_checks = len(current_reviews)
    total_cost = float(current_reviews["total_cost_usd"].sum()) if not current_reviews.empty else 0.0
    alerts = int(current_reviews["should_alert_admin"].sum()) if not current_reviews.empty else 0
    confirmed = int(
        (current_reviews["feedback_status"] == AI_QA_FEEDBACK_PARSER_ERROR).sum()
    ) if not current_reviews.empty else 0
    cost_per_check = total_cost / total_checks if total_checks else 0.0
    cost_per_alert = total_cost / alerts if alerts else 0.0
    cost_per_confirmed = total_cost / confirmed if confirmed else None
    settings = get_settings()

    c0, c1, c2, c3, c4 = st.columns(5)
    provider = settings.ai_qa_provider
    c0.metric(
        "AI QA provider",
        (
            f"openai · {settings.ai_qa_model}"
            if provider == "openai"
            else f"{provider} — no API calls"
        ),
        help="The mock provider is local, deterministic, and free. OpenAI runs use the configured model and prices.",
    )
    c1.metric("Spent on current version", _money(total_cost), help="Total OpenAI cost for AI QA reviews in the current version.")
    c2.metric("Cost per check", _money(cost_per_check), help="Average cost to check one listing.")
    c3.metric("Cost per alert", _money(cost_per_alert), help="Average cost per case where AI sent a report to the admin.")
    c4.metric(
        "Cost per confirmed error",
        _money(cost_per_confirmed) if cost_per_confirmed is not None else _no_data(),
        help="Cost of one human-confirmed parser error. Appears after the first confirmed error.",
    )
    st.caption(
        "OpenAI cost calculation uses configured prices: "
        f"input {_price_per_1m(settings.openai_input_price_per_1m)}, "
        f"output {_price_per_1m(settings.openai_output_price_per_1m)}. "
        f"{AI_QA_HISTORY_SOURCE_CAPTION}"
    )


def _load_demo_listings() -> List[Listing]:
    with SessionLocal() as session:
        return list(
            session.scalars(
                select(Listing)
                .where(Listing.source_active.is_(True))
                .where(Listing.status != REMOVED_STATUS)
                .order_by(Listing.first_seen_at.asc(), Listing.listing_id.asc())
                .limit(25)
            )
        )


def _render_demo_issues(ai_result: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for issue in _safe_issues(ai_result):
        rows.append(
            {
                "Field": FIELD_LABELS.get(
                    str(issue.get("field") or "").strip().lower(),
                    str(issue.get("field") or "Other"),
                ),
                "Parser": issue.get("parser_value"),
                "AI": issue.get("ai_value"),
                "Severity": issue.get("severity"),
                "Reason": issue.get("reason"),
            }
        )
    return pd.DataFrame(rows)


def _render_demo_fault_check() -> None:
    st.markdown("#### Try it yourself: inject a parser fault")
    st.caption(
        "This block intentionally corrupts one parser snapshot and sends AI only raw text + "
        "the corrupted snapshot. Ground truth and the injection flag are not sent to the model prompt. "
        "The result is not saved to production AI QA metrics."
    )

    listings = _load_demo_listings()
    if not listings:
        st.info("There are no active synthetic listings for demo QA.")
        return

    listing_by_label = {
        f"{listing.listing_id}: {listing.title or listing.url}": listing
        for listing in listings
    }
    selected_label = st.selectbox(
        "Demo listing",
        options=list(listing_by_label.keys()),
    )
    fault_type = st.selectbox(
        "Parser error to simulate",
        options=["auto", *AI_QA_DEMO_FAULT_TYPES],
    )
    provider = get_settings().ai_qa_provider
    st.caption(
        f"QA provider: {provider}. In mock mode the cost is zero; "
        "in openai mode this will make one real API call."
    )

    if not st.button("Run QA demo"):
        return

    listing = listing_by_label[selected_label]
    try:
        result = run_ai_qa_demo_check_for_listing(
            listing,
            fault_type=fault_type,
        )
    except Exception as exc:
        st.error(f"Demo AI QA failed to start: {exc}")
        return

    fault = result.fault
    st.success(
        "Demo fault injected: "
        f"{fault['field']} = {fault['injected_value']} "
        f"(was: {fault['original_value']})."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk score", f"{int(result.ai_result.get('risk_score') or 0)} of 100")
    c2.metric("Alert", "yes" if result.ai_result.get("should_alert_admin") else "no")
    c3.metric(
        "AI confidence" if provider != "mock" else "AI confidence (illustrative mock score)",
        f"{float(result.ai_result.get('confidence') or 0.0):.2f}",
    )
    c4.metric("Cost", _money(result.total_cost_usd))

    issues = _render_demo_issues(result.ai_result)
    if issues.empty:
        st.warning("AI did not find a problem in the corrupted snapshot.")
    else:
        st.dataframe(issues, width="stretch", hide_index=True)

    with st.expander("What AI saw", expanded=False):
        st.markdown("Parser snapshot:")
        st.json(result.parser_snapshot)
        st.markdown("Raw listing text:")
        st.code(f"{listing.title or ''}\n{listing.raw_text or ''}", language="text")


def _render_field_quality(current_reviews: pd.DataFrame) -> None:
    field_stats: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "AI risk signals": 0,
            "Confirmed errors": 0,
            "False alarms": 0,
            "_risk_total": 0.0,
        }
    )
    for row in current_reviews.itertuples(index=False):
        if not bool(row.should_alert_admin):
            continue
        fields = set(row.issue_fields)
        for field in fields:
            stats = field_stats[field]
            stats["AI risk signals"] += 1
            stats["_risk_total"] += float(row.risk_score or 0)
            if row.feedback_status == AI_QA_FEEDBACK_PARSER_ERROR:
                stats["Confirmed errors"] += 1
            elif row.feedback_status == AI_QA_FEEDBACK_PARSER_CORRECT:
                stats["False alarms"] += 1

    rows = []
    for field, stats in field_stats.items():
        alerts = int(stats["AI risk signals"])
        confirmed = int(stats["Confirmed errors"])
        false_alarms = int(stats["False alarms"])
        decisive = confirmed + false_alarms
        rows.append(
            {
                "Field": field,
                "AI risk signals": alerts,
                "Confirmed errors": confirmed,
                "False alarms": false_alarms,
                "Useful signal rate": fmt_share(confirmed, decisive),
                "Average risk score (0-100)": round(stats["_risk_total"] / alerts, 1) if alerts else 0.0,
            }
        )

    st.markdown("#### Where the parser is most at risk")
    st.caption(
        "Which fields AI most often flags as risky, and where the admin has already "
        "confirmed errors."
    )
    if not rows:
        st.info("There are no field-level AI alerts yet.")
        return
    frame = pd.DataFrame(rows).sort_values(
        ["Confirmed errors", "AI risk signals"], ascending=False
    )
    st.dataframe(frame, width="stretch", hide_index=True)


def _render_versions(all_reviews: pd.DataFrame) -> None:
    st.markdown("#### How AI QA quality changed by version")
    st.caption(
        "Versions show whether a new prompt or guardrails reduced noise or improved quality."
    )
    if all_reviews.empty:
        st.info("There are no AI checks yet.")
        return

    rows = []
    for version, group in all_reviews.groupby("qa_prompt_version"):
        decisive = _confirmed_or_false_feedback(group)
        confirmed = int((group["feedback_status"] == AI_QA_FEEDBACK_PARSER_ERROR).sum())
        false_alarms = int((group["feedback_status"] == AI_QA_FEEDBACK_PARSER_CORRECT).sum())
        rows.append(
            {
                "Version": version,
                "Checks": len(group),
                "AI risk signals": int(group["should_alert_admin"].sum()),
                "Human reviewed": len(_reviewed_feedback(group)),
                "Confirmed errors": confirmed,
                "False alarms": false_alarms,
                "Useful signal rate": fmt_share(confirmed, len(decisive)),
                "Cost": _money(float(group["total_cost_usd"].sum())),
            }
        )
    frame = pd.DataFrame(rows).sort_values("Version", ascending=False)
    st.dataframe(frame, width="stretch", hide_index=True)


def _review_table(
    reviews: pd.DataFrame,
    *,
    title: str,
    description: str,
    empty_text: str,
    limit: int = 25,
) -> None:
    st.markdown(f"#### {title}")
    st.caption(description)
    if reviews.empty:
        st.info(empty_text)
        return

    table = reviews.head(limit).copy()
    table["Fields"] = table["issue_fields"].map(lambda values: ", ".join(values))
    table["Risk score (0-100)"] = table["risk_score"].map(lambda value: int(value))
    table["AI confidence"] = table["confidence"].map(lambda value: f"{float(value):.2f}")
    table["Date"] = table["created_at_label"]
    table["Status"] = table["feedback_label"]
    table["Source"] = table["source_company"]
    table["Link"] = table["listing_url"]
    table["What AI noticed"] = table["issue_summary"]
    output = table[
        [
            "Date",
            "Source",
            "Risk score (0-100)",
            "AI confidence",
            "Fields",
            "Status",
            "What AI noticed",
            "Link",
        ]
    ]
    st.dataframe(
        output,
        width="stretch",
        hide_index=True,
        column_config={
            "Link": st.column_config.LinkColumn("Link"),
            "What AI noticed": st.column_config.TextColumn(width="large"),
        },
    )


def _render_pending_and_confirmed(current_reviews: pd.DataFrame) -> None:
    if current_reviews.empty:
        _review_table(
            current_reviews,
            title="What the admin should review now",
            description="Queue of AI alerts without human feedback. Start with high-risk items.",
            empty_text="There are no AI alerts waiting for review.",
        )
        _review_table(
            current_reviews,
            title="Latest confirmed parser errors",
            description="This is a ready backlog for improving the deterministic parser.",
            empty_text="There are no confirmed parser errors yet.",
        )
        return

    pending = current_reviews[
        current_reviews["should_alert_admin"]
        & (current_reviews["feedback_status"] == AI_QA_FEEDBACK_PENDING)
    ].sort_values(["risk_score", "created_at"], ascending=[False, False])
    confirmed = current_reviews[
        current_reviews["feedback_status"] == AI_QA_FEEDBACK_PARSER_ERROR
    ].sort_values("created_at", ascending=False)

    _review_table(
        pending,
        title="What the admin should review now",
        description="Queue of AI alerts without human feedback. Start with high-risk items.",
        empty_text="There are no AI alerts waiting for review.",
    )

    _review_table(
        confirmed,
        title="Latest confirmed parser errors",
        description="This is a ready backlog for improving the deterministic parser.",
        empty_text="There are no confirmed parser errors yet.",
        limit=15,
    )


def _render_ai_qa_section(all_reviews: pd.DataFrame, current_reviews: pd.DataFrame) -> None:
    st.subheader("Is AI QA useful enough to keep operating?")
    st.caption(
        "AI QA is one bounded control inside the product: it reviews the parser's output "
        "and flags likely mistakes to an admin. It cannot parse listings, decide matches, "
        "or change what a renter sees — that stays deterministic (see the section above)."
    )
    _render_ai_qa_quality(current_reviews)
    st.markdown("---")
    _render_ai_qa_cost(current_reviews)
    st.markdown("---")
    _render_demo_fault_check()
    st.markdown("---")
    _render_field_quality(current_reviews)
    st.markdown("---")
    _render_versions(all_reviews)
    st.markdown("---")
    _render_pending_and_confirmed(current_reviews)


# ---------------------------------------------------------------------------
# Section 5 — evidence and gaps
# ---------------------------------------------------------------------------


def _render_evidence_and_gaps() -> None:
    st.subheader("What is proven and what remains unproven?")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Working now**")
        st.markdown(
            "- End-to-end filter → match → verified one-time delivery\n"
            "- Source-health monitoring with alert cooldown\n"
            "- Deterministic parsing, regression-tested on every change\n"
            "- AI QA instrumentation, budgets, and a non-mutation boundary\n"
            "- User-data deletion via `/delete`"
        )
    with col_b:
        st.markdown("**Not yet proven**")
        st.markdown(
            "- Live-source coverage and freshness (synthetic catalog only)\n"
            "- Real renter outcomes (time saved, application success)\n"
            "- Real-model AI QA usefulness, false-alarm rate, and cost\n"
            "- Usability with real users outside this demo"
        )

    st.markdown(
        "**Data stored:** Telegram user ID, the saved filter, and sent-listing history "
        "for deduplication — nothing else. No names, no message archive. `/delete` "
        "removes all of it after explicit confirmation, both from the bot and here."
    )
    st.caption(
        "This is a synthetic, local, single-operator prototype: no real scraping, no "
        "network geocoding, no production hosting. Read the case study for the product "
        "decisions and the next validation steps this would need before a real launch."
    )


def render_dashboard() -> None:
    st.set_page_config(
        page_title="FlatFeed · Product Operations",
        page_icon="",
        layout="wide",
    )
    init_db()

    st.title("FlatFeed product operations")
    st.caption(
        "Current state of the synthetic demo pipeline, from source refresh to verified "
        "delivery. AI QA is one control inside the product; it does not parse listings "
        "or decide matches."
    )

    coverage_counts = _load_active_ai_qa_coverage()
    all_reviews = _load_review_rows()
    current_reviews = _current_version(all_reviews)

    _render_metric_guide()
    _render_pipeline_readiness(coverage_counts)
    st.divider()
    _render_source_trust()
    st.divider()
    _render_parsing_accuracy()
    st.divider()
    _render_ai_qa_section(all_reviews, current_reviews)
    st.divider()
    _render_evidence_and_gaps()


if __name__ == "__main__":
    # `streamlit run` executes this file with __name__ == "__main__", so this
    # guard changes nothing for the app itself — it only makes the pure
    # helpers (fmt_share, etc.) safely importable from tests without
    # triggering a full Streamlit page render at import time.
    render_dashboard()
