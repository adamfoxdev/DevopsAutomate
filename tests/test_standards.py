"""Tests for StandardsEnforcer."""

from __future__ import annotations

import pytest

from src.models import Epic, Feature, Priority, QATestCase, Task, UserStory
from src.standards import StandardsEnforcer


@pytest.fixture
def enforcer():
    return StandardsEnforcer()


class TestValidateEpic:
    def test_valid_epic(self, enforcer):
        epic = Epic(title="User Management", description="This epic covers all user management functionality.")
        assert enforcer.validate_epic(epic) == []

    def test_empty_title(self, enforcer):
        epic = Epic(title="", description="Some long enough description here.")
        violations = enforcer.validate_epic(epic)
        assert any("title" in v.lower() for v in violations)

    def test_short_description(self, enforcer):
        epic = Epic(title="Epic", description="Short")
        violations = enforcer.validate_epic(epic)
        assert any("description" in v.lower() for v in violations)


class TestValidateFeature:
    def test_valid_feature(self, enforcer):
        f = Feature(title="Login Flow", description="Covers the complete login flow for all user types.")
        assert enforcer.validate_feature(f) == []

    def test_empty_title(self, enforcer):
        f = Feature(title="", description="Long enough feature description here.")
        violations = enforcer.validate_feature(f)
        assert any("title" in v.lower() for v in violations)


class TestValidateUserStory:
    def _valid_story(self) -> UserStory:
        return UserStory(
            title="Log in with email",
            description="As a user, I want to log in with email, so that I can access my account.",
            acceptance_criteria="Given I am on the login page\nWhen I enter valid credentials\nThen I should be logged in",
            story_points=3,
            test_cases=[
                QATestCase(title="Happy path login"),
                QATestCase(title="Invalid credentials"),
            ],
        )

    def test_valid_story(self, enforcer):
        story = self._valid_story()
        assert enforcer.validate_user_story(story) == []

    def test_missing_as_a(self, enforcer):
        story = self._valid_story()
        story.description = "User can log in with email."
        violations = enforcer.validate_user_story(story)
        assert any("As a" in v for v in violations)

    def test_non_gherkin_ac(self, enforcer):
        story = self._valid_story()
        story.acceptance_criteria = "The user should be able to log in."
        violations = enforcer.validate_user_story(story)
        assert any("Gherkin" in v or "gherkin" in v.lower() for v in violations)

    def test_exceeds_max_story_points(self, enforcer):
        story = self._valid_story()
        story.story_points = 21
        violations = enforcer.validate_user_story(story)
        assert any("story points" in v.lower() for v in violations)

    def test_insufficient_test_cases(self, enforcer):
        story = self._valid_story()
        story.test_cases = [QATestCase(title="Only one")]
        violations = enforcer.validate_user_story(story)
        assert any("test case" in v.lower() for v in violations)


class TestValidateTask:
    def test_valid_task(self, enforcer):
        task = Task(title="Implement login API", task_type="Development")
        assert enforcer.validate_task(task) == []

    def test_empty_title(self, enforcer):
        task = Task(title="", task_type="Development")
        violations = enforcer.validate_task(task)
        assert any("title" in v.lower() for v in violations)

    def test_invalid_task_type(self, enforcer):
        task = Task(title="Some task", task_type="InvalidType")
        violations = enforcer.validate_task(task)
        assert any("task type" in v.lower() for v in violations)


class TestBranchName:
    def test_valid_branch(self, enforcer):
        assert enforcer.validate_branch_name("feature/123-my-feature") == []

    def test_invalid_prefix(self, enforcer):
        violations = enforcer.validate_branch_name("random/123-stuff")
        assert violations  # "random" is not in allowed types

    def test_make_branch_name(self, enforcer):
        name = enforcer.make_branch_name(ado_id=42, title="User Authentication Flow")
        assert name.startswith("feature/")
        assert "42" in name
        assert "user-authentication-flow" in name

    def test_make_branch_name_slug_truncated(self, enforcer):
        long_title = "A" * 100
        name = enforcer.make_branch_name(ado_id=1, title=long_title)
        slug = name.split("/")[1]
        # Remove "1-" prefix before checking length
        assert len(slug) <= 53  # "1-" + 50 chars


class TestDefinitionOfDone:
    def test_returns_list(self, enforcer):
        dod = enforcer.get_definition_of_done()
        assert isinstance(dod, list)
        assert len(dod) > 0

    def test_append_dod(self, enforcer):
        story = UserStory(title="Story", description="As a user, I want x, so that y.")
        story = enforcer.append_definition_of_done(story)
        assert "Definition of Done" in story.description
        assert "- [ ]" in story.description
