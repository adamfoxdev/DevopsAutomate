"""GitHub integration – manages branches, pull requests, and PR templates."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from rich.console import Console

from .models import UserStory, WorkItemHierarchy
from .standards import StandardsEnforcer

console = Console(stderr=True)

_PR_TEMPLATE = """\
## Summary
<!-- Provide a brief description of the changes in this PR. -->
{description}

## Azure DevOps Work Item
- **Epic:** [{epic_title}]({epic_url})
- **Feature:** [{feature_title}]({feature_url})
- **User Story:** [#{story_id} {story_title}]({story_url})

## Changes
<!-- List the key changes made in this PR. -->
- 

## Test Coverage
### QA Test Cases
{test_cases}

## Definition of Done
{dod_checklist}

## Screenshots / Recordings
<!-- Add screenshots or recordings if applicable. -->

## Notes for Reviewer
<!-- Any additional notes for the code reviewer. -->
"""


class GitHubClient:
    """Wraps PyGithub to manage branches and pull requests."""

    def __init__(
        self,
        token: str | None = None,
        repo_name: str | None = None,
        standards_enforcer: StandardsEnforcer | None = None,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.repo_name = repo_name or os.environ.get("GITHUB_REPO", "")
        self.enforcer = standards_enforcer or StandardsEnforcer()
        self._gh = None
        self._repo = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_repo(self):
        if self._repo is None:
            try:
                from github import Github  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "PyGithub package is required. Install with: pip install PyGithub"
                ) from exc
            self._gh = Github(self.token)
            self._repo = self._gh.get_repo(self.repo_name)
        return self._repo

    # ------------------------------------------------------------------
    # Branch management
    # ------------------------------------------------------------------

    def create_branch(
        self,
        ado_id: int,
        title: str,
        branch_type: str = "feature",
        base_branch: str = "main",
    ) -> str:
        """Create a feature branch and return its name."""
        branch_name = self.enforcer.make_branch_name(ado_id, title, branch_type)
        repo = self._get_repo()

        # Get the SHA of the base branch
        base_ref = repo.get_branch(base_branch)
        sha = base_ref.commit.sha

        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=sha)
        return branch_name

    def get_or_create_branch(
        self,
        ado_id: int,
        title: str,
        branch_type: str = "feature",
        base_branch: str = "main",
    ) -> str:
        """Return an existing branch or create it if it doesn't exist."""
        branch_name = self.enforcer.make_branch_name(ado_id, title, branch_type)
        repo = self._get_repo()
        try:
            from github import GithubException  # noqa: PLC0415

            repo.get_branch(branch_name)
            return branch_name
        except GithubException:
            return self.create_branch(ado_id, title, branch_type, base_branch)

    # ------------------------------------------------------------------
    # Pull request management
    # ------------------------------------------------------------------

    def create_pull_request(
        self,
        story: UserStory,
        feature_title: str = "",
        epic_title: str = "",
        ado_org_url: str = "",
        ado_project: str = "",
        base_branch: str = "main",
        draft: bool = True,
        labels: list[str] | None = None,
    ) -> str:
        """Create a GitHub PR for a user story and return the PR URL."""
        repo = self._get_repo()

        pr_title = f"[#{story.ado_id}] {story.title}"
        body = self._build_pr_body(
            story=story,
            feature_title=feature_title,
            epic_title=epic_title,
            ado_org_url=ado_org_url,
            ado_project=ado_project,
        )

        # Ensure branch exists
        if not story.github_branch:
            story.github_branch = self.get_or_create_branch(
                ado_id=story.ado_id or 0,
                title=story.title,
                base_branch=base_branch,
            )

        pr = repo.create_pull(
            title=pr_title,
            body=body,
            head=story.github_branch,
            base=base_branch,
            draft=draft,
        )

        # Apply labels
        _labels = labels or ["ado-linked"]
        try:
            from github import GithubException  # noqa: PLC0415

            for label_name in _labels:
                try:
                    lbl = repo.get_label(label_name)
                except GithubException:
                    lbl = repo.create_label(label_name, "0075ca")
                pr.add_to_labels(lbl)
        except GithubException as exc:
            # Labels are non-critical; log and continue
            console.print(f"[yellow]Warning: could not apply PR labels:[/] {exc}", highlight=False)

        return pr.html_url

    def create_prs_for_hierarchy(
        self,
        hierarchy: WorkItemHierarchy,
        ado_org_url: str = "",
        ado_project: str = "",
        base_branch: str = "main",
        draft: bool = True,
    ) -> WorkItemHierarchy:
        """Create GitHub branches and draft PRs for every user story in a hierarchy."""
        epic = hierarchy.epic
        for feature in epic.features:
            for story in feature.user_stories:
                pr_url = self.create_pull_request(
                    story=story,
                    feature_title=feature.title,
                    epic_title=epic.title,
                    ado_org_url=ado_org_url,
                    ado_project=ado_project,
                    base_branch=base_branch,
                    draft=draft,
                )
                # Store URL in the story description for traceability
                story.description += f"\n\nGitHub PR: {pr_url}"
        return hierarchy

    # ------------------------------------------------------------------
    # PR template helpers
    # ------------------------------------------------------------------

    def _build_pr_body(
        self,
        story: UserStory,
        feature_title: str,
        epic_title: str,
        ado_org_url: str,
        ado_project: str,
    ) -> str:
        def _ado_url(item_id: Optional[int]) -> str:
            if item_id and ado_org_url and ado_project:
                return f"{ado_org_url}/{ado_project}/_workitems/edit/{item_id}"
            return "#"

        test_case_lines = "\n".join(
            f"- [ ] {tc.title}" for tc in story.test_cases
        ) or "- [ ] No test cases generated"

        dod = self.enforcer.get_definition_of_done()
        dod_lines = "\n".join(f"- [ ] {item}" for item in dod) or "- [ ] See standards.yaml"

        return _PR_TEMPLATE.format(
            description=story.description.split("\n\n")[0],
            epic_title=epic_title or "Epic",
            epic_url=_ado_url(None),
            feature_title=feature_title or "Feature",
            feature_url=_ado_url(None),
            story_id=story.ado_id or "N/A",
            story_title=story.title,
            story_url=_ado_url(story.ado_id),
            test_cases=test_case_lines,
            dod_checklist=dod_lines,
        )

    @staticmethod
    def generate_branch_pr_template(output_path: str | Path = ".github/pull_request_template.md") -> Path:
        """Write a reusable PR template to the repository root."""
        template = """\
## Summary
<!-- Brief description of the change -->

## Azure DevOps Work Item
<!-- Link to the ADO work item: https://dev.azure.com/ORG/PROJECT/_workitems/edit/ID -->
- ADO: #

## Type of Change
- [ ] Feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Documentation
- [ ] DevOps / CI

## Test Coverage
- [ ] Unit tests added / updated
- [ ] QA test cases created in Azure DevOps
- [ ] Integration tests passing

## Definition of Done
- [ ] Code reviewed and approved
- [ ] Unit tests written and passing
- [ ] Acceptance criteria met
- [ ] QA test cases created and passing
- [ ] Documentation updated if applicable
- [ ] No critical or high security vulnerabilities
- [ ] PR linked to Azure DevOps work item

## Screenshots / Recordings
<!-- Add screenshots or recordings if applicable -->
"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template, encoding="utf-8")
        return path
