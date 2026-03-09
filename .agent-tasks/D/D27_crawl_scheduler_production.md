# D27: Production Crawl Scheduler

## Status: WAITING (Step 7 - after full pipeline verification)
## Depends on: C31 (pipeline connection), A31/A32 (deploy)

## CONFLICT WARNING
- `lambda_handler.py` is also modified by **Agent C (C31)** who adds `extract_media` action
- Agent D modifies ONLY `_run_crawl()` function tail (auto-dispatch after crawl)
- Do NOT add new actions or new functions to lambda_handler.py
- Coordinate: D27 executes AFTER C31 is complete

## Target Files
- `terraform/eventbridge.tf` (NEW - Agent D creates)
- `backend/lambda_handler.py` (_run_crawl tail ONLY)

---

## Task 1: EventBridge schedule rules (terraform/eventbridge.tf - NEW FILE)

```hcl
# Daily crawl: 3:00 AM JST (18:00 UTC)
resource "aws_cloudwatch_event_rule" "daily_crawl" {
  name                = "vaap-daily-crawl"
  description         = "Daily Japanese ad crawl at 3:00 AM JST"
  schedule_expression = "cron(0 18 * * ? *)"
}

resource "aws_cloudwatch_event_target" "daily_crawl_target" {
  rule = aws_cloudwatch_event_rule.daily_crawl.name
  arn  = aws_lambda_function.api.arn

  input = jsonencode({
    action             = "crawl"
    queries            = ["スキンケア", "ダイエット", "美容液", "サプリメント", "化粧品",
                          "プロテイン", "脱毛", "育毛", "ホワイトニング", "エステ"]
    platforms          = ["facebook", "instagram"]
    limit_per_platform = 30
  })
}

resource "aws_lambda_permission" "allow_eventbridge_crawl" {
  statement_id  = "AllowEventBridgeCrawl"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_crawl.arn
}

# Weekly media extraction: Monday 4:00 AM JST (19:00 UTC Sunday)
resource "aws_cloudwatch_event_rule" "weekly_media_extraction" {
  name                = "vaap-weekly-media-extraction"
  description         = "Weekly batch media extraction at 4:00 AM JST on Monday"
  schedule_expression = "cron(0 19 ? * MON *)"
}

resource "aws_cloudwatch_event_target" "weekly_media_target" {
  rule = aws_cloudwatch_event_rule.weekly_media_extraction.name
  arn  = aws_lambda_function.api.arn

  input = jsonencode({
    action   = "extract_media"
    limit    = 100
    statuses = ["pending", "pending_heavy"]
  })
}

resource "aws_lambda_permission" "allow_eventbridge_media" {
  statement_id  = "AllowEventBridgeMedia"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_media_extraction.arn
}
```

---

## Task 2: Auto-dispatch media extraction after crawl (lambda_handler.py)

Find `_run_crawl()` function. At the END of the function, BEFORE the final `return`, add:

```python
# Auto-dispatch media extraction for newly crawled ads
if total_saved > 0:
    try:
        from app.tasks.dispatcher import dispatch_task
        pending_ads = session.query(Ad).filter(
            Ad.media_extraction_status == "pending",
            Ad.snapshot_url.isnot(None),
        ).limit(total_saved).all()

        media_dispatched = 0
        for ad in pending_ads:
            try:
                dispatch_task("extract_media", ad_id=ad.id)
                ad.media_extraction_status = "dispatched"
                media_dispatched += 1
            except Exception:
                pass
        session.commit()
        query_results["media_dispatched"] = media_dispatched
        logger.info("auto_media_dispatch", dispatched=media_dispatched, total_saved=total_saved)
    except Exception as e:
        logger.warning("auto_media_dispatch_failed", error=str(e))
```

**IMPORTANT:** Only add code inside `_run_crawl()`. Do NOT:
- Add new top-level functions
- Add new `action` branches
- Modify `_run_extract_media()` (Agent C's C31 task)

---

## Constraints
- `terraform/eventbridge.tf`: New file (no conflict)
- `lambda_handler.py`: ONLY modify `_run_crawl()` tail
- Coordinate with Agent C planner: D27 runs AFTER C31
- Print statements: English only
