from __future__ import annotations

from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class UserPreferences(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location: Optional[List[str]] = Field(
        default=None,
        description="Preferred Berlin districts, neighborhoods, or addresses.",
    )
    wbs_type: Optional[str] = Field(
        default=None,
        description="WBS type such as WBS 100, WBS 140, WBS 160, WBS 180, WBS 220.",
    )
    max_rent: Optional[int] = Field(
        default=None,
        description="Maximum cold rent in EUR.",
    )
    rooms: Optional[float] = Field(
        default=None,
        description="Exact number of rooms. Value 5 means 5 rooms or more.",
    )

    @field_validator("location", mode="before")
    @classmethod
    def normalize_location(cls, value: object) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else None
        if isinstance(value, list):
            cleaned_values = [str(item).strip() for item in value if str(item).strip()]
            return cleaned_values or None
        return None

    @field_validator("wbs_type", mode="before")
    @classmethod
    def normalize_wbs_type(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class ListingConstraints(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    required_wbs: Optional[str] = None
    seniors_only: bool = False
    exchange_only_tauschwohnung: bool = Field(
        default=False,
        validation_alias=AliasChoices("exchange_only_tauschwohnung", "exchange_only"),
    )
    family_only: bool = False

    @property
    def exchange_only(self) -> bool:
        return self.exchange_only_tauschwohnung
