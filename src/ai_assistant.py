"""AI assistant module – uses OpenAI / Azure OpenAI to decompose an intake
request into an Epic > Feature > UserStory > Task hierarchy."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from .models import (
    Epic,
    Feature,
    IntakeRequest,
    Priority,
    QATestCase,
    Task,
    UserStory,
    WorkItemHierarchy,
)

_STANDARDS_PATH = Path(__file__).parent.parent / "config" / "standards.yaml"

_SYSTEM_PROMPT = """\
You are an expert Agile coach and Azure DevOps architect. Your job is to take
an intake request and decompose it into a structured work item hierarchy that
follows Agile best practices.

You will produce a JSON object (no markdown fences) with the following schema:
{
  "epic": {
    "title": "<short epic title>",
    "description": "<detailed description>",
    "features": [
      {
        "title": "<feature title>",
        "description": "<feature description>",
        "acceptance_criteria": "<Gherkin Given/When/Then>",
        "user_stories": [
          {
            "title": "<user story title>",
            "description": "As a <persona>, I want <goal>, so that <benefit>.",
            "acceptance_criteria": "Given <context>\\nWhen <action>\\nThen <outcome>",
            "story_points": <fibonacci: 1,2,3,5,8,13>,
            "priority": <1=Critical,2=High,3=Medium,4=Low>,
            "tasks": [
              {
                "title": "<task title>",
                "description": "<task description>",
                "task_type": "<Development|Testing|Documentation|DevOps|Design|Code Review>",
                "estimated_hours": <float>
              }
            ],
            "test_cases": [
              {
                "title": "<test case title>",
                "preconditions": "<preconditions>",
                "steps": ["<step 1>", "<step 2>"],
                "expected_result": "<expected result>",
                "test_type": "<Manual|Automated>"
              }
            ]
          }
        ]
      }
    ]
  }
}

Rules:
- Each epic should have 1-3 features.
- Each feature should have 2-5 user stories.
- Each user story should have 2-6 tasks.
- Each user story should have at least 2 test cases (happy path + edge/negative).
- Use Fibonacci story points (1,2,3,5,8,13). Never exceed 13.
- Acceptance criteria MUST use Gherkin (Given/When/Then).
- Always include a "Code Review" task and a "Testing" task per user story.
- Tasks for DevOps/CI should have task_type = "DevOps".
- Output ONLY valid JSON, no markdown, no explanation.
"""


def _build_user_prompt(intake: IntakeRequest, standards: dict[str, Any]) -> str:
    dod = standards.get("work_items", {}).get("definition_of_done", [])
    dod_str = "\n".join(f"- {item}" for item in dod)
    return (
        f"Intake Title: {intake.title}\n"
        f"Description: {intake.description}\n"
        f"Requester: {intake.requester or 'N/A'}\n"
        f"Priority: {intake.priority.name}\n"
        f"Tags: {', '.join(intake.tags) or 'None'}\n\n"
        f"Definition of Done that every user story must satisfy:\n{dod_str}\n\n"
        "Decompose this intake into an Epic/Feature/UserStory/Task hierarchy "
        "following the JSON schema provided."
    )


class AIAssistant:
    """Wraps OpenAI (or Azure OpenAI) to generate work item hierarchies."""

    def __init__(
        self,
        api_key: str | None = None,
        azure_endpoint: str | None = None,
        azure_deployment: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        standards_path: str | Path = _STANDARDS_PATH,
    ) -> None:
        self.standards = self._load_standards(standards_path)
        ai_cfg = self.standards.get("ai", {})

        self.model = model or ai_cfg.get("model", "gpt-4o")
        self.temperature = temperature if temperature is not None else ai_cfg.get("temperature", 0.2)
        self.max_tokens = max_tokens or ai_cfg.get("max_tokens", 4096)

        # Resolve credentials from args or environment
        _api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
        _azure_endpoint = azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        _azure_deployment = azure_deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT")

        try:
            import openai  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "openai package is required. Install with: pip install openai"
            ) from exc

        if _azure_endpoint:
            self.client = openai.AzureOpenAI(
                api_key=_api_key,
                azure_endpoint=_azure_endpoint,
                api_version="2024-02-01",
            )
            self.model = _azure_deployment or self.model
        else:
            self.client = openai.OpenAI(api_key=_api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decompose(self, intake: IntakeRequest) -> WorkItemHierarchy:
        """Call the LLM and return a complete WorkItemHierarchy."""
        user_prompt = _build_user_prompt(intake, self.standards)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)
        epic = self._parse_epic(data["epic"])

        return WorkItemHierarchy(intake=intake, epic=epic)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_epic(data: dict[str, Any]) -> Epic:
        features = [AIAssistant._parse_feature(f) for f in data.get("features", [])]
        return Epic(
            title=data.get("title", ""),
            description=data.get("description", ""),
            features=features,
        )

    @staticmethod
    def _parse_feature(data: dict[str, Any]) -> Feature:
        stories = [AIAssistant._parse_user_story(s) for s in data.get("user_stories", [])]
        return Feature(
            title=data.get("title", ""),
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptance_criteria", ""),
            user_stories=stories,
        )

    @staticmethod
    def _parse_user_story(data: dict[str, Any]) -> UserStory:
        tasks = [AIAssistant._parse_task(t) for t in data.get("tasks", [])]
        test_cases = [AIAssistant._parse_test_case(tc) for tc in data.get("test_cases", [])]
        return UserStory(
            title=data.get("title", ""),
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptance_criteria", ""),
            story_points=int(data.get("story_points", 0)),
            priority=Priority(int(data.get("priority", 3))),
            tasks=tasks,
            test_cases=test_cases,
        )

    @staticmethod
    def _parse_task(data: dict[str, Any]) -> Task:
        return Task(
            title=data.get("title", ""),
            description=data.get("description", ""),
            task_type=data.get("task_type", "Development"),
            estimated_hours=float(data.get("estimated_hours", 0.0)),
        )

    @staticmethod
    def _parse_test_case(data: dict[str, Any]) -> QATestCase:
        return QATestCase(
            title=data.get("title", ""),
            preconditions=data.get("preconditions", ""),
            steps=list(data.get("steps", [])),
            expected_result=data.get("expected_result", ""),
            test_type=data.get("test_type", "Manual"),
        )

    @staticmethod
    def _load_standards(path: str | Path) -> dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        except FileNotFoundError:
            return {}
