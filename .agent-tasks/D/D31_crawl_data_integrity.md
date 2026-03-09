# D31: クロールデータ整合性改善

## 問題
- `crawl_tasks.py` の部分失敗時にDBが不整合状態（一部広告のみ更新済み）
- 同一広告への重複クロールリクエストがキューに溜まる
- クロール結果の上書きで既存の有効データを消す可能性

## 対象ファイル
- `backend/app/tasks/crawl_tasks.py`

## 修正

### 1. 広告単位のトランザクション分離
```python
def crawl_ads(ad_ids: list[str]):
    results = {"success": [], "failed": []}
    for ad_id in ad_ids:
        try:
            with get_sync_session() as session:
                _crawl_single_ad(session, ad_id)
                session.commit()
                results["success"].append(ad_id)
        except Exception as e:
            logger.error(f"Failed to crawl {ad_id}: {e}")
            results["failed"].append({"ad_id": ad_id, "error": str(e)})
    return results
```

### 2. 重複クロール防止
```python
def _crawl_single_ad(session, ad_id):
    ad = session.query(Ad).filter_by(ad_id=ad_id).with_for_update().first()
    if not ad:
        return

    meta = ad.ad_metadata or {}
    last_crawled = meta.get("last_crawled_at")
    if last_crawled:
        elapsed = (datetime.utcnow() - datetime.fromisoformat(last_crawled)).seconds
        if elapsed < 300:  # 5分以内の再クロールはスキップ
            logger.info(f"Skipping {ad_id}: crawled {elapsed}s ago")
            return

    # クロール実行
    meta["last_crawled_at"] = datetime.utcnow().isoformat()
    # ...
```

### 3. 既存データの保護（マージ戦略）
```python
def _update_ad_data(session, ad, new_data: dict):
    """新データを既存データにマージ（nullで上書きしない）"""
    for key, value in new_data.items():
        if value is not None:  # null値では既存データを消さない
            setattr(ad, key, value)

    # ad_metadata もマージ
    meta = ad.ad_metadata or {}
    new_meta = new_data.get("ad_metadata", {})
    for k, v in new_meta.items():
        if v is not None:
            meta[k] = v
    ad.ad_metadata = meta
```

## 制約
- `crawl_tasks.py` のみ修正
- クロールロジック自体は変更しない（データ永続化部分のみ）
