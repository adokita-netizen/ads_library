[CmdletBinding()]
param(
    [string]$CheckpointRoot = ".checkpoints"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$latestPath = Join-Path $repoRoot $CheckpointRoot
$latestPath = Join-Path $latestPath "latest.json"

if (-not (Test-Path $latestPath)) {
    throw "No checkpoint metadata found at $latestPath"
}

$latest = Get-Content -Raw -Path $latestPath | ConvertFrom-Json
$checkpointDir = Join-Path (Join-Path $repoRoot $CheckpointRoot) $latest.timestamp

Write-Host "Latest checkpoint" -ForegroundColor Green
Write-Host "  Timestamp: $($latest.timestamp)"
Write-Host "  Created:   $($latest.created_at)"
Write-Host "  Branch:    $($latest.branch)"
Write-Host "  HEAD:      $($latest.head)"
Write-Host "  Note:      $($latest.note)"
Write-Host "  Tracked:   $($latest.tracked_changed_count)"
Write-Host "  Staged:    $($latest.staged_changed_count)"
Write-Host "  Untracked: $($latest.untracked_count)"
if ($latest.backup_branch) {
    Write-Host "  Backup branch: $($latest.backup_branch)"
}
if ($latest.backup_commit) {
    Write-Host "  Backup commit: $($latest.backup_commit)"
}
if ($latest.pushed_to_origin) {
    Write-Host "  Origin push: yes"
}

Write-Host ""
Write-Host "Files" -ForegroundColor Green
Write-Host "  Status:    $checkpointDir\status.txt"
Write-Host "  Diff:      $checkpointDir\tracked.diff"
Write-Host "  Staged:    $checkpointDir\staged.diff"
Write-Host "  Untracked: $checkpointDir\untracked-files.txt"

$statusPath = Join-Path $checkpointDir "status-short.txt"
if (Test-Path $statusPath) {
    Write-Host ""
    Write-Host "status --short snapshot" -ForegroundColor Green
    Get-Content -Path $statusPath | Select-Object -First 40
}
