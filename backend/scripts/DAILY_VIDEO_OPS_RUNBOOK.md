# Daily Video Ops Runbook

## Overview
This project runs daily video intelligence operations via Windows Task Scheduler task:

- Task name: `ads_library_daily_video_ops`
- Script: `backend/scripts/run_daily_video_ops.cmd`
- Default time: daily `04:30`

The task executes:

`python -m scripts.daily_video_ops_notify --analyze-limit 50 --sample-limit 10`

## Environment Variables

Set these in the environment used by the scheduled task:

- `DAILY_VIDEO_OPS_WEBHOOK_URL` (preferred)
- `SLACK_WEBHOOK_URL` (fallback)
- `DAILY_VIDEO_OPS_NOTIFY_SUCCESS=1` (optional; notify on OK as well)

## Manual Commands

Run scheduled task now:

`schtasks /Run /TN ads_library_daily_video_ops`

Check task status:

`schtasks /Query /TN ads_library_daily_video_ops /V /FO LIST`

Run notifier directly:

`python -m scripts.daily_video_ops_notify --analyze-limit 50 --sample-limit 10`

Force alert test without sending:

`python -m scripts.daily_video_ops_notify --force-level WARN --dry-run`

Force alert test with one-off webhook:

`python -m scripts.daily_video_ops_notify --force-level WARN --webhook-url "<WEBHOOK_URL>"`

## Logs

- Main log: `backend/logs/daily_video_ops.log`
- Rotated backup: `backend/logs/daily_video_ops.log.1`
- Rotation threshold: 5MB

## Failure Triage

1. Confirm task execution:
   - `Last Run Time`, `Last Result`, `Status` from `schtasks /Query ...`
2. Check latest log tail:
   - `Get-Content backend\\logs\\daily_video_ops.log -Tail 100`
3. Run report snapshot:
   - `python -m app.tasks.runner report_video_analysis '{"sample_limit":10}'`
4. If backlog appears:
   - `python -m app.tasks.runner analyze_new_videos '{"limit":200}'`

