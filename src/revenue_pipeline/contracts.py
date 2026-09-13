from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Event(BaseModel):
    """A source version is a full replacement, including explicit soft deletion."""

    model_config = ConfigDict(extra="forbid", strict=True)
    source: Literal["crm", "contracts"]
    entity_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    version: int = Field(ge=1)
    effective_at: str
    deleted: bool = False
    opportunity_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    stage: Literal["open", "closed_won", "closed_lost"] | None = None
    amount_minor: int | None = Field(default=None, ge=0)
    currency: Literal["USD", "GBP", "EUR", "INR"] | None = None
    status: Literal["draft", "signed", "cancelled"] | None = None

    @model_validator(mode="after")
    def validate_source(self):
        timestamp = datetime.fromisoformat(self.effective_at)
        if timestamp.tzinfo is None:
            raise ValueError("effective_at must contain a timezone")
        if self.source == "crm":
            if self.entity_id != self.opportunity_id:
                raise ValueError("CRM entity_id must equal opportunity_id")
            if self.stage is None or self.amount_minor is None or self.currency is None:
                raise ValueError("CRM requires stage, integer minor-unit amount and currency")
            if self.status is not None:
                raise ValueError("CRM cannot contain contract status")
        elif self.status is None or any(
            value is not None for value in (self.stage, self.amount_minor, self.currency)
        ):
            raise ValueError("Contracts require status, not CRM financial fields")
        return self
