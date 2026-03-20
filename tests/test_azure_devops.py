"""Tests for AzureDevOpsClient (mocked SDK)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.azure_devops import AzureDevOpsClient
from src.models import (
    Epic,
    Feature,
    IntakeRequest,
    QATestCase,
    Task,
    UserStory,
    WorkItemHierarchy,
    WorkItemState,
)


def _make_client(mock_wit=None) -> tuple[AzureDevOpsClient, MagicMock]:
    """Create an AzureDevOpsClient with a mock WIT client."""
    client = AzureDevOpsClient(
        org_url="https://dev.azure.com/testorg",
        pat="test-pat",
        project="TestProject",
    )
    if mock_wit is None:
        mock_wit = MagicMock()
    client._wit_client = mock_wit
    return client, mock_wit


class TestCreateEpic:
    def test_create_epic_returns_id(self):
        ado, mock_wit = _make_client()
        mock_result = MagicMock()
        mock_result.id = 100
        mock_wit.create_work_item.return_value = mock_result

        epic = Epic(title="My Epic", description="Some long epic description here.")
        result = ado.create_epic(epic)

        assert result.ado_id == 100
        mock_wit.create_work_item.assert_called_once()

    def test_create_epic_uses_correct_type(self):
        ado, mock_wit = _make_client()
        mock_wit.create_work_item.return_value = MagicMock(id=1)

        epic = Epic(title="E", description="Desc")
        ado.create_epic(epic)

        call_kwargs = mock_wit.create_work_item.call_args
        assert call_kwargs.kwargs.get("type") == "Epic" or call_kwargs[1].get("type") == "Epic"


class TestCreateFeature:
    def test_create_feature_links_to_parent(self):
        ado, mock_wit = _make_client()
        mock_wit.create_work_item.return_value = MagicMock(id=200)
        mock_wit.update_work_item.return_value = MagicMock()

        feature = Feature(title="Feature", description="A detailed feature description for testing.")
        result = ado.create_feature(feature, parent_epic_id=100)

        assert result.ado_id == 200
        # Should have called update_work_item to add parent link
        mock_wit.update_work_item.assert_called_once()


class TestCreateUserStory:
    def test_create_user_story(self):
        ado, mock_wit = _make_client()
        mock_wit.create_work_item.return_value = MagicMock(id=300)
        mock_wit.update_work_item.return_value = MagicMock()

        story = UserStory(
            title="Story",
            description="As a user, I want x, so that y.",
            story_points=5,
        )
        result = ado.create_user_story(story, parent_feature_id=200)
        assert result.ado_id == 300


class TestCreateTask:
    def test_create_task(self):
        ado, mock_wit = _make_client()
        mock_wit.create_work_item.return_value = MagicMock(id=400)
        mock_wit.update_work_item.return_value = MagicMock()

        task = Task(title="My Task", estimated_hours=3.0)
        result = ado.create_task(task, parent_story_id=300)
        assert result.ado_id == 400


class TestCreateHierarchy:
    def _build_hierarchy(self) -> WorkItemHierarchy:
        return WorkItemHierarchy(
            intake=IntakeRequest(title="I", description="D"),
            epic=Epic(
                title="Epic",
                description="Epic description long enough",
                features=[
                    Feature(
                        title="Feature",
                        description="Feature description long enough",
                        user_stories=[
                            UserStory(
                                title="Story",
                                description="As a user, I want x, so that y.",
                                tasks=[Task(title="T1"), Task(title="T2")],
                                test_cases=[QATestCase(title="TC1")],
                            )
                        ],
                    )
                ],
            ),
        )

    def test_create_hierarchy_calls_all_items(self):
        ado, mock_wit = _make_client()
        id_counter = iter(range(100, 200))
        mock_wit.create_work_item.side_effect = lambda **kw: MagicMock(id=next(id_counter))
        mock_wit.update_work_item.return_value = MagicMock()

        hierarchy = self._build_hierarchy()
        result = ado.create_hierarchy(hierarchy)

        # Epic + Feature + Story + 2 Tasks + 1 Test Case = 6 calls
        assert mock_wit.create_work_item.call_count == 6


class TestRenderTestSteps:
    def test_empty_steps(self):
        result = AzureDevOpsClient._render_test_steps([])
        assert result == ""

    def test_renders_table(self):
        result = AzureDevOpsClient._render_test_steps(["Step 1", "Step 2"])
        assert "<table" in result
        assert "Step 1" in result
        assert "Step 2" in result
