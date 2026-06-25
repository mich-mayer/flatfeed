from __future__ import annotations

import importlib
from typing import Dict, Tuple

from flatfeed.ingestion.base import SourceAdapter


_SOURCE_ADAPTERS: Dict[str, SourceAdapter] = {}
ENABLED_SOURCE_COMPANIES = (
    "FlatFeed Synthetic",
)


def _ensure_enabled_adapters_registered() -> None:
    missing = [
        source_company
        for source_company in ENABLED_SOURCE_COMPANIES
        if source_company not in _SOURCE_ADAPTERS
    ]
    if missing:
        importlib.import_module("flatfeed.ingestion.synthetic")


def register_source_adapter(adapter: SourceAdapter) -> None:
    source_company = adapter.source_company.strip()
    if not source_company:
        raise ValueError("Source adapter company name cannot be empty.")
    if source_company in _SOURCE_ADAPTERS:
        raise ValueError(f"Source adapter already registered: {source_company}")
    _SOURCE_ADAPTERS[source_company] = adapter


def get_source_adapter(source_company: str) -> SourceAdapter:
    _ensure_enabled_adapters_registered()
    try:
        return _SOURCE_ADAPTERS[source_company]
    except KeyError as exc:
        raise KeyError(f"No source adapter registered for {source_company}") from exc


def list_source_adapters() -> Tuple[SourceAdapter, ...]:
    _ensure_enabled_adapters_registered()
    return tuple(_SOURCE_ADAPTERS[name] for name in sorted(_SOURCE_ADAPTERS))
