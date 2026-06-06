from datetime import datetime

from pydantic import BaseModel, Field


class PreferenceUpsertRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    changed_by: str = Field(default="api", min_length=1)
    change_reason: str = Field(default="upsert", min_length=1)


class PreferenceDeleteRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    changed_by: str = Field(default="api", min_length=1)
    change_reason: str = Field(default="delete", min_length=1)


class PreferenceRollbackRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    target_version: int | None = Field(default=None, ge=1)
    changed_by: str = Field(default="api", min_length=1)
    change_reason: str = Field(default="rollback", min_length=1)


class PreferenceItem(BaseModel):
    user_id: str
    key: str
    value: str


class PreferenceHistoryItem(BaseModel):
    user_id: str
    key: str
    version: int
    change_type: str
    old_value: str | None
    new_value: str | None
    changed_by: str
    change_reason: str
    changed_at: datetime


class SessionSummaryItem(BaseModel):
    user_id: str
    session_id: str
    summary_text: str
    last_message_count: int
    updated_at: datetime
