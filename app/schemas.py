from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)


class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    created_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    sub: Optional[str] = None


class ReportCreate(BaseModel):
    location: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=20, max_length=20000)


class ReportOut(BaseModel):
    id: int
    reporter: str
    location: str
    description: str
    status: str
    created_at: datetime


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_id: int
    sha256: str
    size_bytes: int
    content_type: str
    original_filename: str
    uploaded_by: int
    created_at: datetime
