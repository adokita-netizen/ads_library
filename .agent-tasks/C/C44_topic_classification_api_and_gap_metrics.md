# C44: Topic Classification API + Gap Metrics

## 目的
広告文/CR画像/OCR/LP由来情報からトピック分類をAPI化し、全カテゴリの取得乖離をメトリクスで可視化する。
併せて、HITに寄与した要素を返却できるようにする。

## タスク
1. 分類API追加（マルチモーダル）
- `POST /rankings/classify-topic`
- 入力: `ad_id` or raw text
- 出力: `topic_tags`, `confidence`, `evidence_terms`, `hit_drivers`, `model_version`

2. 乖離監査API追加（カテゴリ横断）
- `GET /rankings/topic-gap-report`
- 出力:
  - `expected_volume` (キーワード出現推定)
  - `classified_volume`
  - `gap`
  - `false_negative_candidates`

3. 保存契約を統一
- `ad_metadata.topic_tags`
- `ad_metadata.topic_confidence`
- `ad_metadata.topic_evidence`
 - `ad_metadata.hit_drivers`

4. 契約テスト
- 医療/金融/教育/EC/アプリの代表サンプルで分類結果を固定
- 乖離APIのレスポンス検証

## 完了条件
- [x] 分類APIが根拠つきで返却できる
- [x] topic gapをカテゴリ別に数値監視できる
- [x] API契約テストが通る

## 対象
- `backend/app/api/endpoints/rankings.py`
- `backend/tests/test_api.py`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

