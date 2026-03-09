# D29: media_tasks DBセッション・リトライ修正

## 問題
- リトライ時にDBセッションが前回の失敗状態を引き継ぐ → クエリエラー
- ステータス遷移が不整合（`processing` → 例外 → リトライで再度 `processing`、`failed` を経由しない）
- `max_retries=3` だがリトライ間隔の backoff が固定

## 対象ファイル
- `backend/app/tasks/media_tasks.py`

## 修正

### 1. リトライ前のセッションクリーンアップ
```python
@celery_app.task(bind=True, max_retries=3)
def extract_media_task(self, ad_id: str, **kwargs):
    try:
        with get_sync_session() as session:
            _do_extraction(session, ad_id)
    except Exception as exc:
        # セッションは with ブロックで自動 close される
        # リトライ時は新しいセッションが作られる
        self.retry(exc=exc, countdown=2 ** self.request.retries * 10)
```

### 2. ステータス状態遷移の明確化
```python
# 状態遷移: pending → processing → completed/failed
# リトライ時: processing → retrying → processing → ...

def _do_extraction(session, ad_id):
    ad = session.query(Ad).filter_by(ad_id=ad_id).first()
    if not ad:
        return  # リトライしない

    # ステータス更新
    _update_status(session, ad, "processing")
    try:
        result = _extract(ad)
        _update_status(session, ad, "completed", result)
    except Exception:
        _update_status(session, ad, "retrying")
        raise  # 上位の retry ハンドラへ

def _update_status(session, ad, status, result=None):
    meta = ad.ad_metadata or {}
    meta["media_extraction_status"] = status
    meta["media_extraction_updated_at"] = datetime.utcnow().isoformat()
    if result:
        meta.update(result)
    ad.ad_metadata = meta
    session.commit()
```

### 3. Exponential backoff
```python
@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,),
                 retry_backoff=True, retry_backoff_max=300)
```

## 制約
- `media_tasks.py` のみ修正
- タスクのシグネチャ（引数）は変更しない
