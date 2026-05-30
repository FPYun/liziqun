$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$resultsDir = Join-Path $projectRoot "results"
$figuresDir = Join-Path $projectRoot "figures"

New-Item -ItemType Directory -Force -Path $resultsDir | Out-Null

function Resolve-FirstExistingPath {
    param(
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    return $null
}

$syncPlan = @(
    @{
        Name = "tune_results.json"
        Candidates = @(
            (Join-Path $figuresDir "tune_results.json"),
            (Join-Path $projectRoot "tune_results.json")
        )
    },
    @{
        Name = "quick_compare_results.json"
        Candidates = @(
            (Join-Path $figuresDir "quick_compare_results.json"),
            (Join-Path $projectRoot "quick_compare_results.json")
        )
    },
    @{
        Name = "paper_aligned_results.json"
        Candidates = @(
            (Join-Path $figuresDir "paper_aligned_results.json"),
            (Join-Path $projectRoot "paper_aligned_results.json")
        )
    },
    @{
        Name = "challenging_scene_results.json"
        Candidates = @(
            (Join-Path $figuresDir "challenging_scene_results.json"),
            (Join-Path $projectRoot "challenging_scene_results.json")
        )
    }
)

foreach ($item in $syncPlan) {
    $source = Resolve-FirstExistingPath -Candidates $item.Candidates
    $target = Join-Path $resultsDir $item.Name

    if ($null -eq $source) {
        Write-Host "Missing source, skipped: $($item.Name)"
        continue
    }

    $resolvedTarget = Resolve-Path $target -ErrorAction SilentlyContinue | ForEach-Object Path
    if ($source -eq $resolvedTarget) {
        Write-Host "Already canonical: $source"
    } else {
        Copy-Item -Force $source $target
        Write-Host "Synced: $source -> $target"
    }
}

Write-Host ""
Write-Host "Result intake directory ready: $resultsDir"
