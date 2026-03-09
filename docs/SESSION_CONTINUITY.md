# Session Continuity

Use this workflow before risky edits, long test runs, or any session where terminal interruption would be costly.

## Goal

- Keep a local checkpoint of the exact worktree state.
- Make it easy to resume after a terminal/session drop.
- Allow an explicit backup branch push to GitHub without touching `main`.

## Local checkpoint

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\checkpoint-session.ps1 -Note "before rankings refactor"
```

This writes a timestamped checkpoint under `.checkpoints/<timestamp>/` with:

- `status.txt` and `status-short.txt`
- `tracked.diff`
- `staged.diff`
- `tracked-files.txt`
- `staged-files.txt`
- `untracked-files.txt`
- `metadata.json`

To also copy current untracked files into the checkpoint folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\checkpoint-session.ps1 -Note "capture untracked files" -IncludeUntrackedArchive
```

## Safe GitHub backup branch

The deploy workflow only runs on push to `main`, so backup branches are safe for remote continuity.

Create a checkpoint branch and commit the current worktree:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\checkpoint-session.ps1 -Note "before long crawl batch" -CreateGitCommit
```

Create a checkpoint branch, commit, and push it to GitHub:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\checkpoint-session.ps1 -Note "before infra changes" -CreateGitCommit -PushToOrigin
```

Notes:

- The script creates `checkpoint/<timestamp>`.
- This is intentionally separate from `main`.
- If you later want production deploy, merge/cherry-pick intentionally and push `main`.

## Resume after interruption

Show the latest checkpoint summary:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\resume-session.ps1
```

That prints the latest branch, HEAD, note, counts, and the checkpoint file locations to inspect.

## Recommended operating habit

1. Run a checkpoint before large edits or test batches.
2. Add `-CreateGitCommit -PushToOrigin` before risky infra/deploy work or when you need off-machine recovery.
3. Keep backup commits on `checkpoint/*` branches until the real change is reviewed and intentionally landed on `main`.
