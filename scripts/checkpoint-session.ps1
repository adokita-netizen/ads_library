[CmdletBinding()]
param(
    [string]$Note = "",
    [string]$CheckpointRoot = ".checkpoints",
    [switch]$CreateGitCommit,
    [switch]$PushToOrigin,
    [switch]$IncludeUntrackedArchive
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Green
}

function Write-WarnLine([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$gitDir = Join-Path $repoRoot ".git"
if (-not (Test-Path $gitDir)) {
    throw "Git repository not found: $repoRoot"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$checkpointBase = Join-Path $repoRoot $CheckpointRoot
$checkpointDir = Join-Path $checkpointBase $timestamp
New-Item -ItemType Directory -Force -Path $checkpointDir | Out-Null

Write-Step "Collecting repository state"
$branch = git rev-parse --abbrev-ref HEAD
$head = git rev-parse HEAD
$statusShort = git status --short
$statusFull = git status
$trackedDiff = git diff --binary --no-ext-diff
$stagedDiff = git diff --cached --binary --no-ext-diff
$untrackedFiles = git ls-files --others --exclude-standard
$trackedFiles = git diff --name-only
$stagedFiles = git diff --cached --name-only

Set-Content -Path (Join-Path $checkpointDir "branch.txt") -Value $branch
Set-Content -Path (Join-Path $checkpointDir "head.txt") -Value $head
Set-Content -Path (Join-Path $checkpointDir "note.txt") -Value $Note
Set-Content -Path (Join-Path $checkpointDir "status-short.txt") -Value $statusShort
Set-Content -Path (Join-Path $checkpointDir "status.txt") -Value $statusFull
Set-Content -Path (Join-Path $checkpointDir "tracked.diff") -Value $trackedDiff
Set-Content -Path (Join-Path $checkpointDir "staged.diff") -Value $stagedDiff
Set-Content -Path (Join-Path $checkpointDir "tracked-files.txt") -Value $trackedFiles
Set-Content -Path (Join-Path $checkpointDir "staged-files.txt") -Value $stagedFiles
Set-Content -Path (Join-Path $checkpointDir "untracked-files.txt") -Value $untrackedFiles

$metadata = [ordered]@{
    timestamp = $timestamp
    created_at = (Get-Date).ToString("o")
    repo_root = $repoRoot
    branch = $branch
    head = $head
    note = $Note
    tracked_changed_count = @($trackedFiles | Where-Object { $_ }).Count
    staged_changed_count = @($stagedFiles | Where-Object { $_ }).Count
    untracked_count = @($untrackedFiles | Where-Object { $_ }).Count
    create_git_commit = [bool]$CreateGitCommit
    push_to_origin = [bool]$PushToOrigin
}

if ($IncludeUntrackedArchive -and @($untrackedFiles | Where-Object { $_ }).Count -gt 0) {
    Write-Step "Archiving untracked files"
    $archiveDir = Join-Path $checkpointDir "untracked"
    New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null

    foreach ($relativePath in $untrackedFiles) {
        if ([string]::IsNullOrWhiteSpace($relativePath)) {
            continue
        }

        $sourcePath = Join-Path $repoRoot $relativePath
        if (-not (Test-Path $sourcePath)) {
            Write-WarnLine "Skipped missing untracked file: $relativePath"
            continue
        }

        $targetPath = Join-Path $archiveDir $relativePath
        $targetParent = Split-Path -Parent $targetPath
        if ($targetParent) {
            New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
        }

        Copy-Item -Path $sourcePath -Destination $targetPath -Force
    }
}

if ($CreateGitCommit) {
    $backupBranch = "checkpoint/$timestamp"
    Write-Step "Creating backup branch $backupBranch"
    git switch -c $backupBranch | Out-Null
    git add -A

    $message = if ($Note) {
        "checkpoint: $timestamp - $Note"
    }
    else {
        "checkpoint: $timestamp"
    }

    git commit -m $message | Out-Null
    $metadata.backup_branch = $backupBranch
    $metadata.backup_commit = (git rev-parse HEAD)

    if ($PushToOrigin) {
        Write-Step "Pushing backup branch to origin"
        git push -u origin $backupBranch
        $metadata.pushed_to_origin = $true
    }
    else {
        $metadata.pushed_to_origin = $false
    }
}

$metadataPath = Join-Path $checkpointDir "metadata.json"
$metadata | ConvertTo-Json -Depth 4 | Set-Content -Path $metadataPath
$latestPath = Join-Path $checkpointBase "latest.json"
$metadata | ConvertTo-Json -Depth 4 | Set-Content -Path $latestPath

Write-Host ""
Write-Host "Checkpoint saved:" -ForegroundColor Green
Write-Host "  $checkpointDir"
Write-Host "Branch: $branch"
Write-Host "HEAD:   $head"
if ($CreateGitCommit) {
    Write-Host "Backup branch: $($metadata.backup_branch)"
    Write-Host "Backup commit: $($metadata.backup_commit)"
}
if ($PushToOrigin) {
    Write-Host "Origin push:   completed"
}
