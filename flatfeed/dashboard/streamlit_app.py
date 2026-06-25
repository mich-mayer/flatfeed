from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flatfeed.ai_qa import (  # noqa: E402
    AI_QA_FEEDBACK_PARSER_CORRECT,
    AI_QA_FEEDBACK_PARSER_ERROR,
    AI_QA_FEEDBACK_PENDING,
    AI_QA_FEEDBACK_UNSURE,
    AI_QA_DEMO_FAULT_TYPES,
    CURRENT_AI_QA_PROMPT_VERSION,
    get_ai_qa_status,
    run_ai_qa_demo_check_for_listing,
)
from flatfeed.config import get_settings  # noqa: E402
from flatfeed.db.models import AIQAReview, Listing  # noqa: E402
from flatfeed.db.session import SessionLocal, init_db  # noqa: E402
from flatfeed.ingestion import ENABLED_SOURCE_COMPANIES, REMOVED_STATUS  # noqa: E402
from flatfeed.monitoring import (  # noqa: E402
    INGESTION_STATUS_PARTIAL_SUCCESS,
    load_ingestion_health_summary,
)


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


def _money(value: Optional[float]) -> str:
    return f"${float(value or 0):,.4f}"


def _price_per_1m(value: Optional[float]) -> str:
    return f"${float(value or 0):,.2f} / 1M"


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


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
            ).order_by(AIQAReview.created_at.desc(), AIQAReview.review_id.desc())
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
            - **AI risk signals** are cases where the model believes the parser may have made a material mistake worth admin review.
            - **Useful signal rate** shows how often reviewed AI signals became confirmed parser errors.
            - **False alarm rate** shows how often AI distracted the admin without a real parser error.
            - **Cost per confirmed error** shows model cost per human-confirmed parser error.
            """
        )


def _render_health(coverage_counts: Dict[str, int]) -> None:
    summaries = {
        source_company: load_ingestion_health_summary(source_company=source_company)
        for source_company in ENABLED_SOURCE_COMPANIES
    }
    active_count = coverage_counts["active"]
    reviewed_active_count = coverage_counts["reviewed_active"]
    coverage = reviewed_active_count / active_count if active_count else 0.0
    unreviewed = coverage_counts["unreviewed_active"]

    st.subheader("Is AI QA running well now?")
    statuses = [summary.latest_status for summary in summaries.values()]
    if statuses and all(status == "success" for status in statuses):
        st.success("The synthetic catalog is refreshing successfully.")
    elif any(status in {INGESTION_STATUS_PARTIAL_SUCCESS, "failed"} for status in statuses):
        st.warning("The synthetic catalog has a partial or failed refresh.")
    elif all(status is None for status in statuses):
        st.info("The synthetic catalog has not been refreshed yet.")
    else:
        st.info("The synthetic catalog still has incomplete refresh history.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Active listings",
        f"{active_count:,}",
        help="How many listings are currently active in the bot database.",
    )
    c2.metric(
        "AI reviewed",
        f"{reviewed_active_count:,} of {active_count:,}",
        help="How many active listings have been reviewed by the current AI QA version.",
    )
    c3.metric(
        "Active catalog coverage",
        _percent(coverage),
        help="Share of active listings with an AI QA report from the current version.",
    )
    c4.metric(
        "Still to review",
        f"{unreviewed:,}",
        help="Active listings without a report from the current AI QA version.",
    )

    health_rows = pd.DataFrame(
        [
            {
                "Catalog": source_company,
                "Status": summary.latest_status or "no data",
                "Latest success": _format_time(summary.last_success_at),
                "Consecutive failures": summary.consecutive_failures,
            }
            for source_company, summary in summaries.items()
        ]
    )
    st.dataframe(health_rows, width="stretch", hide_index=True)
    st.caption(f"Current AI QA version: {CURRENT_AI_QA_PROMPT_VERSION}.")


def _render_quality(current_reviews: pd.DataFrame) -> None:
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
    unsure = int(
        (current_reviews["feedback_status"] == AI_QA_FEEDBACK_UNSURE).sum()
    ) if not current_reviews.empty else 0
    pending_alerts = int(
        (
            current_reviews["should_alert_admin"]
            & (current_reviews["feedback_status"] == AI_QA_FEEDBACK_PENDING)
        ).sum()
    ) if not current_reviews.empty else 0
    precision = confirmed / len(decisive) if len(decisive) else 0.0
    false_alarm_rate = false_alarms / len(decisive) if len(decisive) else 0.0
    useful_finding_rate = confirmed / total_checks if total_checks else 0.0

    st.subheader("How useful is AI QA?")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Total AI checks",
        f"{total_checks:,}",
        help="How many listings were checked by the current AI QA version.",
    )
    c2.metric(
        "AI risk signals",
        f"{alerts:,}",
        help="How often AI decided the parser may have erred enough to show an admin.",
    )
    c3.metric(
        "Human reviewed",
        f"{len(reviewed):,}",
        help="How many AI reports received admin feedback.",
    )
    c4.metric(
        "Pending decision",
        f"{pending_alerts:,}",
        help="How many risky AI reports are still neither confirmed nor rejected.",
    )

    c5, c6, c7, c8 = st.columns(4)
    c5.metric(
        "Real parser errors",
        f"{confirmed:,}",
        help="How many AI alerts the admin confirmed as real parsing errors.",
    )
    c6.metric(
        "False alarms",
        f"{false_alarms:,}",
        help="How many AI alerts the admin marked as correct parser behavior.",
    )
    c7.metric(
        "Useful signal rate",
        _percent(precision) if len(decisive) else _no_data(),
        help="Share of confirmed errors among reports where the admin gave a clear parser-error or false-alarm decision.",
    )
    c8.metric(
        "False alarm rate",
        _percent(false_alarm_rate) if len(decisive) else _no_data(),
        help="Share of false alarms among reports where the admin gave a clear decision.",
    )

    st.caption(
        "A useful finding is an AI report that the admin confirmed as a real parser error. "
        f"Current useful findings: {confirmed:,} out of {total_checks:,} checks "
        f"({_percent(useful_finding_rate)})."
    )


def _render_costs(current_reviews: pd.DataFrame) -> None:
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

    st.subheader("How much does AI QA cost?")
    c0, c1, c2, c3, c4 = st.columns(5)
    c0.metric(
        "OpenAI model",
        settings.ai_qa_model,
        help="AI QA model when AI_QA_PROVIDER=openai. In mock mode, actual check cost is zero.",
    )
    c1.metric(
        "Spent on current version",
        _money(total_cost),
        help="Total OpenAI cost for AI QA reviews in the current version.",
    )
    c2.metric(
        "Cost per check",
        _money(cost_per_check),
        help="Average cost to check one listing.",
    )
    c3.metric(
        "Cost per alert",
        _money(cost_per_alert),
        help="Average cost per case where AI sent a report to the admin.",
    )
    c4.metric(
        "Cost per confirmed error",
        _money(cost_per_confirmed) if cost_per_confirmed is not None else _no_data(),
        help="Cost of one human-confirmed parser error. Appears after the first confirmed error.",
    )
    st.caption(
        "OpenAI cost calculation uses configured prices: "
        f"input {_price_per_1m(settings.openai_input_price_per_1m)}, "
        f"output {_price_per_1m(settings.openai_output_price_per_1m)}. "
        "Default updated for GPT-5.4 mini OpenAI API pricing, verified 2026-06-23."
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
    st.subheader("Demo: parser made a mistake, AI checked it")
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

    if not st.button("Run demo AI QA"):
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
    c1.metric("AI risk", f"{int(result.ai_result.get('risk_score') or 0)}%")
    c2.metric("Alert", "yes" if result.ai_result.get("should_alert_admin") else "no")
    c3.metric("Confidence", f"{float(result.ai_result.get('confidence') or 0.0):.2f}")
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
            "Real errors": 0,
            "False alarms": 0,
            "Average AI risk": 0.0,
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
                stats["Real errors"] += 1
            elif row.feedback_status == AI_QA_FEEDBACK_PARSER_CORRECT:
                stats["False alarms"] += 1

    rows = []
    for field, stats in field_stats.items():
        alerts = int(stats["AI risk signals"])
        confirmed = int(stats["Real errors"])
        false_alarms = int(stats["False alarms"])
        decisive = confirmed + false_alarms
        rows.append(
            {
                "Field": field,
                "AI risk signals": alerts,
                "Real errors": confirmed,
                "False alarms": false_alarms,
                "Useful signal rate": _percent(confirmed / decisive) if decisive else _no_data(),
                "Average AI risk": round(stats["_risk_total"] / alerts, 1) if alerts else 0.0,
            }
        )

    st.subheader("Where the parser is most at risk")
    st.caption(
        "This table shows which fields AI most often flags as risky, "
        "and where a human has already confirmed real errors."
    )
    if not rows:
        st.info("There are no field-level AI alerts yet.")
        return
    frame = pd.DataFrame(rows).sort_values(
        ["Real errors", "AI risk signals"], ascending=False
    )
    st.dataframe(frame, width="stretch", hide_index=True)


def _render_versions(all_reviews: pd.DataFrame) -> None:
    st.subheader("How AI QA quality changed by version")
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
                "Real errors": confirmed,
                "False alarms": false_alarms,
                "Useful signal rate": _percent(confirmed / len(decisive)) if len(decisive) else _no_data(),
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
    st.subheader(title)
    st.caption(description)
    if reviews.empty:
        st.info(empty_text)
        return

    table = reviews.head(limit).copy()
    table["Fields"] = table["issue_fields"].map(lambda values: ", ".join(values))
    table["AI risk"] = table["risk_score"].map(lambda value: f"{int(value)}%")
    table["AI confidence"] = table["confidence"].map(lambda value: f"{float(value):.2f}")
    table["Date"] = table["created_at_label"]
    table["Status"] = table["feedback_label"]
    table["Catalog"] = table["source_company"]
    table["Link"] = table["listing_url"]
    table["What AI noticed"] = table["issue_summary"]
    output = table[
        [
            "Date",
            "Catalog",
            "AI risk",
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


def render_dashboard() -> None:
    st.set_page_config(
        page_title="FlatFeed · AI QA",
        page_icon="",
        layout="wide",
    )
    init_db()

    st.title("FlatFeed parser AI QA")
    st.caption(
        "The dashboard shows how much AI QA helps find real parser errors, "
        "how much of the active catalog it covers, and how much model usage costs."
    )

    coverage_counts = _load_active_ai_qa_coverage()
    all_reviews = _load_review_rows()
    current_reviews = _current_version(all_reviews)

    _render_metric_guide()
    _render_health(coverage_counts)
    st.divider()
    _render_quality(current_reviews)
    st.divider()
    _render_costs(current_reviews)
    st.divider()
    _render_demo_fault_check()
    st.divider()
    _render_field_quality(current_reviews)
    st.divider()
    _render_versions(all_reviews)
    st.divider()
    _render_pending_and_confirmed(current_reviews)


render_dashboard()
