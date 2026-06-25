import importlib

from flatfeed.ingestion.base import (
    REMOVED_STATUS,
    UNPARSED_STATUS,
    SourceAdapter,
    SourceIngestionResult,
    SourceListing,
    merge_source_listing,
)
from flatfeed.ingestion.registry import (
    ENABLED_SOURCE_COMPANIES,
    get_source_adapter,
    list_source_adapters,
)


def __getattr__(name: str):
    if name in {
        "SYNTHETIC_ADAPTER",
        "SYNTHETIC_SOURCE_COMPANY",
        "collect_synthetic_listings",
        "sync_synthetic_listings",
    }:
        synthetic = importlib.import_module("flatfeed.ingestion.synthetic")
        return getattr(synthetic, name)
    raise AttributeError(name)

__all__ = [
    "ENABLED_SOURCE_COMPANIES",
    "REMOVED_STATUS",
    "SYNTHETIC_ADAPTER",
    "SYNTHETIC_SOURCE_COMPANY",
    "UNPARSED_STATUS",
    "SourceAdapter",
    "SourceIngestionResult",
    "SourceListing",
    "collect_synthetic_listings",
    "get_source_adapter",
    "list_source_adapters",
    "merge_source_listing",
    "sync_synthetic_listings",
]
