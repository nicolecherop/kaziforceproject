# GitHub Project Board, Milestones, and Issue Automation

This repository includes scripts and workflow files to bootstrap GitHub planning artifacts and keep them maintained.

## What is included

- Issue templates in `.github/ISSUE_TEMPLATE/` for bug, feature, and task tracking.
- Pull request template in `.github/pull_request_template.md`.
- Project board auto-add workflow in `.github/workflows/project-board.yml`.
- Bootstrap script for project, milestones, labels, and seed issues in `scripts/bootstrap_github_project.ps1`.
- Branch protection script in `scripts/set_github_branch_protection.ps1`.

## 1) Create board, milestones, and issues

Create a personal access token (classic or fine-grained) with repository and projects permissions.

PowerShell:

```powershell
$env:GITHUB_TOKEN = "<your-token>"
.
\scripts\bootstrap_github_project.ps1 -Owner "<owner>" -Repo "<repo>"
```

The script creates (or reuses):

- A Project (v2) board titled `KaziForce Delivery Board`
- Milestones M1/M2/M3
- Priority labels
- Seed planning issues, each attached to a milestone and added to the project

## 2) Enable project auto-management

In GitHub repository settings, add:

- Repository variable `GITHUB_PROJECT_URL`: the board URL printed by the bootstrap script.
- Repository secret `GH_PROJECT_AUTOMATION_TOKEN`: token with access to add items to the project.

Once set, every new issue and non-draft pull request is added automatically to the board.

## 3) Enforce tests before merge

This repository already runs CI on every pull request in `.github/workflows/ci.yml`.

Apply branch protection so PRs cannot merge unless CI passes:

```powershell
$env:GITHUB_TOKEN = "<your-token>"
.
\scripts\set_github_branch_protection.ps1 -Owner "<owner>" -Repo "<repo>" -Branch "main" -RequiredChecks verify
```

If your default branch is `master`, pass `-Branch "master"`.