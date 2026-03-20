"""Standards enforcement for work items and GitHub artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import Epic, Feature, UserStory, Task, QATestCase, Priority

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "standards.yaml"


def load_standards(config_path: str | Path = _DEFAULT_CONFIG) -> dict[str, Any]:
    """Load standards configuration from a YAML file."""
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class StandardsViolation(Exception):
    """Raised when a work item violates defined standards."""


class StandardsEnforcer:
    """Validates work items against the configured standards."""

    def __init__(self, config_path: str | Path = _DEFAULT_CONFIG) -> None:
        self.standards = load_standards(config_path)
        self._wi = self.standards.get("work_items", {})
        self._gh = self.standards.get("github", {})
        self._qa = self.standards.get("qa", {})

    # ------------------------------------------------------------------
    # Public validation API
    # ------------------------------------------------------------------

    def validate_epic(self, epic: Epic) -> list[str]:
        """Return a list of violation messages for an Epic."""
        violations: list[str] = []
        if not epic.title.strip():
            violations.append("Epic title must not be empty.")
        min_len = self._wi.get("min_description_length", 20)
        if len(epic.description.strip()) < min_len:
            violations.append(
                f"Epic description must be at least {min_len} characters."
            )
        return violations

    def validate_feature(self, feature: Feature) -> list[str]:
        """Return a list of violation messages for a Feature."""
        violations: list[str] = []
        if not feature.title.strip():
            violations.append("Feature title must not be empty.")
        min_len = self._wi.get("min_description_length", 20)
        if len(feature.description.strip()) < min_len:
            violations.append(
                f"Feature description must be at least {min_len} characters."
            )
        return violations

    def validate_user_story(self, story: UserStory) -> list[str]:
        """Return a list of violation messages for a UserStory."""
        violations: list[str] = []
        if not story.title.strip():
            violations.append("User story title must not be empty.")

        # User story format check
        required_sections = self._wi.get("user_story_required_sections", [])
        for section in required_sections:
            if section.lower() not in story.description.lower():
                violations.append(
                    f"User story description must contain '{section}'."
                )

        # Acceptance criteria format
        ac_format = self._wi.get("acceptance_criteria_format", "gherkin")
        if ac_format == "gherkin":
            if story.acceptance_criteria and not self._is_gherkin(story.acceptance_criteria):
                violations.append(
                    "Acceptance criteria must use Gherkin format (Given/When/Then)."
                )

        # Story points cap
        max_sp = self._wi.get("max_story_points", 13)
        if story.story_points > max_sp:
            violations.append(
                f"Story points ({story.story_points}) exceed maximum ({max_sp})."
            )

        # Minimum test cases
        min_tc = self._qa.get("min_test_cases_per_story", 2)
        if len(story.test_cases) < min_tc:
            violations.append(
                f"User story must have at least {min_tc} QA test case(s) "
                f"(found {len(story.test_cases)})."
            )

        return violations

    def validate_task(self, task: Task) -> list[str]:
        """Return a list of violation messages for a Task."""
        violations: list[str] = []
        if not task.title.strip():
            violations.append("Task title must not be empty.")
        allowed_types = self._wi.get("task_types", [])
        if allowed_types and task.task_type not in allowed_types:
            violations.append(
                f"Task type '{task.task_type}' is not in the allowed list: "
                f"{allowed_types}."
            )
        return violations

    def validate_branch_name(self, branch: str) -> list[str]:
        """Validate a GitHub branch name against the configured pattern."""
        violations: list[str] = []
        allowed_types = self._gh.get("branch_types", [])
        if allowed_types:
            pattern = r"^(" + "|".join(re.escape(t) for t in allowed_types) + r")/.+"
            if not re.match(pattern, branch):
                violations.append(
                    f"Branch name '{branch}' must start with one of "
                    f"{allowed_types} followed by a '/' and a descriptor."
                )
        return violations

    def get_definition_of_done(self) -> list[str]:
        """Return the configured Definition of Done checklist."""
        return list(self._wi.get("definition_of_done", []))

    def append_definition_of_done(self, story: UserStory) -> UserStory:
        """Append the DoD checklist to a user story's description."""
        dod = self.get_definition_of_done()
        if not dod:
            return story
        dod_text = "\n\n**Definition of Done:**\n" + "\n".join(
            f"- [ ] {item}" for item in dod
        )
        story.description = story.description.rstrip() + dod_text
        return story

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_gherkin(text: str) -> bool:
        """Return True if text contains at least one Given/When/Then block."""
        lower = text.lower()
        return "given" in lower and "when" in lower and "then" in lower

    def make_branch_name(self, ado_id: int | str, title: str, branch_type: str = "feature") -> str:
        """Generate a standards-compliant branch name."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
        return f"{branch_type}/{ado_id}-{slug}"
