from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from flatfeed.db.models import IngestionRun
from flatfeed.db.session import SessionLocal


INGESTION_STATUS_SUCCESS = "success"
INGESTION_STATUS_PARTIAL_SUCCESS = "partial_success"
INGESTION_STATUS_FAILED = "failed"
DEFAULT_SOURCE_COMPANY = "FlatFeed Synthetic"
NON_SUCCESS_STATUSES = {INGESTION_STATUS_PARTIAL_SUCCESS, INGESTION_STATUS_FAILED}


@dataclass(frozen=True)
class IngestionAlertCandidate:
    run_id: int
    trigger_type: str
    consecutive_failures: int
    error_type: Optional[str]
    error_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]
    last_success_at: Optional[datetime]


@dataclass(frozen=True)
class IngestionHealthSummary:
    latest_status: Optional[str]
    latest_trigger_type: Optional[str]
    latest_started_at: Optional[datetime]
    latest_finished_at: Optional[datetime]
    consecutive_failures: int
    last_success_at: Optional[datetime]
    last_error_type: Optional[str]
    last_error_message: Optional[str]
    runs_24h: int
    failures_24h: int


def _truncate(value: str, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def record_ingestion_success(
    *,
    trigger_type: str,
    listings_found: int = 0,
    saved_count: int = 0,
    removed_count: int = 0,
    parsed_count: int = 0,
    transport_count: int = 0,
    started_at: Optional[datetime] = None,
    source_company: str = DEFAULT_SOURCE_COMPANY,
    status: str = INGESTION_STATUS_SUCCESS,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> int:
    started = started_at or datetime.utcnow()
    finished = datetime.utcnow()
    run = IngestionRun(
        source_company=source_company,
        trigger_type=trigger_type,
        status=status,
        listings_found=listings_found,
        saved_count=saved_count,
        removed_count=removed_count,
        parsed_count=parsed_count,
        transport_count=transport_count,
        error_type=error_type,
        error_message=_truncate(error_message or "") if error_message else None,
        started_at=started,
        finished_at=finished,
        duration_seconds=(finished - started).total_seconds(),
    )
    with SessionLocal() as session:
        session.add(run)
        session.commit()
        return run.run_id


def record_ingestion_failure(
    *,
    trigger_type: str,
    error: BaseException,
    started_at: Optional[datetime] = None,
    source_company: str = DEFAULT_SOURCE_COMPANY,
) -> int:
    started = started_at or datetime.utcnow()
    finished = datetime.utcnow()
    message = str(error) or repr(error)
    run = IngestionRun(
        source_company=source_company,
        trigger_type=trigger_type,
        status=INGESTION_STATUS_FAILED,
        error_type=type(error).__name__,
        error_message=_truncate(message),
        started_at=started,
        finished_at=finished,
        duration_seconds=(finished - started).total_seconds(),
    )
    with SessionLocal() as session:
        session.add(run)
        session.commit()
        return run.run_id


def get_consecutive_ingestion_failures(
    *,
    source_company: str = DEFAULT_SOURCE_COMPANY,
    trigger_type: Optional[str] = None,
    lookback: int = 100,
) -> int:
    with SessionLocal() as session:
        statement = (
            select(IngestionRun)
            .where(IngestionRun.source_company == source_company)
            .order_by(IngestionRun.started_at.desc(), IngestionRun.run_id.desc())
            .limit(lookback)
        )
        if trigger_type is not None:
            statement = statement.where(IngestionRun.trigger_type == trigger_type)
        runs = list(
            session.scalars(
                statement
            )
        )

    failures = 0
    for run in runs:
        if run.status == INGESTION_STATUS_SUCCESS:
            break
        failures += 1
    return failures


def get_ingestion_alert_candidate(
    *,
    failure_threshold: int,
    cooldown_seconds: int,
    source_company: str = DEFAULT_SOURCE_COMPANY,
    trigger_type: Optional[str] = None,
) -> Optional[IngestionAlertCandidate]:
    threshold = max(failure_threshold, 1)
    cooldown = max(cooldown_seconds, 0)
    now = datetime.utcnow()

    with SessionLocal() as session:
        recent_statement = (
            select(IngestionRun)
            .where(IngestionRun.source_company == source_company)
            .order_by(IngestionRun.started_at.desc(), IngestionRun.run_id.desc())
            .limit(100)
        )
        if trigger_type is not None:
            recent_statement = recent_statement.where(IngestionRun.trigger_type == trigger_type)
        recent_runs = list(
            session.scalars(
                recent_statement
            )
        )
        if not recent_runs or recent_runs[0].status == INGESTION_STATUS_SUCCESS:
            return None

        consecutive_failures = 0
        for run in recent_runs:
            if run.status == INGESTION_STATUS_SUCCESS:
                break
            consecutive_failures += 1

        latest_problem_run = recent_runs[0]
        if consecutive_failures < threshold or latest_problem_run.alert_sent:
            return None

        alerted_statement = (
            select(IngestionRun)
            .where(IngestionRun.source_company == source_company)
            .where(IngestionRun.status.in_(NON_SUCCESS_STATUSES))
            .where(IngestionRun.alert_sent.is_(True))
            .order_by(IngestionRun.finished_at.desc(), IngestionRun.run_id.desc())
            .limit(1)
        )
        if trigger_type is not None:
            alerted_statement = alerted_statement.where(IngestionRun.trigger_type == trigger_type)
        last_alerted_run = session.scalar(alerted_statement)
        if (
            last_alerted_run is not None
            and last_alerted_run.finished_at is not None
            and now - last_alerted_run.finished_at < timedelta(seconds=cooldown)
        ):
            return None

        success_statement = (
            select(IngestionRun.finished_at)
            .where(IngestionRun.source_company == source_company)
            .where(IngestionRun.status == INGESTION_STATUS_SUCCESS)
            .order_by(IngestionRun.finished_at.desc(), IngestionRun.run_id.desc())
            .limit(1)
        )
        if trigger_type is not None:
            success_statement = success_statement.where(IngestionRun.trigger_type == trigger_type)
        last_success_at = session.scalar(success_statement)

        return IngestionAlertCandidate(
            run_id=latest_problem_run.run_id,
            trigger_type=latest_problem_run.trigger_type,
            consecutive_failures=consecutive_failures,
            error_type=latest_problem_run.error_type,
            error_message=latest_problem_run.error_message,
            started_at=latest_problem_run.started_at,
            finished_at=latest_problem_run.finished_at,
            last_success_at=last_success_at,
        )


def mark_ingestion_alert_sent(run_id: int) -> None:
    with SessionLocal() as session:
        run = session.get(IngestionRun, run_id)
        if run is None:
            return
        run.alert_sent = True
        session.commit()


def load_ingestion_health_summary(
    *,
    source_company: str = DEFAULT_SOURCE_COMPANY,
) -> IngestionHealthSummary:
    since = datetime.utcnow() - timedelta(hours=24)
    with SessionLocal() as session:
        latest_run = session.scalar(
            select(IngestionRun)
            .where(IngestionRun.source_company == source_company)
            .order_by(IngestionRun.started_at.desc(), IngestionRun.run_id.desc())
            .limit(1)
        )
        last_success_at = session.scalar(
            select(IngestionRun.finished_at)
            .where(IngestionRun.source_company == source_company)
            .where(IngestionRun.status == INGESTION_STATUS_SUCCESS)
            .order_by(IngestionRun.finished_at.desc(), IngestionRun.run_id.desc())
            .limit(1)
        )
        runs_24h = len(
            list(
                session.scalars(
                    select(IngestionRun.run_id)
                    .where(IngestionRun.source_company == source_company)
                    .where(IngestionRun.started_at >= since)
                )
            )
        )
        failures_24h = len(
            list(
                session.scalars(
                    select(IngestionRun.run_id)
                    .where(IngestionRun.source_company == source_company)
                    .where(IngestionRun.status.in_(NON_SUCCESS_STATUSES))
                    .where(IngestionRun.started_at >= since)
                )
            )
        )

    return IngestionHealthSummary(
        latest_status=latest_run.status if latest_run is not None else None,
        latest_trigger_type=latest_run.trigger_type if latest_run is not None else None,
        latest_started_at=latest_run.started_at if latest_run is not None else None,
        latest_finished_at=latest_run.finished_at if latest_run is not None else None,
        consecutive_failures=get_consecutive_ingestion_failures(
            source_company=source_company,
        ),
        last_success_at=last_success_at,
        last_error_type=latest_run.error_type if latest_run is not None else None,
        last_error_message=latest_run.error_message if latest_run is not None else None,
        runs_24h=runs_24h,
        failures_24h=failures_24h,
    )
