from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from flatfeed.db.models import SourceCompany


SOURCE_COMPANIES = (
    {
        "name": "FlatFeed Synthetic",
        "base_url": "https://demo.flatfeed.local",
        "parser_status": "implemented",
    },
)


def seed_source_companies(session: Session) -> None:
    for company_data in SOURCE_COMPANIES:
        existing = session.scalar(
            select(SourceCompany).where(SourceCompany.name == company_data["name"])
        )
        if existing is None:
            session.add(SourceCompany(**company_data))
        else:
            existing.base_url = company_data["base_url"]
            existing.parser_status = company_data["parser_status"]
