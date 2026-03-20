"""CLI entry point for DevopsAutomate."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

load_dotenv()

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_hierarchy_json(path: str):
    """Load a WorkItemHierarchy from a JSON file."""
    from .models import WorkItemHierarchy  # noqa: PLC0415

    with open(path, "r", encoding="utf-8") as fh:
        return WorkItemHierarchy.model_validate_json(fh.read())


def _print_hierarchy(hierarchy) -> None:
    """Pretty-print a WorkItemHierarchy to the console."""
    epic = hierarchy.epic
    tree = Tree(f"[bold magenta]Epic:[/] {epic.title} (ADO: {epic.ado_id or 'pending'})")
    for feature in epic.features:
        f_node = tree.add(
            f"[bold blue]Feature:[/] {feature.title} (ADO: {feature.ado_id or 'pending'})"
        )
        for story in feature.user_stories:
            s_node = f_node.add(
                f"[bold green]Story:[/] {story.title} "
                f"({story.story_points} pts, ADO: {story.ado_id or 'pending'})"
            )
            for task in story.tasks:
                s_node.add(
                    f"[yellow]Task:[/] {task.title} [{task.task_type}] "
                    f"({task.estimated_hours}h)"
                )
            for tc in story.test_cases:
                s_node.add(f"[cyan]Test:[/] {tc.title} [{tc.test_type}]")
    console.print(tree)


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option("0.1.0", prog_name="devops-automate")
def main():
    """DevopsAutomate – AI-powered Azure DevOps lifecycle automation."""


# ---------------------------------------------------------------------------
# intake command
# ---------------------------------------------------------------------------

@main.command()
@click.option("--title", "-t", required=True, help="Short title for the intake request.")
@click.option("--description", "-d", required=True, help="Detailed description of the work.")
@click.option("--requester", "-r", default="", help="Name or email of the requester.")
@click.option(
    "--priority",
    "-p",
    type=click.Choice(["1", "2", "3", "4"], case_sensitive=False),
    default="3",
    show_default=True,
    help="Priority: 1=Critical, 2=High, 3=Medium, 4=Low.",
)
@click.option("--tags", default="", help="Comma-separated tags.")
@click.option("--area-path", default="", help="Azure DevOps area path override.")
@click.option("--iteration-path", default="", help="Azure DevOps iteration path override.")
@click.option(
    "--output",
    "-o",
    default="hierarchy.json",
    show_default=True,
    help="Output file for the generated hierarchy JSON.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generate hierarchy with AI but do NOT create items in Azure DevOps.",
)
@click.option(
    "--no-github",
    is_flag=True,
    default=False,
    help="Skip GitHub branch/PR creation.",
)
@click.option(
    "--no-test-plan",
    is_flag=True,
    default=False,
    help="Skip Azure DevOps Test Plan creation.",
)
@click.option(
    "--base-branch",
    default="main",
    show_default=True,
    help="Base GitHub branch for new feature branches.",
)
def intake(
    title: str,
    description: str,
    requester: str,
    priority: str,
    tags: str,
    area_path: str,
    iteration_path: str,
    output: str,
    dry_run: bool,
    no_github: bool,
    no_test_plan: bool,
    base_branch: str,
) -> None:
    """Process an intake request: AI decomposition → ADO work items → GitHub PRs."""

    from .ai_assistant import AIAssistant  # noqa: PLC0415
    from .azure_devops import AzureDevOpsClient  # noqa: PLC0415
    from .github_integration import GitHubClient  # noqa: PLC0415
    from .models import IntakeRequest, Priority  # noqa: PLC0415
    from .qa_manager import QAManager  # noqa: PLC0415
    from .standards import StandardsEnforcer  # noqa: PLC0415

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    intake_req = IntakeRequest(
        title=title,
        description=description,
        requester=requester,
        priority=Priority(int(priority)),
        tags=tag_list,
        area_path=area_path,
        iteration_path=iteration_path,
    )

    console.print(Panel(f"[bold]Processing Intake:[/] {title}", style="cyan"))

    # ── Step 1: AI decomposition ──────────────────────────────────────
    console.print("\n[1/4] 🤖 Decomposing intake with AI...")
    try:
        import openai  # noqa: PLC0415

        ai = AIAssistant()
        hierarchy = ai.decompose(intake_req)
    except openai.OpenAIError as exc:
        console.print(f"[red]AI decomposition failed:[/] {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001 – catch non-OpenAI errors (e.g. import, JSON parse)
        console.print(f"[red]AI decomposition failed:[/] {exc}")
        raise SystemExit(1) from exc

    # ── Step 2: Standards validation ─────────────────────────────────
    console.print("[2/4] 📋 Validating against standards...")
    enforcer = StandardsEnforcer()
    violations: list[str] = []
    violations += enforcer.validate_epic(hierarchy.epic)
    for feature in hierarchy.epic.features:
        violations += enforcer.validate_feature(feature)
        for story in feature.user_stories:
            violations += enforcer.validate_user_story(story)
            for task in story.tasks:
                violations += enforcer.validate_task(task)
            # Append DoD to each story
            enforcer.append_definition_of_done(story)

    if violations:
        console.print("[yellow]Standards violations found (auto-corrected where possible):[/]")
        for v in violations:
            console.print(f"  ⚠  {v}")

    # ── Step 3: Create Azure DevOps work items ────────────────────────
    if not dry_run:
        console.print("[3/4] 🔵 Creating Azure DevOps work items...")
        try:
            ado = AzureDevOpsClient()
            hierarchy = ado.create_hierarchy(hierarchy)
            console.print(
                f"  ✅ Epic #{hierarchy.epic.ado_id}: {hierarchy.epic.title}"
            )
        except Exception as exc:  # noqa: BLE001 – azure-devops SDK raises varied exception types
            console.print(f"[red]Azure DevOps creation failed:[/] {exc}")
            raise SystemExit(1) from exc

        # ── Step 4a: Create GitHub branches + PRs ────────────────────
        if not no_github:
            console.print("[4/4] 🐙 Creating GitHub branches and draft PRs...")
            try:
                gh = GitHubClient(standards_enforcer=enforcer)
                hierarchy = gh.create_prs_for_hierarchy(
                    hierarchy,
                    ado_org_url=ado.org_url,
                    ado_project=ado.project,
                    base_branch=base_branch,
                )
            except Exception as exc:  # noqa: BLE001 – non-fatal; GitHub integration optional
                console.print(f"[yellow]GitHub integration failed (non-fatal):[/] {exc}")

        # ── Step 4b: Create test plan ─────────────────────────────────
        if not no_test_plan:
            console.print("     📐 Creating Azure DevOps Test Plan...")
            try:
                qa = QAManager()
                plan_id = qa.create_test_plan_for_hierarchy(hierarchy)
                console.print(f"  ✅ Test Plan #{plan_id} created.")
            except Exception as exc:  # noqa: BLE001 – non-fatal; test plans are optional
                console.print(f"[yellow]Test plan creation failed (non-fatal):[/] {exc}")
    else:
        console.print("[3/4] ⏭  Dry-run: skipping Azure DevOps and GitHub steps.")
        console.print("[4/4] ⏭  Dry-run: skipping test plan creation.")

    # ── Save output ───────────────────────────────────────────────────
    Path(output).write_text(hierarchy.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"\n[bold green]✅ Hierarchy saved to:[/] {output}")

    # ── Pretty print ─────────────────────────────────────────────────
    _print_hierarchy(hierarchy)


# ---------------------------------------------------------------------------
# validate command
# ---------------------------------------------------------------------------

@main.command()
@click.argument("hierarchy_file", type=click.Path(exists=True))
def validate(hierarchy_file: str) -> None:
    """Validate a saved hierarchy JSON against the configured standards."""

    from .standards import StandardsEnforcer  # noqa: PLC0415

    hierarchy = _load_hierarchy_json(hierarchy_file)
    enforcer = StandardsEnforcer()
    all_violations: list[str] = []

    all_violations += enforcer.validate_epic(hierarchy.epic)
    for feature in hierarchy.epic.features:
        all_violations += enforcer.validate_feature(feature)
        for story in feature.user_stories:
            all_violations += enforcer.validate_user_story(story)
            for task in story.tasks:
                all_violations += enforcer.validate_task(task)

    if all_violations:
        console.print(f"[red]Found {len(all_violations)} violation(s):[/]")
        for v in all_violations:
            console.print(f"  ❌ {v}")
        raise SystemExit(1)
    else:
        console.print("[green]✅ All standards checks passed.[/]")


# ---------------------------------------------------------------------------
# show command
# ---------------------------------------------------------------------------

@main.command()
@click.argument("hierarchy_file", type=click.Path(exists=True))
def show(hierarchy_file: str) -> None:
    """Display a saved hierarchy JSON in a tree view."""
    hierarchy = _load_hierarchy_json(hierarchy_file)
    _print_hierarchy(hierarchy)


# ---------------------------------------------------------------------------
# init-github command
# ---------------------------------------------------------------------------

@main.command("init-github")
@click.option(
    "--output",
    "-o",
    default=".github/pull_request_template.md",
    show_default=True,
    help="Path to write the PR template.",
)
def init_github(output: str) -> None:
    """Write the standard GitHub PR template to the repository."""
    from .github_integration import GitHubClient  # noqa: PLC0415

    path = GitHubClient.generate_branch_pr_template(output)
    console.print(f"[green]✅ PR template written to:[/] {path}")


if __name__ == "__main__":
    main()
