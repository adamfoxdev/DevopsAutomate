"""Tests for AIAssistant (mocked OpenAI client)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ai_assistant import AIAssistant
from src.models import IntakeRequest, Priority, WorkItemHierarchy


_SAMPLE_RESPONSE = {
    "epic": {
        "title": "User Authentication",
        "description": "This epic covers all aspects of user authentication including login, registration, and password reset.",
        "features": [
            {
                "title": "User Login",
                "description": "Allow users to log in with their email and password.",
                "acceptance_criteria": "Given I am on the login page\nWhen I enter valid credentials\nThen I should see the dashboard",
                "user_stories": [
                    {
                        "title": "Login with email and password",
                        "description": "As a registered user, I want to log in with my email, so that I can access my account.",
                        "acceptance_criteria": "Given I have a valid account\nWhen I enter my credentials\nThen I am redirected to the dashboard",
                        "story_points": 3,
                        "priority": 2,
                        "tasks": [
                            {
                                "title": "Implement login API",
                                "description": "Create POST /auth/login endpoint",
                                "task_type": "Development",
                                "estimated_hours": 4.0,
                            },
                            {
                                "title": "Write unit tests",
                                "description": "Write tests for the login endpoint",
                                "task_type": "Testing",
                                "estimated_hours": 2.0,
                            },
                            {
                                "title": "Code review",
                                "description": "PR code review",
                                "task_type": "Code Review",
                                "estimated_hours": 1.0,
                            },
                        ],
                        "test_cases": [
                            {
                                "title": "Successful login",
                                "preconditions": "User exists in the system",
                                "steps": ["Navigate to login page", "Enter valid email and password", "Click login"],
                                "expected_result": "User is redirected to dashboard",
                                "test_type": "Manual",
                            },
                            {
                                "title": "Invalid credentials",
                                "preconditions": "User exists",
                                "steps": ["Navigate to login page", "Enter wrong password", "Click login"],
                                "expected_result": "Error message is displayed",
                                "test_type": "Manual",
                            },
                        ],
                    }
                ],
            }
        ],
    }
}


def _make_ai(mock_client) -> AIAssistant:
    """Create an AIAssistant with a mock OpenAI client."""
    with patch("openai.OpenAI", return_value=mock_client):
        ai = AIAssistant(api_key="test-key")
    ai.client = mock_client
    return ai


class TestAIAssistantDecompose:
    def _make_mock_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(_SAMPLE_RESPONSE)
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_decompose_returns_hierarchy(self):
        mock_client = self._make_mock_client()
        ai = _make_ai(mock_client)
        intake = IntakeRequest(title="Auth System", description="Build the authentication system")
        hierarchy = ai.decompose(intake)

        assert isinstance(hierarchy, WorkItemHierarchy)
        assert hierarchy.epic.title == "User Authentication"
        assert len(hierarchy.epic.features) == 1

    def test_decompose_features_structure(self):
        mock_client = self._make_mock_client()
        ai = _make_ai(mock_client)
        intake = IntakeRequest(title="Auth System", description="Build the authentication system")
        hierarchy = ai.decompose(intake)

        feature = hierarchy.epic.features[0]
        assert feature.title == "User Login"
        assert len(feature.user_stories) == 1

    def test_decompose_user_story_structure(self):
        mock_client = self._make_mock_client()
        ai = _make_ai(mock_client)
        intake = IntakeRequest(title="Auth System", description="Build the authentication system")
        hierarchy = ai.decompose(intake)

        story = hierarchy.epic.features[0].user_stories[0]
        assert story.title == "Login with email and password"
        assert story.story_points == 3
        assert story.priority == Priority.HIGH
        assert len(story.tasks) == 3
        assert len(story.test_cases) == 2

    def test_decompose_tasks(self):
        mock_client = self._make_mock_client()
        ai = _make_ai(mock_client)
        intake = IntakeRequest(title="Auth System", description="Build the authentication system")
        hierarchy = ai.decompose(intake)

        tasks = hierarchy.epic.features[0].user_stories[0].tasks
        task_types = {t.task_type for t in tasks}
        assert "Development" in task_types
        assert "Testing" in task_types

    def test_decompose_test_cases(self):
        mock_client = self._make_mock_client()
        ai = _make_ai(mock_client)
        intake = IntakeRequest(title="Auth System", description="Build the authentication system")
        hierarchy = ai.decompose(intake)

        tcs = hierarchy.epic.features[0].user_stories[0].test_cases
        assert tcs[0].title == "Successful login"
        assert tcs[0].steps[0] == "Navigate to login page"


class TestAIAssistantParsers:
    def test_parse_task(self):
        data = {"title": "Implement API", "task_type": "Development", "estimated_hours": 4.0}
        task = AIAssistant._parse_task(data)
        assert task.title == "Implement API"
        assert task.estimated_hours == 4.0

    def test_parse_test_case(self):
        data = {
            "title": "Happy path",
            "steps": ["Step 1"],
            "expected_result": "Success",
            "test_type": "Automated",
        }
        tc = AIAssistant._parse_test_case(data)
        assert tc.test_type == "Automated"

    def test_parse_user_story_defaults(self):
        data = {"title": "Story with no tasks"}
        story = AIAssistant._parse_user_story(data)
        assert story.tasks == []
        assert story.test_cases == []
