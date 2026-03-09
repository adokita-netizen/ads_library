# D36: PENDING広告メディア抽出バッチ処理

## 優先度: 🅰️ A（クリティカル）

## 問題
- 本番DBに約50件の広告が `media_extraction_status = PENDING` のまま
- Playwrightパイプラインは稼働確認済み（2026-03-02: 2/2テスト成功）
- PENDING分を一括で処理するバッチ実行が必要

## 対象ファイル
- `backend/app/tasks/media_tasks.py`
- `backend/sqs_ecs_trigger.py`
- `backend/app/services/media_extraction.py`

## タスク

### Task 1: PENDINGリスト取得スクリプト
```python
# PENDING状態の全広告IDを取得
SELECT id, ad_id, title FROM ads
WHERE media_extraction_status = 'PENDING'
ORDER BY id;
```

### Task 2: バッチディスパッチ
- 50件をSQS heavy queueに順次投入
- 同時実行数を制御（ECS Fargate同時タスク数制限考慮）
- 各ジョブ間に適切なインターバル（rate limiting）

### Task 3: 失敗リトライ
- FAILED状態の広告を再度PENDING→DISPATCHED→処理
- 最大リトライ3回、それ以上はSKIPPED
- 失敗理由をad_metadataに記録

### Task 4: 完了確認
- 全件のmedia_extraction_statusがCOMPLETED/ENRICHED/SKIPPEDであること
- S3にメディアファイルが存在すること確認
- DB上のvideo_s3_key/thumbnail_urlが設定されていること

## 完了条件
- [ ] PENDING状態の広告が0件になる
- [ ] 各広告にメディアファイル(画像/動画)がS3に格納されている
- [ ] DB上のmedia_extraction_statusが最終状態に更新されている
- [ ] 処理ログがCloudWatchに記録されている

## 制約
- ECS Fargateの同時タスク上限に注意
- NAT Gateway(t4g.nano)の帯域制限を考慮し、同時ダウンロード数を制御
- 外部サイトへのアクセスはrate limitingを適用
