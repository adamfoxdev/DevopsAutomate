# DevopsAutomate

Automate the full Azure DevOps lifecycle — from intake to Epic, Feature, User
Story, Task and QA — using AI (OpenAI / Azure OpenAI), GitHub, and enforced
engineering standards to reduce churn and streamline delivery.

---

## Overview

```
Intake Request
      │
      ▼ (AI decomposition)
    Epic
      │
      ├── Feature 1
      │     ├── User Story 1.1  ──► Tasks + QA Test Cases + GitHub Branch + Draft PR
      │     └── User Story 1.2  ──► Tasks + QA Test Cases + GitHub Branch + Draft PR
      │
      └── Feature 2
            └── User Story 2.1  ──► Tasks + QA Test Cases + GitHub Branch + Draft PR
```

All work items are:
- Created in **Azure DevOps** with correct parent-child links
- Validated against **engineering standards** (Gherkin AC, story point caps, DoD)
- Backed by **auto-generated QA test cases** and an ADO Test Plan
- Linked to **GitHub draft PRs** on standards-compliant feature branches

---

## Features

| Area | Capability |
|------|-----------|
| **AI Decomposition** | GPT-4o breaks an intake request into Epic → Features → User Stories → Tasks |
| **Azure DevOps** | Creates all work items with correct hierarchy, links, and metadata |
| **Standards Enforcement** | Validates Gherkin AC, story point caps, task types, branch names, DoD |
| **QA Automation** | Generates test cases (happy path + edge cases) and an ADO Test Plan per epic |
| **GitHub Integration** | Creates feature branches (`feature/{ado-id}-{slug}`) and draft PRs |
| **PR Templates** | Generates reusable `.github/pull_request_template.md` with DoD checklist |
| **CLI** | Single command from intake → fully created work items |

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- An [Azure DevOps](https://dev.azure.com) organization with a project
- A Personal Access Token (PAT) with **Work Items (Read & Write)** and **Test Plans** scopes
- An OpenAI API key **or** Azure OpenAI deployment

### 2. Install

```bash
git clone https://github.com/adamfoxdev/DevopsAutomate.git
cd DevopsAutomate
pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `AZURE_DEVOPS_ORG_URL` | e.g. `https://dev.azure.com/myorg` |
| `AZURE_DEVOPS_PAT` | Personal Access Token |
| `AZURE_DEVOPS_PROJECT` | Project name |
| `OPENAI_API_KEY` | OpenAI API key (or use Azure OpenAI vars) |
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `GITHUB_REPO` | `owner/repo-name` |

### 4. Run

```bash
devops-automate intake \
  --title "Customer Portal Redesign" \
  --description "Redesign the customer-facing portal to improve UX, add SSO, and reduce support tickets by 30%." \
  --requester "jane@example.com" \
  --priority 2
```

This will:
1. Call the AI to decompose the request into an Epic/Feature/Story/Task hierarchy
2. Validate all items against the engineering standards in `config/standards.yaml`
3. Create all work items in Azure DevOps with correct parent-child links
4. Create GitHub feature branches and draft PRs for each user story
5. Create an ADO Test Plan with test suites per feature
6. Save the complete hierarchy to `hierarchy.json`

### Dry Run (no ADO/GitHub calls)

```bash
devops-automate intake \
  --title "My Feature" \
  --description "A detailed description of the work to do." \
  --dry-run
```

---

## CLI Reference

### `intake` — Process a new intake request

```
devops-automate intake [OPTIONS]

Options:
  -t, --title TEXT           Short title for the intake request  [required]
  -d, --description TEXT     Detailed description of the work  [required]
  -r, --requester TEXT       Name or email of the requester
  -p, --priority [1|2|3|4]  1=Critical 2=High 3=Medium 4=Low  [default: 3]
  --tags TEXT                Comma-separated tags
  --area-path TEXT           Azure DevOps area path override
  --iteration-path TEXT      Azure DevOps iteration path override
  -o, --output TEXT          Output JSON file  [default: hierarchy.json]
  --dry-run                  AI decomposition only; skip ADO and GitHub
  --no-github                Skip GitHub branch/PR creation
  --no-test-plan             Skip ADO Test Plan creation
  --base-branch TEXT         Base branch for feature branches  [default: main]
```

### `validate` — Validate a saved hierarchy

```bash
devops-automate validate hierarchy.json
```

### `show` — Display a hierarchy tree

```bash
devops-automate show hierarchy.json
```

### `init-github` — Write the PR template

```bash
devops-automate init-github
# Writes .github/pull_request_template.md
```

---

## Project Structure

```
DevopsAutomate/
├── src/
│   ├── cli.py               # Click CLI entry point
│   ├── models.py            # Pydantic data models (Epic, Feature, UserStory, …)
│   ├── ai_assistant.py      # OpenAI/Azure OpenAI decomposition
│   ├── azure_devops.py      # Azure DevOps SDK integration
│   ├── github_integration.py# PyGithub branch/PR management
│   ├── qa_manager.py        # ADO Test Plan / Test Suite management
│   └── standards.py        # Standards validation and enforcement
├── config/
│   └── standards.yaml       # Configurable engineering standards
├── templates/
│   ├── epic_template.md
│   ├── feature_template.md
│   ├── user_story_template.md
│   └── task_template.md
├── tests/                   # Pytest test suite (53 tests)
├── .env.example             # Environment variable template
└── pyproject.toml           # Package configuration
```

---

## Engineering Standards

Edit `config/standards.yaml` to customize:

- **Minimum description lengths** for epics, features, and stories
- **User story format** (As a / I want / So that)
- **Acceptance criteria format** (Gherkin Given/When/Then)
- **Story point cap** (default: 13)
- **Definition of Done checklist** (appended to every story)
- **GitHub branch naming** (`feature|bugfix|hotfix|chore|docs/{id}-{slug}`)
- **Minimum QA test cases** per story (default: 2)

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_standards.py -v
```

---

## AI Configuration

By default the tool uses **OpenAI GPT-4o**. To use Azure OpenAI:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

The AI prompt is in `src/ai_assistant.py` and can be adjusted to match your
organization's work item templates.

---

## License

MIT
