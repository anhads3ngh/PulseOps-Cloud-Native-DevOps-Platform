"""The deliberately small public contract of our simulated publisher."""
from typing import Literal

from pydantic import BaseModel, Field


class NewJob(BaseModel):
    channel: Literal["linkedin", "instagram", "x"]
    content: str = Field(min_length=1, max_length=280)
    # Chaos engineering controls, NOT a real social-media publishing integration.
    failure_mode: Literal["none", "transient", "permanent"] = "none"


class Job(BaseModel):
    id: str
    channel: str
    content: str
    failure_mode: str
    status: str
    attempts: int
    created_at: str
    updated_at: str
    published_at: str | None = None
    last_error: str | None = None
