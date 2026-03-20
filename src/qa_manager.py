"""QA workflow module – manages test plans, test suites, and QA lifecycle."""

from __future__ import annotations

import os
from typing import Optional

from .models import QATestCase, UserStory, WorkItemHierarchy


class QAManager:
    """Creates and manages Azure DevOps Test Plans for a work item hierarchy."""

    def __init__(
        self,
        org_url: str | None = None,
        pat: str | None = None,
        project: str | None = None,
    ) -> None:
        self.org_url = org_url or os.environ.get("AZURE_DEVOPS_ORG_URL", "")
        self.pat = pat or os.environ.get("AZURE_DEVOPS_PAT", "")
        self.project = project or os.environ.get("AZURE_DEVOPS_PROJECT", "")
        self._test_client = None
        self._plan_client = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_test_client(self):
        if self._test_client is None:
            self._test_client = self._connect()
        return self._test_client

    def _connect(self):
        try:
            from azure.devops.connection import Connection  # noqa: PLC0415
            from msrest.authentication import BasicAuthentication  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "azure-devops and msrest packages are required."
            ) from exc
        creds = BasicAuthentication("", self.pat)
        connection = Connection(base_url=self.org_url, creds=creds)
        return connection.clients.get_test_client()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_test_plan(self, name: str, area_path: str = "", iteration_path: str = "") -> int:
        """Create a test plan and return its ID."""
        from azure.devops.v7_1.test.models import TestPlanCreateParams  # noqa: PLC0415

        client = self._get_test_client()
        params = TestPlanCreateParams(
            name=name,
            area_path=area_path or self.project,
            iteration=iteration_path or self.project,
        )
        plan = client.create_test_plan(params, self.project)
        return plan.id

    def create_test_suite(self, plan_id: int, suite_name: str) -> int:
        """Create a static test suite inside a plan and return its ID."""
        from azure.devops.v7_1.test.models import SuiteCreateParams  # noqa: PLC0415

        client = self._get_test_client()
        params = SuiteCreateParams(
            name=suite_name,
            suite_type="StaticTestSuite",
        )
        suite = client.create_test_suite(params, self.project, plan_id)
        return suite.id

    def add_test_cases_to_suite(
        self,
        plan_id: int,
        suite_id: int,
        test_case_ids: list[int],
    ) -> None:
        """Add test cases (by ID) to a test suite."""
        client = self._get_test_client()
        suite_test_cases = [
            {"testCase": {"id": str(tc_id)}} for tc_id in test_case_ids
        ]
        client.add_test_cases_to_suite(
            self.project,
            plan_id,
            suite_id,
            ",".join(str(tc_id) for tc_id in test_case_ids),
        )

    def create_test_plan_for_hierarchy(
        self,
        hierarchy: WorkItemHierarchy,
        area_path: str = "",
        iteration_path: str = "",
    ) -> int:
        """Create a full test plan with suites per feature and test cases per story."""
        plan_name = f"Test Plan: {hierarchy.epic.title}"
        plan_id = self.create_test_plan(plan_name, area_path, iteration_path)

        for feature in hierarchy.epic.features:
            suite_id = self.create_test_suite(plan_id, feature.title)
            tc_ids: list[int] = []
            for story in feature.user_stories:
                for tc in story.test_cases:
                    if tc.ado_id:
                        tc_ids.append(tc.ado_id)
            if tc_ids:
                self.add_test_cases_to_suite(plan_id, suite_id, tc_ids)

        return plan_id

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_test_case_markdown(story: UserStory) -> str:
        """Render test cases for a user story as a Markdown table."""
        if not story.test_cases:
            return "_No test cases._\n"
        lines = [
            f"### Test Cases for: {story.title}\n",
            "| # | Title | Type | Steps | Expected Result |",
            "|---|-------|------|-------|-----------------|",
        ]
        for i, tc in enumerate(story.test_cases, 1):
            steps = " → ".join(tc.steps) or "—"
            lines.append(
                f"| {i} | {tc.title} | {tc.test_type} | {steps} | {tc.expected_result} |"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def update_story_qa_status(story: UserStory, all_passing: bool) -> UserStory:
        """Mark a story's state based on QA results."""
        from .models import WorkItemState  # noqa: PLC0415

        if all_passing:
            story.state = WorkItemState.RESOLVED
        else:
            story.state = WorkItemState.ACTIVE
        return story
