param([string]$Version = 'v1.2.0', [int]$PageSize = 100)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$dataRoot = Join-Path $projectRoot 'data'
$cacheRoot = Join-Path $projectRoot 'tmp/esco-pages'
New-Item -ItemType Directory -Force -Path $dataRoot,$cacheRoot | Out-Null
# Six bounded workers download independent public pages with Windows TLS validation.
$worker = {
    param($url, $cachePath)
    $ErrorActionPreference = 'Stop'
    if (Test-Path -LiteralPath $cachePath) { return (Get-Content -LiteralPath $cachePath -Raw | ConvertFrom-Json) }
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            $result = Invoke-RestMethod -Uri $url -TimeoutSec 90
            $rows = @($result._embedded.results | ForEach-Object {
                [pscustomobject]@{conceptUri=$_.uri; preferredLabel=$_.preferredLabel.en; altLabels=($_.alternativeLabel.en -join "`n"); description=$_.description.en.literal}
            })
            if ($rows.Count -eq 0) { throw 'ESCO returned an empty page.' }
            $rows | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $cachePath -Encoding UTF8
            return $rows
        } catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds 2 }
    }
}
foreach ($kind in @('skill','occupation')) {
    $firstUrl = "https://ec.europa.eu/esco/api/search?type=$kind&language=en&limit=100&offset=0&full=false&selectedVersion=$Version"
    $metadata = Invoke-RestMethod -Uri $firstUrl -TimeoutSec 60
    $actualSize = @($metadata._embedded.results).Count
    $pageCount = [int][Math]::Ceiling($metadata.total / $actualSize)
    $pool = [RunspaceFactory]::CreateRunspacePool(1, 6)
    $pool.Open()
    $tasks = [System.Collections.Generic.List[object]]::new()
    $rows = [System.Collections.Generic.List[object]]::new()
    try {
        for ($page = 0; $page -lt $pageCount; $page++) {
            $url = "https://ec.europa.eu/esco/api/search?type=$kind&language=en&limit=$actualSize&offset=$page&full=true&selectedVersion=$Version"
            $cachePath = Join-Path $cacheRoot "$Version-$kind-$page.json"
            $ps = [PowerShell]::Create()
            $ps.RunspacePool = $pool
            $null = $ps.AddScript($worker.ToString()).AddArgument($url).AddArgument($cachePath)
            $tasks.Add([pscustomobject]@{Pipe=$ps; Handle=$ps.BeginInvoke(); Page=$page})
        }
        foreach ($task in $tasks) {
            $batch = @($task.Pipe.EndInvoke($task.Handle))
            # A recovered request can leave a nonempty error stream; validate the
            # returned data instead of discarding a successful retry.
            if ($batch.Count -eq 0) { throw "ESCO page $($task.Page) failed: $($task.Pipe.Streams.Error | Out-String)" }
            foreach ($item in $batch) { $rows.Add($item) }
            $task.Pipe.Dispose()
            if (($task.Page + 1) % 10 -eq 0) { Write-Output "ESCO ${kind}: $($rows.Count) / $($metadata.total)" }
        }
    } finally { $pool.Close(); $pool.Dispose() }
    $unique = @($rows | Sort-Object conceptUri -Unique)
    if ($unique.Count -ne $metadata.total) { throw "Catalogue count mismatch: $($unique.Count) / $($metadata.total)" }
    $unique | Export-Csv -LiteralPath (Join-Path $dataRoot "esco-$kind-en.csv") -Encoding UTF8 -NoTypeInformation
    Write-Output "Saved $($unique.Count) official ESCO $kind records."
}
@{source='https://ec.europa.eu/esco/api/search'; selectedVersion=$Version; language='en'; downloaded=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $dataRoot 'esco-source.json')
