from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from flatfeed.config import PROJECT_ROOT, get_settings
from flatfeed.db.models import Base
from flatfeed.db.seed import seed_source_companies


def _ensure_sqlite_parent(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        return
    if url.database == ":memory:":
        return

    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_sqlite_parent(settings.database_url)

connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ensure_listing_columns() -> None:
    inspector = inspect(engine)
    if "listings" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("listings")}
    columns_to_add = {
        "image_url": "VARCHAR(1024)",
        "address": "VARCHAR(512)",
        "postal_code": "VARCHAR(5)",
        "district": "VARCHAR(120)",
        "floor": "VARCHAR(40)",
        "rooms": "FLOAT",
        "rent_kalt": "INTEGER",
        "rent_warm": "INTEGER",
        "latitude": "FLOAT",
        "longitude": "FLOAT",
        "transport_walk": "JSON",
        "source_active": "BOOLEAN",
        "first_seen_at": "DATETIME",
        "last_seen_at": "DATETIME",
        "last_checked_at": "DATETIME",
    }

    with engine.begin() as connection:
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE listings ADD COLUMN {column_name} {column_type}")
                )
        connection.execute(
            text(
                "UPDATE listings "
                "SET first_seen_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                "WHERE first_seen_at IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE listings "
                "SET source_active = CASE "
                "WHEN status = 'removed_from_source' THEN 0 "
                "ELSE 1 END "
                "WHERE source_active IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE listings "
                "SET last_seen_at = COALESCE(updated_at, first_seen_at, created_at, CURRENT_TIMESTAMP) "
                "WHERE last_seen_at IS NULL AND source_active = 1"
            )
        )
        connection.execute(
            text(
                "UPDATE listings "
                "SET last_checked_at = COALESCE(updated_at, first_seen_at, created_at, CURRENT_TIMESTAMP) "
                "WHERE last_checked_at IS NULL"
            )
        )


def _ensure_user_columns() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    columns_to_add = {
        "filter_updated_at": "DATETIME",
    }

    with engine.begin() as connection:
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                )
        connection.execute(
            text(
                "UPDATE users "
                "SET filter_updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) "
                "WHERE parsed_preferences IS NOT NULL AND filter_updated_at IS NULL"
            )
        )


def _ensure_ai_qa_schema() -> None:
    inspector = inspect(engine)
    if "ai_qa_reviews" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("ai_qa_reviews")}
    unique_constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("ai_qa_reviews")
    }
    indexes = [
        index.get("name")
        for index in inspector.get_indexes("ai_qa_reviews")
        if index.get("name")
    ]
    needs_rebuild = (
        "qa_prompt_version" not in existing_columns
        or "uq_ai_qa_reviews_listing_id" in unique_constraints
    )
    if not needs_rebuild:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE ai_qa_reviews RENAME TO ai_qa_reviews_old"))
        for index_name in indexes:
            connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
        Base.metadata.tables["ai_qa_reviews"].create(bind=connection)
        connection.execute(
            text(
                "INSERT INTO ai_qa_reviews ("
                "review_id, listing_id, listing_url, source_company, trigger_type, "
                "qa_prompt_version, raw_text_hash, parser_snapshot_hash, parser_snapshot, "
                "ai_result, risk_score, confidence, parser_result_correct, "
                "should_alert_admin, alert_sent, feedback_status, feedback_by, "
                "feedback_at, prompt_tokens, completion_tokens, total_cost_usd, created_at"
                ") "
                "SELECT "
                "review_id, listing_id, listing_url, source_company, trigger_type, "
                "'v1', raw_text_hash, parser_snapshot_hash, parser_snapshot, "
                "ai_result, risk_score, confidence, parser_result_correct, "
                "should_alert_admin, alert_sent, feedback_status, feedback_by, "
                "feedback_at, prompt_tokens, completion_tokens, total_cost_usd, created_at "
                "FROM ai_qa_reviews_old"
            )
        )
        connection.execute(text("DROP TABLE ai_qa_reviews_old"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_listing_columns()
    _ensure_user_columns()
    _ensure_ai_qa_schema()
    with get_session() as session:
        seed_source_companies(session)
