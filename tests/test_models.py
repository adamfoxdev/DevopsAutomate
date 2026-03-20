"""Tests for data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models import (
    Epic,
    Feature,
    IntakeRequest,
    Priority,
    QATestCase,
    Task,
    UserStory,
    WorkItemHierarchy,
    WorkItemState,
)


class TestPriority:
    def test_values(self):
        assert Priority.CRITICAL == 1
        assert Priority.HIGH == 2
        assert Priority.MEDIUM == 3
        assert Priority.LOW == 4

    def test_from_int(self):
        assert Priority(2) is Priority.HIGH


class TestIntakeRequest:
    def test_defaults(self):
        req = IntakeRequest(title="Test", description="Some description")
        assert req.priority == Priority.MEDIUM
        assert req.tags == []
        assert req.requester == ""

    def test_custom_priority(self):
        req = IntakeRequest(title="T", description="D", priority=Priority.HIGH)
        assert req.priority == Priority.HIGH

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            IntakeRequest()


class TestTask:
    def test_defaults(self):
        task = Task(title="Write tests")
        assert task.task_type == "Development"
        assert task.estimated_hours == 0.0
        assert task.state == WorkItemState.NEW
        assert task.ado_id is None


class TestUserStory:
    def test_defaults(self):
        story = UserStory(title="As a user")
        assert story.story_points == 0
        assert story.tasks == []
        assert story.test_cases == []
        assert story.state == WorkItemState.NEW

    def test_with_tasks(self):
        task = Task(title="Implement endpoint")
        story = UserStory(title="Auth story", tasks=[task])
        assert len(story.tasks) == 1


class TestFeature:
    def test_defaults(self):
        f = Feature(title="Auth Feature")
        assert f.user_stories == []
        assert f.ado_id is None


class TestEpic:
    def test_defaults(self):
        epic = Epic(title="My Epic")
        assert epic.features == []
        assert epic.ado_id is None


class TestWorkItemHierarchy:
    def test_round_trip_json(self):
        intake = IntakeRequest(title="T", description="D")
        epic = Epic(
            title="E",
            description="Epic description",
            features=[
                Feature(
                    title="F",
                    description="Feature description",
                    user_stories=[
                        UserStory(
                            title="S",
                            description="As a user, I want x, so that y.",
                            acceptance_criteria="Given x\nWhen y\nThen z",
                            story_points=5,
                            tasks=[Task(title="T1")],
                            test_cases=[QATestCase(title="TC1")],
                        )
                    ],
                )
            ],
        )
        hierarchy = WorkItemHierarchy(intake=intake, epic=epic)
        json_str = hierarchy.model_dump_json()
        restored = WorkItemHierarchy.model_validate_json(json_str)
        assert restored.epic.title == "E"
        assert restored.epic.features[0].user_stories[0].story_points == 5
