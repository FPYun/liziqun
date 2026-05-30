param(
    [double]$Hours = 4,
    [string]$TongjiRoot = "",
    [string]$StagingRoot = "",
    [switch]$StagingOnly,
    [switch]$NoOfficialWrites,
    [switch]$SkipCompile,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StartTime = Get-Date
$BudgetSeconds = [int]([Math]::Max(300, $Hours * 3600))
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$RunRoot = Join-Path $ProjectRoot "reports\autorun_$Stamp"
if ([string]::IsNullOrWhiteSpace($StagingRoot)) {
    $StagingRoot = Join-Path $RunRoot "staging"
}
$StagingRoot = [System.IO.Path]::GetFullPath($StagingRoot)

$ResultsDir = Join-Path $StagingRoot "results"
$FiguresDir = Join-Path $StagingRoot "figures"
$LogDir = Join-Path $StagingRoot "logs"
$ReviewDir = Join-Path $StagingRoot "review"
$PreviewDir = Join-Path $StagingRoot "preview"
$StatusPath = Join-Path $LogDir "status.jsonl"

function Assert-StagingChild {
    param(
        [string]$Path,
        [string]$Label
    )
    $rootFull = [System.IO.Path]::GetFullPath($StagingRoot).TrimEnd('\', '/')
    $rootWithSep = $rootFull + [System.IO.Path]::DirectorySeparatorChar
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (($pathFull -ne $rootFull) -and (-not $pathFull.StartsWith($rootWithSep, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "$Label must be under staging root. Path: $pathFull ; StagingRoot: $rootFull"
    }
}

Assert-StagingChild -Path $ResultsDir -Label "ResultsDir"
Assert-StagingChild -Path $FiguresDir -Label "FiguresDir"
Assert-StagingChild -Path $LogDir -Label "LogDir"
Assert-StagingChild -Path $ReviewDir -Label "ReviewDir"
Assert-StagingChild -Path $PreviewDir -Label "PreviewDir"

New-Item -ItemType Directory -Force -Path $ResultsDir, $FiguresDir, $LogDir, $ReviewDir, $PreviewDir | Out-Null

function Quote-PS {
    param([string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

function Get-RemainingSeconds {
    $elapsed = ((Get-Date) - $StartTime).TotalSeconds
    return [int]([Math]::Max(0, $BudgetSeconds - $elapsed))
}

function Write-Status {
    param(
        [string]$Name,
        [string]$Status,
        [int]$ExitCode,
        [double]$Seconds,
        [string]$Command,
        [string]$Stdout = "",
        [string]$Stderr = ""
    )
    $entry = [ordered]@{
        time = (Get-Date).ToString("s")
        name = $Name
        status = $Status
        exit_code = $ExitCode
        seconds = [Math]::Round($Seconds, 1)
        remaining_seconds = Get-RemainingSeconds
        command = $Command
        stdout = $Stdout
        stderr = $Stderr
    }
    ($entry | ConvertTo-Json -Compress) | Add-Content -Path $StatusPath -Encoding UTF8
}

function Invoke-BudgetedStep {
    param(
        [string]$Name,
        [string]$Command,
        [int]$MaxMinutes,
        [int]$MinRemainingMinutes = 5,
        [switch]$Optional
    )

    $remaining = Get-RemainingSeconds
    if ($remaining -lt ($MinRemainingMinutes * 60)) {
        Write-Host "[SKIP] $Name - remaining budget too small ($remaining s)"
        Write-Status -Name $Name -Status "skipped_budget" -ExitCode 0 -Seconds 0 -Command $Command
        return
    }

    $timeoutSeconds = [Math]::Min($MaxMinutes * 60, [Math]::Max(60, $remaining - 60))
    $safeName = ($Name -replace '[^A-Za-z0-9_.-]', '_')
    $stdout = Join-Path $LogDir "$safeName.out.log"
    $stderr = Join-Path $LogDir "$safeName.err.log"

    Write-Host ""
    Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] START $Name"
    Write-Host "  timeout: $([Math]::Round($timeoutSeconds / 60, 1)) min"
    Write-Host "  command: $Command"

    if ($DryRun) {
        "DRY RUN: $Command" | Set-Content -Path $stdout -Encoding UTF8
        "" | Set-Content -Path $stderr -Encoding UTF8
        Write-Status -Name $Name -Status "dry_run" -ExitCode 0 -Seconds 0 -Command $Command -Stdout $stdout -Stderr $stderr
        return
    }

    $stepStart = Get-Date
    try {
        $process = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command) `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -WindowStyle Hidden `
            -PassThru

        $finished = $process.WaitForExit($timeoutSeconds * 1000)
        $duration = ((Get-Date) - $stepStart).TotalSeconds

        if (-not $finished) {
            Write-Host "[TIMEOUT] $Name after $([Math]::Round($duration / 60, 1)) min"
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            Write-Status -Name $Name -Status "timeout" -ExitCode 124 -Seconds $duration -Command $Command -Stdout $stdout -Stderr $stderr
            return
        }

        if ($process.ExitCode -eq 0) {
            Write-Host "[OK] $Name in $([Math]::Round($duration / 60, 1)) min"
            Write-Status -Name $Name -Status "ok" -ExitCode 0 -Seconds $duration -Command $Command -Stdout $stdout -Stderr $stderr
        } else {
            Write-Host "[FAIL] $Name exit=$($process.ExitCode). See $stderr"
            $status = if ($Optional) { "failed_optional" } else { "failed" }
            Write-Status -Name $Name -Status $status -ExitCode $process.ExitCode -Seconds $duration -Command $Command -Stdout $stdout -Stderr $stderr
        }
    } catch {
        $duration = ((Get-Date) - $stepStart).TotalSeconds
        $_ | Out-String | Set-Content -Path $stderr -Encoding UTF8
        $status = if ($Optional) { "failed_optional" } else { "failed" }
        Write-Status -Name $Name -Status $status -ExitCode 1 -Seconds $duration -Command $Command -Stdout $stdout -Stderr $stderr
    }
}

function Resolve-TongjiRoot {
    if (-not [string]::IsNullOrWhiteSpace($TongjiRoot)) {
        if (Test-Path -LiteralPath $TongjiRoot) {
            return (Resolve-Path -LiteralPath $TongjiRoot).Path
        }
        return $null
    }

    $candidate = Join-Path $ProjectRoot "TongjiThesis-1.4.0"
    if (Test-Path -LiteralPath $candidate) {
        return (Resolve-Path -LiteralPath $candidate).Path
    }
    return $null
}

function Copy-StagedPreviewTemplate {
    $sourceRoot = Resolve-TongjiRoot
    if ($null -eq $sourceRoot) {
        Write-Status -Name "R053_prepare_preview_template" -Status "skipped_missing_template" -ExitCode 0 -Seconds 0 -Command "Resolve Tongji template"
        return $null
    }

    $targetRoot = Join-Path $PreviewDir "TongjiThesis-1.4.0"
    Assert-StagingChild -Path $targetRoot -Label "Preview template"
    if (Test-Path -LiteralPath $targetRoot) {
        $targetFull = [System.IO.Path]::GetFullPath($targetRoot)
        $stagingFull = [System.IO.Path]::GetFullPath($StagingRoot).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
        if (-not $targetFull.StartsWith($stagingFull, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clear preview outside staging: $targetFull"
        }
        Remove-Item -LiteralPath $targetRoot -Recurse -Force
    }

    if ($DryRun) {
        Write-Status -Name "R053_prepare_preview_template" -Status "dry_run" -ExitCode 0 -Seconds 0 -Command "Copy $sourceRoot to $targetRoot"
        return $targetRoot
    }

    $copyStart = Get-Date
    Copy-Item -LiteralPath $sourceRoot -Destination $targetRoot -Recurse -Force
    $figureTarget = Join-Path $targetRoot "figures"
    New-Item -ItemType Directory -Force -Path $figureTarget | Out-Null
    Get-ChildItem -LiteralPath $FiguresDir -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $figureTarget $_.Name) -Force
    }
    $seconds = ((Get-Date) - $copyStart).TotalSeconds
    Write-Status -Name "R053_prepare_preview_template" -Status "ok" -ExitCode 0 -Seconds $seconds -Command "Copy $sourceRoot to $targetRoot"
    return $targetRoot
}

function Read-StatusEntries {
    if (-not (Test-Path -LiteralPath $StatusPath)) {
        return @()
    }
    return @(Get-Content -LiteralPath $StatusPath -Encoding UTF8 | Where-Object { $_.Trim().Length -gt 0 } | ForEach-Object { $_ | ConvertFrom-Json })
}

function Write-ReviewArtifacts {
    $entries = Read-StatusEntries
    $summaryPath = Join-Path $ReviewDir "RUN_SUMMARY.md"
    $figureManifestPath = Join-Path $ReviewDir "FIGURE_MANIFEST.md"
    $experimentReviewPath = Join-Path $ReviewDir "EXPERIMENT_REVIEW.md"
    $patchPreviewPath = Join-Path $ReviewDir "PAPER_PATCH_PREVIEW.diff"
    $manifestPath = Join-Path $ReviewDir "STAGING_MANIFEST.md"

    $settings = [ordered]@{
        project_root = $ProjectRoot
        staging_root = $StagingRoot
        results_dir = $ResultsDir
        figures_dir = $FiguresDir
        logs_dir = $LogDir
        official_writes = $false
        dry_run = [bool]$DryRun
        hours = $Hours
        started_at = $StartTime.ToString("s")
        finished_at = (Get-Date).ToString("s")
    }
    ($settings | ConvertTo-Json -Depth 4) | Set-Content -Path (Join-Path $ReviewDir "run_settings.json") -Encoding UTF8

    $summary = @()
    $summary += "# Run Summary"
    $summary += ""
    $summary += "- Project root: ``$ProjectRoot``"
    $summary += "- Staging root: ``$StagingRoot``"
    $summary += "- Results: ``$ResultsDir``"
    $summary += "- Figures: ``$FiguresDir``"
    $summary += "- Official thesis writes: disabled"
    $summary += "- Dry run: $([bool]$DryRun)"
    $summary += ""
    $summary += "| Step | Status | Exit | Seconds | Stdout | Stderr |"
    $summary += "|---|---:|---:|---:|---|---|"
    foreach ($entry in $entries) {
        $summary += "| $($entry.name) | $($entry.status) | $($entry.exit_code) | $($entry.seconds) | ``$($entry.stdout)`` | ``$($entry.stderr)`` |"
    }
    $summary | Set-Content -Path $summaryPath -Encoding UTF8

    $figures = @(Get-ChildItem -LiteralPath $FiguresDir -File -ErrorAction SilentlyContinue | Sort-Object Name)
    $figureManifest = @()
    $figureManifest += "# Figure Manifest"
    $figureManifest += ""
    $figureManifest += "| File | Bytes | Suggested thesis use |"
    $figureManifest += "|---|---:|---|"
    foreach ($figure in $figures) {
        $use = switch -Wildcard ($figure.Name) {
            "algorithm_*" { "Chapter 5 multi-algorithm comparison"; break }
            "runtime_*" { "Chapter 5 efficiency and quality trade-off"; break }
            "boundary_*" { "Chapter 5 boundary-effect validation"; break }
            "knee_*" { "Chapter 5 representative deployment comparison"; break }
            "paper_aligned_correlation.png" { "Chapter 5 ECR-Jmin correlation analysis"; break }
            "paper_aligned_*" { "Chapter 5 paper-aligned scenario analysis"; break }
            "13_challenging_scene.png" { "Chapter 5 challenging scenario analysis"; break }
            default { "Review before insertion" }
        }
        $figureManifest += "| ``$($figure.Name)`` | $($figure.Length) | $use |"
    }
    $figureManifest | Set-Content -Path $figureManifestPath -Encoding UTF8

    $review = @()
    $review += "# Experiment Review"
    $review += ""
    $review += "本文件是审阅草稿，不会自动写入论文。建议明早先核对数值、图像和失败步骤，再决定是否把内容并入第五章。"
    $review += ""
    $review += "## Fifth Chapter Writing Notes"
    $review += ""
    $review += "- 多算法对比应集中表述为：本文方法在复杂区域约束处理、边界覆盖和工程建模完整性方面具有优势；若某些纯 Pareto 指标由 NSGA-II、MOEA/D 或 SPEA2 更优，不写“全面优于”。"
    $review += "- 相关性分析可作为权衡关系说明：ECR 与 `$J_{\min}` 的相关性反映覆盖扩展和最小压制强度之间是否存在冲突，适合放在结果讨论或参数调优与消融分析之后。"
    $review += "- 图表进入论文前需要继续检查字号、图题距离和公式前后行距，避免把暂存图直接覆盖正式图。"
    $review += ""

    $algorithmPath = Join-Path $ResultsDir "algorithm_comparison.json"
    if (Test-Path -LiteralPath $algorithmPath) {
        $algorithm = Get-Content -LiteralPath $algorithmPath -Encoding UTF8 | ConvertFrom-Json
        $review += "## Multi-Algorithm Comparison Summary"
        $review += ""
        $review += "| Scenario | Method | HV mean | Spacing mean | Solutions mean | Runtime mean |"
        $review += "|---|---|---:|---:|---:|---:|"
        foreach ($row in @($algorithm.summary)) {
            $review += "| $($row.scenario) | $($row.method) | $($row.hv_mean) | $($row.spacing_mean) | $($row.n_solutions_mean) | $($row.runtime_mean) |"
        }
        $review += ""
    }

    foreach ($name in @("paper_aligned_results.json", "challenging_scene_results.json")) {
        $path = Join-Path $ResultsDir $name
        if (Test-Path -LiteralPath $path) {
            $data = Get-Content -LiteralPath $path -Encoding UTF8 | ConvertFrom-Json
            $review += "## $($data.scenario) Correlation Summary"
            $review += ""
            $review += "- Pareto solution count: $($data.n_solutions)"
            $review += "- ECR range: $($data.ecr_min) to $($data.ecr_max)"
            $review += "- `$J_{\min}` range: $($data.j_min_min) to $($data.j_min_max)"
            $review += "- ECR-`$J_{\min}` correlation: $($data.correlation)"
            $review += ""
        }
    }
    $review | Set-Content -Path $experimentReviewPath -Encoding UTF8

    $patch = @()
    $patch += "# Review-only patch preview"
    $patch += "#"
    $patch += "# No thesis source was modified by this autorun."
    $patch += "# Use EXPERIMENT_REVIEW.md and FIGURE_MANIFEST.md tomorrow morning to decide"
    $patch += "# which figures, tables, and paragraphs should be applied to Chapter 5."
    $patch | Set-Content -Path $patchPreviewPath -Encoding UTF8

    $files = @(Get-ChildItem -LiteralPath $StagingRoot -Recurse -File -ErrorAction SilentlyContinue | Sort-Object FullName)
    $manifest = @()
    $manifest += "# Staging Manifest"
    $manifest += ""
    $manifest += "- Staging root: ``$StagingRoot``"
    $manifest += "- File count: $($files.Count)"
    $manifest += ""
    $manifest += "| File | Bytes |"
    $manifest += "|---|---:|"
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($StagingRoot.Length).TrimStart('\', '/')
        $manifest += "| ``$relative`` | $($file.Length) |"
    }
    $manifest | Set-Content -Path $manifestPath -Encoding UTF8
}

$settingsForConsole = [ordered]@{
    ProjectRoot = $ProjectRoot
    StagingRoot = $StagingRoot
    ResultsDir = $ResultsDir
    FiguresDir = $FiguresDir
    LogDir = $LogDir
    BudgetHours = $Hours
    OfficialWrites = $false
    DryRun = [bool]$DryRun
}
($settingsForConsole | ConvertTo-Json -Depth 4) | Set-Content -Path (Join-Path $StagingRoot "autorun_settings.json") -Encoding UTF8

Write-Host "Four-hour thesis autorun (staging only)"
Write-Host "Project: $ProjectRoot"
Write-Host "Staging: $StagingRoot"
Write-Host "Budget: $Hours hour(s)"
Write-Host "Official thesis/results writes: disabled"

$algorithmPath = Join-Path $ResultsDir "algorithm_comparison.json"
$boundaryPath = Join-Path $ResultsDir "boundary_analysis.json"
$paperAlignedComparisonPath = Join-Path $ResultsDir "algorithm_comparison_paper_aligned.json"

Invoke-BudgetedStep `
    -Name "R001_targeted_tests" `
    -MaxMinutes 20 `
    -Command "python -m pytest tests\test_metrics.py tests\test_baseline_algorithms.py tests\test_experiment_protocol.py -q"

Invoke-BudgetedStep `
    -Name "R010_challenging_algorithm_comparison_5seeds" `
    -MaxMinutes 100 `
    -Command "python experiments\compare_algorithms.py --scenario challenging --methods ours mopso_legacy nsga2 moead spea2 random --seeds 2026 2027 2028 2029 2030 --N_P 80 --T_max 180 --output $(Quote-PS $algorithmPath)"

Invoke-BudgetedStep `
    -Name "R020_boundary_lshape_5seeds" `
    -MaxMinutes 80 `
    -Command "python experiments\boundary_analysis.py --methods ours_transform direct_physical mopso_legacy nsga2 --seeds 2026 2027 2028 2029 2030 --N_P 80 --T_max 180 --boundary_grid 35 --output $(Quote-PS $boundaryPath)"

Invoke-BudgetedStep `
    -Name "R030_core_ablations" `
    -MaxMinutes 70 `
    -Command "python experiments\ablation_core.py --ablation all --output-dir $(Quote-PS $ResultsDir) --figure-dir $(Quote-PS $FiguresDir)"

Invoke-BudgetedStep `
    -Name "R040_paper_aligned_main_scene" `
    -MaxMinutes 45 `
    -Command "python experiments\experiment_paper_aligned.py --output-dir $(Quote-PS $ResultsDir) --figure-dir $(Quote-PS $FiguresDir)"

Invoke-BudgetedStep `
    -Name "R041_challenging_main_scene" `
    -MaxMinutes 35 `
    -Command "python experiments\experiment_challenging.py --output-dir $(Quote-PS $ResultsDir) --figure-dir $(Quote-PS $FiguresDir)"

Invoke-BudgetedStep `
    -Name "R060_backfill_challenging_extra_seeds" `
    -MaxMinutes 90 `
    -MinRemainingMinutes 75 `
    -Optional `
    -Command "python experiments\compare_algorithms.py --scenario challenging --methods ours mopso_legacy nsga2 moead spea2 random --seeds 2031 2032 2033 2034 2035 2036 --N_P 100 --T_max 240 --output $(Quote-PS $algorithmPath) --append"

Invoke-BudgetedStep `
    -Name "R061_paper_aligned_algorithm_comparison" `
    -MaxMinutes 70 `
    -MinRemainingMinutes 60 `
    -Optional `
    -Command "python experiments\compare_algorithms.py --scenario paper_aligned --methods ours mopso_legacy nsga2 spea2 --seeds 2026 2027 2028 --N_P 50 --T_max 180 --output $(Quote-PS $paperAlignedComparisonPath)"

Write-Status -Name "R050_sync_results" -Status "skipped_staging_only" -ExitCode 0 -Seconds 0 -Command "Skipped to avoid writing official results directory"

Invoke-BudgetedStep `
    -Name "R051_generate_comparison_figures" `
    -MaxMinutes 20 `
    -Command "python tools\generate_comparison_figures.py --results-dir $(Quote-PS $ResultsDir) --figure-dir $(Quote-PS $FiguresDir)"

if (-not $SkipCompile) {
    $previewRoot = Copy-StagedPreviewTemplate
    if ($null -ne $previewRoot) {
        $compileCommand = @"
Set-Location $(Quote-PS $previewRoot)
`$env:TEXINPUTS='.;./style//;./chapters//;./figures//;'
`$env:BIBINPUTS='.;./bib//;'
xelatex -interaction=nonstopmode -shell-escape main.tex
biber main
xelatex -interaction=nonstopmode -shell-escape main.tex
xelatex -interaction=nonstopmode -shell-escape main.tex
"@

        Invoke-BudgetedStep `
            -Name "R054_compile_staged_preview_pdf" `
            -MaxMinutes 45 `
            -Optional `
            -Command $compileCommand
    }
} else {
    Write-Status -Name "R054_compile_staged_preview_pdf" -Status "skipped_by_flag" -ExitCode 0 -Seconds 0 -Command "SkipCompile"
}

Write-ReviewArtifacts

Write-Host ""
Write-Host "Autorun complete. Review package: $ReviewDir"
Write-Host "Status file: $StatusPath"
