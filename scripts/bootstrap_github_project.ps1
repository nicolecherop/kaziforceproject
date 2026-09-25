param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,

    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [string]$ProjectTitle = "KaziForce Delivery Board",

    [ValidateSet("open", "closed", "all")]
    [string]$MilestoneState = "open"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $env:GITHUB_TOKEN) {
    throw "Set GITHUB_TOKEN to a Personal Access Token with repo and project scopes before running this script."
}

$headers = @{
    Authorization = "Bearer $($env:GITHUB_TOKEN)"
    Accept        = "application/vnd.github+json"
}

function Invoke-GithubRest {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("GET", "POST", "PATCH", "PUT")]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [object]$Body
    )
    $uri = "https://api.github.com$Path"
    if ($null -ne $Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body ($Body | ConvertTo-Json -Depth 8) -ContentType "application/json"
    }
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
}

function Invoke-GithubGraphql {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Query,
        [hashtable]$Variables = @{}
    )
    $body = @{
        query     = $Query
        variables = $Variables
    }
    return Invoke-RestMethod -Method POST -Uri "https://api.github.com/graphql" -Headers $headers -Body ($body | ConvertTo-Json -Depth 8) -ContentType "application/json"
}

Write-Host "Resolving repository and owner metadata..."
$repoInfo = Invoke-GithubRest -Method GET -Path "/repos/$Owner/$Repo"

$viewerQuery = @"
query {
  viewer {
    id
    login
  }
}
"@
$viewerResponse = Invoke-GithubGraphql -Query $viewerQuery
$ownerId = $repoInfo.owner.node_id

Write-Host "Creating (or reusing) project board..."
$projectsQuery = @"
query(
  $owner: String!,
  $repo: String!
) {
  repository(owner: $owner, name: $repo) {
    projectsV2(first: 50) {
      nodes {
        id
        title
        url
      }
    }
  }
}
"@
$existingProjects = Invoke-GithubGraphql -Query $projectsQuery -Variables @{ owner = $Owner; repo = $Repo }
$project = $existingProjects.data.repository.projectsV2.nodes | Where-Object { $_.title -eq $ProjectTitle } | Select-Object -First 1

if (-not $project) {
    $createProjectMutation = @"
mutation(
  $ownerId: ID!,
  $title: String!
) {
  createProjectV2(input: { ownerId: $ownerId, title: $title }) {
    projectV2 {
      id
      title
      url
    }
  }
}
"@
    $created = Invoke-GithubGraphql -Query $createProjectMutation -Variables @{ ownerId = $ownerId; title = $ProjectTitle }
    $project = $created.data.createProjectV2.projectV2
}

Write-Host "Project URL: $($project.url)"

$milestones = @(
    @{ title = "M1 - Foundation and setup"; description = "Environment setup, baseline data import, and first runnable release."; due_on = (Get-Date).AddDays(14).ToString("o") },
    @{ title = "M2 - Matching quality and UX"; description = "Matching quality improvements, recruiter/candidate UX updates, and tests."; due_on = (Get-Date).AddDays(28).ToString("o") },
    @{ title = "M3 - Hardening and release"; description = "Performance checks, documentation completion, and final release prep."; due_on = (Get-Date).AddDays(42).ToString("o") }
)

Write-Host "Ensuring milestones exist..."
$existingMilestones = Invoke-GithubRest -Method GET -Path "/repos/$Owner/$Repo/milestones?state=$MilestoneState"
$milestoneMap = @{}
foreach ($m in $existingMilestones) {
    $milestoneMap[$m.title] = $m.number
}

foreach ($milestone in $milestones) {
    if (-not $milestoneMap.ContainsKey($milestone.title)) {
        $createdMilestone = Invoke-GithubRest -Method POST -Path "/repos/$Owner/$Repo/milestones" -Body $milestone
        $milestoneMap[$createdMilestone.title] = $createdMilestone.number
        Write-Host "Created milestone: $($createdMilestone.title)"
    }
}

$labels = @(
    @{ name = "priority:high"; color = "B60205"; description = "High-priority work" },
    @{ name = "priority:medium"; color = "FBCA04"; description = "Medium-priority work" },
    @{ name = "priority:low"; color = "0E8A16"; description = "Lower-priority work" },
    @{ name = "chore"; color = "C5DEF5"; description = "Maintenance or housekeeping" }
)

Write-Host "Ensuring labels exist..."
$existingLabels = Invoke-GithubRest -Method GET -Path "/repos/$Owner/$Repo/labels?per_page=100"
$existingLabelNames = @($existingLabels | ForEach-Object { $_.name })
foreach ($label in $labels) {
    if ($existingLabelNames -notcontains $label.name) {
        Invoke-GithubRest -Method POST -Path "/repos/$Owner/$Repo/labels" -Body $label | Out-Null
        Write-Host "Created label: $($label.name)"
    }
}

$seedIssues = @(
    @{ title = "Set up branch protection with required CI checks"; body = "Require CI checks before merge and disallow bypass for direct pushes to the default branch."; labels = @("chore", "priority:high"); milestone = "M1 - Foundation and setup" },
    @{ title = "Validate ESCO import data quality"; body = "Audit imported skills and occupations for duplicates, missing labels, and linkage anomalies."; labels = @("enhancement", "priority:medium"); milestone = "M1 - Foundation and setup" },
    @{ title = "Improve matching score explanations in candidate UI"; body = "Make score rationale and skill-gap explanations easier to interpret by candidates."; labels = @("enhancement", "priority:medium"); milestone = "M2 - Matching quality and UX" },
    @{ title = "Add regression tests for recruiter workflow"; body = "Cover job creation, application review, shortlist, and decision transitions end-to-end."; labels = @("chore", "priority:high"); milestone = "M2 - Matching quality and UX" },
    @{ title = "Finalize release checklist and documentation pass"; body = "Complete final docs review, verification pass, and release checklist."; labels = @("chore", "priority:low"); milestone = "M3 - Hardening and release" }
)

Write-Host "Creating missing seed issues and adding them to project..."
$existingOpenIssues = Invoke-GithubRest -Method GET -Path "/repos/$Owner/$Repo/issues?state=open&per_page=100"
$existingIssueTitles = @($existingOpenIssues | ForEach-Object { $_.title })

$addItemMutation = @"
mutation(
  $projectId: ID!,
  $contentId: ID!
) {
  addProjectV2ItemById(input: { projectId: $projectId, contentId: $contentId }) {
    item {
      id
    }
  }
}
"@

foreach ($seed in $seedIssues) {
    $issue = $null
    if ($existingIssueTitles -contains $seed.title) {
        $issue = $existingOpenIssues | Where-Object { $_.title -eq $seed.title } | Select-Object -First 1
    }
    else {
        $payload = @{
            title     = $seed.title
            body      = $seed.body
            labels    = $seed.labels
            milestone = $milestoneMap[$seed.milestone]
        }
        $issue = Invoke-GithubRest -Method POST -Path "/repos/$Owner/$Repo/issues" -Body $payload
        Write-Host "Created issue: #$($issue.number) $($issue.title)"
    }

    if ($issue.node_id) {
        Invoke-GithubGraphql -Query $addItemMutation -Variables @{ projectId = $project.id; contentId = $issue.node_id } | Out-Null
    }
}

Write-Host "Bootstrap complete."
Write-Host "Project board: $($project.url)"
