"""Azure DevOps integration – creates and links work items via the REST API."""

from __future__ import annotations

import os
from typing import Optional

from .models import (
    Epic,
    Feature,
    Priority,
    QATestCase,
    Task,
    UserStory,
    WorkItemHierarchy,
    WorkItemState,
)


def _priority_to_ado(priority: Priority) -> int:
    """Map internal Priority enum to ADO integer (1-4)."""
    return int(priority)


class AzureDevOpsClient:
    """Thin wrapper around the azure-devops SDK for work item management."""

    def __init__(
        self,
        org_url: str | None = None,
        pat: str | None = None,
        project: str | None = None,
        area_path: str | None = None,
        iteration_path: str | None = None,
    ) -> None:
        self.org_url = org_url or os.environ.get("AZURE_DEVOPS_ORG_URL", "")
        self.pat = pat or os.environ.get("AZURE_DEVOPS_PAT", "")
        self.project = project or os.environ.get("AZURE_DEVOPS_PROJECT", "")
        self.area_path = area_path or os.environ.get("ADO_AREA_PATH", self.project)
        self.iteration_path = iteration_path or os.environ.get("ADO_ITERATION_PATH", self.project)

        self._wit_client = None
        self._test_client = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_wit_client(self):
        if self._wit_client is None:
            self._wit_client = self._connect_wit()
        return self._wit_client

    def _get_test_client(self):
        if self._test_client is None:
            self._test_client = self._connect_test()
        return self._test_client

    def _connect_wit(self):
        try:
            from azure.devops.connection import Connection  # noqa: PLC0415
            from msrest.authentication import BasicAuthentication  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "azure-devops and msrest packages are required. "
                "Install with: pip install azure-devops msrest"
            ) from exc

        credentials = BasicAuthentication("", self.pat)
        connection = Connection(base_url=self.org_url, creds=credentials)
        return connection.clients.get_work_item_tracking_client()

    def _connect_test(self):
        try:
            from azure.devops.connection import Connection  # noqa: PLC0415
            from msrest.authentication import BasicAuthentication  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "azure-devops and msrest packages are required. "
                "Install with: pip install azure-devops msrest"
            ) from exc

        credentials = BasicAuthentication("", self.pat)
        connection = Connection(base_url=self.org_url, creds=credentials)
        return connection.clients.get_test_client()

    # ------------------------------------------------------------------
    # Work item creation helpers
    # ------------------------------------------------------------------

    def _patch_document(self, fields: dict[str, str]) -> list:
        """Build a JSON Patch document from a field dict."""
        from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation  # noqa: PLC0415

        return [
            JsonPatchOperation(
                op="add",
                path=f"/fields/{key}",
                value=value,
            )
            for key, value in fields.items()
        ]

    def _create_work_item(self, work_item_type: str, fields: dict[str, str]) -> int:
        """Create a single work item and return its ID."""
        client = self._get_wit_client()
        doc = self._patch_document(fields)
        result = client.create_work_item(
            document=doc,
            project=self.project,
            type=work_item_type,
        )
        return result.id

    def _add_parent_link(self, child_id: int, parent_id: int) -> None:
        """Add a parent-child relationship between two work items."""
        from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation  # noqa: PLC0415

        client = self._get_wit_client()
        relation_patch = [
            JsonPatchOperation(
                op="add",
                path="/relations/-",
                value={
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": f"{self.org_url}/{self.project}/_apis/wit/workItems/{parent_id}",
                    "attributes": {"comment": "Auto-linked by DevopsAutomate"},
                },
            )
        ]
        client.update_work_item(
            document=relation_patch,
            id=child_id,
            project=self.project,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_epic(self, epic: Epic, area_path: str = "", iteration_path: str = "") -> Epic:
        """Create an Epic work item in Azure DevOps."""
        fields = {
            "System.Title": epic.title,
            "System.Description": epic.description,
            "System.AreaPath": area_path or self.area_path,
            "System.IterationPath": iteration_path or self.iteration_path,
        }
        epic.ado_id = self._create_work_item("Epic", fields)
        return epic

    def create_feature(self, feature: Feature, parent_epic_id: int,
                       area_path: str = "", iteration_path: str = "") -> Feature:
        """Create a Feature work item and link it to its parent Epic."""
        fields = {
            "System.Title": feature.title,
            "System.Description": feature.description,
            "Microsoft.VSTS.Common.AcceptanceCriteria": feature.acceptance_criteria,
            "System.AreaPath": area_path or self.area_path,
            "System.IterationPath": iteration_path or self.iteration_path,
        }
        feature.ado_id = self._create_work_item("Feature", fields)
        self._add_parent_link(feature.ado_id, parent_epic_id)
        return feature

    def create_user_story(
        self, story: UserStory, parent_feature_id: int,
        area_path: str = "", iteration_path: str = ""
    ) -> UserStory:
        """Create a User Story work item and link it to its parent Feature."""
        fields = {
            "System.Title": story.title,
            "System.Description": story.description,
            "Microsoft.VSTS.Common.AcceptanceCriteria": story.acceptance_criteria,
            "Microsoft.VSTS.Scheduling.StoryPoints": str(story.story_points),
            "Microsoft.VSTS.Common.Priority": str(_priority_to_ado(story.priority)),
            "System.AreaPath": area_path or self.area_path,
            "System.IterationPath": iteration_path or self.iteration_path,
        }
        story.ado_id = self._create_work_item("User Story", fields)
        self._add_parent_link(story.ado_id, parent_feature_id)
        return story

    def create_task(self, task: Task, parent_story_id: int,
                    area_path: str = "", iteration_path: str = "") -> Task:
        """Create a Task work item and link it to its parent User Story."""
        fields = {
            "System.Title": task.title,
            "System.Description": task.description,
            "Microsoft.VSTS.Common.Activity": task.task_type,
            "System.AreaPath": area_path or self.area_path,
            "System.IterationPath": iteration_path or self.iteration_path,
        }
        if task.estimated_hours > 0:
            fields["Microsoft.VSTS.Scheduling.OriginalEstimate"] = str(task.estimated_hours)
        task.ado_id = self._create_work_item("Task", fields)
        self._add_parent_link(task.ado_id, parent_story_id)
        return task

    def create_test_case(self, tc: QATestCase, parent_story_id: int,
                         area_path: str = "") -> QATestCase:
        """Create a Test Case work item and link it to its parent User Story."""
        steps_html = self._render_test_steps(tc.steps)
        fields = {
            "System.Title": tc.title,
            "System.Description": tc.preconditions,
            "Microsoft.VSTS.TCM.Steps": steps_html,
            "Microsoft.VSTS.TCM.AutomationStatus": (
                "Planned" if tc.test_type == "Automated" else "Not Automated"
            ),
            "System.AreaPath": area_path or self.area_path,
        }
        tc.ado_id = self._create_work_item("Test Case", fields)
        self._add_parent_link(tc.ado_id, parent_story_id)
        return tc

    def create_hierarchy(self, hierarchy: WorkItemHierarchy) -> WorkItemHierarchy:
        """Create the full Epic > Feature > UserStory > Task hierarchy in ADO."""
        intake = hierarchy.intake
        area = intake.area_path or self.area_path
        iteration = intake.iteration_path or self.iteration_path

        # Epic
        hierarchy.epic = self.create_epic(hierarchy.epic, area, iteration)

        for feature in hierarchy.epic.features:
            feature = self.create_feature(feature, hierarchy.epic.ado_id, area, iteration)

            for story in feature.user_stories:
                story = self.create_user_story(story, feature.ado_id, area, iteration)

                for task in story.tasks:
                    self.create_task(task, story.ado_id, area, iteration)

                for tc in story.test_cases:
                    self.create_test_case(tc, story.ado_id, area)

        return hierarchy

    def update_work_item_state(self, item_id: int, state: WorkItemState) -> None:
        """Update the state of a work item."""
        from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation  # noqa: PLC0415

        client = self._get_wit_client()
        doc = [
            JsonPatchOperation(
                op="add",
                path="/fields/System.State",
                value=state.value,
            )
        ]
        client.update_work_item(document=doc, id=item_id, project=self.project)

    def link_github_commit(self, work_item_id: int, commit_url: str, comment: str = "") -> None:
        """Link a GitHub commit to a work item."""
        from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation  # noqa: PLC0415

        client = self._get_wit_client()
        patch = [
            JsonPatchOperation(
                op="add",
                path="/relations/-",
                value={
                    "rel": "ArtifactLink",
                    "url": commit_url,
                    "attributes": {
                        "name": "GitHub Commit",
                        "comment": comment or "Linked by DevopsAutomate",
                    },
                },
            )
        ]
        client.update_work_item(document=patch, id=work_item_id, project=self.project)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_test_steps(steps: list[str]) -> str:
        """Render test steps as ADO HTML table format."""
        if not steps:
            return ""
        rows = "".join(
            f"<tr><td>{i + 1}</td><td>{step}</td><td></td></tr>"
            for i, step in enumerate(steps)
        )
        return (
            '<table border="1">'
            "<thead><tr><th>#</th><th>Step</th><th>Expected</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
