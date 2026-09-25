param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,

    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [string]$Branch = "main",

    [string[]]$RequiredChecks = @("verify")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $env:GITHUB_TOKEN) {
    throw "Set GITHUB_TOKEN to a Personal Access Token with repo scope before running this script."
}

$headers = @{
    Authorization = "Bearer $($env:GITHUB_TOKEN)"
    Accept        = "application/vnd.github+json"
}

$contexts = @()
foreach ($check in $RequiredChecks) {
    $contexts += $check
}

$payload = @{
    required_status_checks = @{
        strict   = $true
        contexts = $contexts
    }
    enforce_admins = $true
    required_pull_request_reviews = @{
        dismissal_restrictions      = @{}
        dismiss_stale_reviews       = $true
        require_code_owner_reviews  = $false
        required_approving_review_count = 1
    }
    allow_force_pushes = $false
    allow_deletions = $false
    required_conversation_resolution = $true
}

$uri = "https://api.github.com/repos/$Owner/$Repo/branches/$Branch/protection"
Invoke-RestMethod -Method PUT -Uri $uri -Headers $headers -Body ($payload | ConvertTo-Json -Depth 8) -ContentType "application/json" | Out-Null

Write-Host "Branch protection applied to $Owner/$Repo on branch '$Branch'."
Write-Host "Required checks: $($RequiredChecks -join ', ')"
