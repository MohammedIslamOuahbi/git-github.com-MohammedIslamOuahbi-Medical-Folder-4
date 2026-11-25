from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import SyncSchema


class WorkspaceDoctorRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceAssistantRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceBase(BaseModel):
    name: str
    campaign_id: int
    company_id: int
    branch_id: int
    drilling_site_id: int | None = None
    workspace_code: str
    start_date: date
    end_date: date
    status: str = "draft"
    is_locked: bool = False
    settings_json: dict | None = None


class WorkspaceCreate(WorkspaceBase):
    workspace_password: str = Field(min_length=4)


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    company_id: int | None = None
    branch_id: int | None = None
    drilling_site_id: int | None = None
    workspace_code: str | None = None
    workspace_password: str | None = Field(default=None, min_length=4)
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    is_locked: bool | None = None
    settings_json: dict | None = None


class WorkspaceRead(WorkspaceBase, SyncSchema):
    id: int
    campaign_name: str | None = None
    company_name: str | None = None
    branch_name: str | None = None
    drilling_site_name: str | None = None
    assigned_doctors: list[WorkspaceDoctorRead] = Field(default_factory=list)
    assigned_assistants: list[WorkspaceAssistantRead] = Field(default_factory=list)


class WorkspaceAccessRequest(BaseModel):
    access_code: str = Field(min_length=1)


class WorkspaceSessionRead(BaseModel):
    workspace: WorkspaceRead
    access_granted: bool = True
