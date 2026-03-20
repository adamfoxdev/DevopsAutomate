"""Tests for GitHubClient (mocked PyGithub)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.github_integration import GitHubClient
from src.models import QATestCase, UserStory
from src.standards import StandardsEnforcer


def _make_client() -> tuple[GitHubClient, MagicMock]:
    """Return a GitHubClient with a mocked repo."""
    mock_repo = MagicMock()
    client = GitHubClient(token="test-token", repo_name="owner/repo")
    client._repo = mock_repo
    return client, mock_repo


class TestCreateBranch:
    def test_create_branch_returns_name(self):
        gh, mock_repo = _make_client()
        mock_repo.get_branch.return_value = MagicMock(commit=MagicMock(sha="abc123"))
        mock_repo.create_git_ref.return_value = MagicMock()

        name = gh.create_branch(ado_id=42, title="User Auth", base_branch="main")

        assert name.startswith("feature/")
        assert "42" in name
        mock_repo.create_git_ref.assert_called_once()

    def test_branch_name_slugified(self):
        gh, mock_repo = _make_client()
        mock_repo.get_branch.return_value = MagicMock(commit=MagicMock(sha="abc"))
        mock_repo.create_git_ref.return_value = MagicMock()

        name = gh.create_branch(ado_id=1, title="Hello World Feature", base_branch="main")
        assert "hello-world-feature" in name


class TestCreatePullRequest:
    def _make_story(self) -> UserStory:
        return UserStory(
            title="Login flow",
            description="As a user, I want to login, so that I can access my account.",
            acceptance_criteria="Given I am on the login page\nWhen I submit\nThen I am logged in",
            ado_id=99,
            github_branch="feature/99-login-flow",
            test_cases=[
                QATestCase(title="Happy path"),
                QATestCase(title="Invalid credentials"),
            ],
        )

    def test_create_pr_returns_url(self):
        gh, mock_repo = _make_client()
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/owner/repo/pull/1"
        mock_repo.create_pull.return_value = mock_pr
        from github import GithubException
        mock_repo.get_label.side_effect = GithubException(404, "not found")
        mock_repo.create_label.return_value = MagicMock()

        story = self._make_story()
        url = gh.create_pull_request(story, feature_title="Auth", epic_title="Auth Epic")

        assert url == "https://github.com/owner/repo/pull/1"
        mock_repo.create_pull.assert_called_once()

    def test_pr_title_includes_ado_id(self):
        gh, mock_repo = _make_client()
        mock_repo.create_pull.return_value = MagicMock(html_url="https://github.com/test")
        from github import GithubException
        mock_repo.get_label.side_effect = GithubException(404, "not found")
        mock_repo.create_label.return_value = MagicMock()

        story = self._make_story()
        gh.create_pull_request(story)

        call_kwargs = mock_repo.create_pull.call_args
        title = call_kwargs.kwargs.get("title") or call_kwargs[1].get("title")
        assert "#99" in title

    def test_pr_body_contains_dod(self):
        gh, _ = _make_client()
        story = self._make_story()
        body = gh._build_pr_body(story, "Feature", "Epic", "", "")
        assert "Definition of Done" in body or "definition_of_done" in body.lower() or "- [ ]" in body

    def test_pr_body_contains_test_cases(self):
        gh, _ = _make_client()
        story = self._make_story()
        body = gh._build_pr_body(story, "Feature", "Epic", "", "")
        assert "Happy path" in body


class TestGeneratePRTemplate:
    def test_writes_template(self, tmp_path):
        output = tmp_path / ".github" / "pull_request_template.md"
        result = GitHubClient.generate_branch_pr_template(output)
        assert result.exists()
        content = result.read_text()
        assert "Definition of Done" in content
        assert "Azure DevOps" in content
