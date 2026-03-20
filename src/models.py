"""Pydantic data models for the Azure DevOps work item hierarchy."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Priority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class WorkItemState(str, Enum):
    NEW = "New"
    ACTIVE = "Active"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    REMOVED = "Removed"


class IntakeRequest(BaseModel):
    """Represents a raw intake request submitted by a stakeholder."""

    title: str = Field(..., description="Short title for the intake request")
    description: str = Field(..., description="Detailed description of the work requested")
    requester: str = Field(default="", description="Name or email of the person making the request")
    priority: Priority = Field(default=Priority.MEDIUM, description="Business priority")
    tags: list[str] = Field(default_factory=list, description="Optional tags/labels")
    area_path: str = Field(default="", description="Azure DevOps area path override")
    iteration_path: str = Field(default="", description="Azure DevOps iteration path override")


class QATestCase(BaseModel):
    """A single QA test case generated for a user story."""

    title: str
    preconditions: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    test_type: str = "Manual"  # Manual | Automated
    ado_id: Optional[int] = None


class Task(BaseModel):
    """A development task that belongs to a user story."""

    title: str
    description: str = ""
    task_type: str = "Development"  # Development | Testing | Documentation | DevOps
    estimated_hours: float = 0.0
    assigned_to: str = ""
    ado_id: Optional[int] = None
    state: WorkItemState = WorkItemState.NEW


class UserStory(BaseModel):
    """An Agile user story that belongs to a Feature."""

    title: str
    description: str = ""
    acceptance_criteria: str = ""
    story_points: int = 0
    priority: Priority = Priority.MEDIUM
    tasks: list[Task] = Field(default_factory=list)
    test_cases: list[QATestCase] = Field(default_factory=list)
    ado_id: Optional[int] = None
    state: WorkItemState = WorkItemState.NEW
    github_branch: str = ""


class Feature(BaseModel):
    """An Azure DevOps Feature that belongs to an Epic."""

    title: str
    description: str = ""
    acceptance_criteria: str = ""
    user_stories: list[UserStory] = Field(default_factory=list)
    ado_id: Optional[int] = None
    state: WorkItemState = WorkItemState.NEW


class Epic(BaseModel):
    """A top-level Azure DevOps Epic."""

    title: str
    description: str = ""
    features: list[Feature] = Field(default_factory=list)
    ado_id: Optional[int] = None
    state: WorkItemState = WorkItemState.NEW


class WorkItemHierarchy(BaseModel):
    """Complete work item hierarchy produced from a single intake request."""

    intake: IntakeRequest
    epic: Epic
    github_pr_url: str = ""
    github_branch: str = ""
