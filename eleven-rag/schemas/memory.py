from pydantic import BaseModel, Field


class PreferenceUpsertRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class PreferenceItem(BaseModel):
    user_id: str
    key: str
    value: str
