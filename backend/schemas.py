"""Request/response models for the authenticated API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class SessionUser(BaseModel):
    id: str
    username: str
    full_name: str
    role_id: str
    role_title: str
    role_badge: str
    role_icon: str
    department: str
    workspace_id: str
    subtitle: str
    jurisdiction: str | None = None
    capabilities: list[str]
    is_demo: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: float
    user: SessionUser


class RoleInfo(BaseModel):
    id: str
    title: str
    department: str
    badge: str
    icon: str
    workspace_id: str
    subtitle: str
    capabilities: list[str]


class GrievanceCreate(BaseModel):
    region: str = Field(min_length=1, max_length=64)
    building_id: str = Field(min_length=1, max_length=128)
    category: str = Field(default="MUTATION_OR_SURVEY", max_length=64)
    subject: str = Field(min_length=3, max_length=200)
    narrative: str = Field(min_length=3, max_length=4000)


class GrievanceView(BaseModel):
    id: str
    user_id: str
    region: str
    building_id: str
    category: str
    subject: str
    narrative: str
    status: str
    created_at: float


class ReviewDecision(BaseModel):
    region: str = Field(min_length=1, max_length=64)
    building_id: str = Field(min_length=1, max_length=128)
    decision: str = Field(pattern="^(APPROVE|CORRECT|REJECT|UNRESOLVED)$")
    note: str = Field(default="", max_length=2000)


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
