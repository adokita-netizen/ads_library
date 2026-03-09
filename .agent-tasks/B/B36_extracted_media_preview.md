# B36: 抽出メディアプレビュー強化

## 目的
Playwright で抽出されたメディア（画像・動画）をフロントエンドで適切にプレビュー表示。
S3キーからの画像配信、フォールバック表示、カルーセル対応。

## タスク

### 1. CreativeViewer 改善
- `frontend/src/components/common/CreativeViewer.tsx` を修正

#### 追加機能
- **S3画像対応**: `image_s3_key` がある場合、`/api/v1/media/images/{s3_key}` 経由で表示
- **カルーセル表示**: `image_s3_keys.urls[]` が複数ある場合、左右矢印でスライド
- **抽出ステータスバッジ**: 右上に `completed`/`enriched`/`pending` バッジ
- **フォールバック優先順位**:
  1. `image_s3_key` → S3 proxy 経由
  2. `image_url` → 直接表示
  3. `thumbnail_url` → サムネイル
  4. `snapshot_url` → スナップショットリンク
  5. プレースホルダー

### 2. AdDetailModal メディアタブ追加
- `frontend/src/components/analysis/ProductDetailModal.tsx` を修正
- 新タブ「メディア」追加:
  - 抽出された全画像のギャラリー表示
  - 動画プレーヤー（video_url がある場合）
  - メディア抽出メタデータ:
    - 抽出方法 (HTTP / Playwright)
    - 抽出日時
    - creative_type
    - 画像数 / 動画数

### 3. HitAdAnalysisView メディアアイコン
- テーブルの各行に小さなメディアアイコン表示
  - 📷 画像あり (image_url or image_s3_key)
  - 🎬 動画あり (video_url)
  - ⏳ 抽出待ち (media_extraction_status == "pending")
  - ❌ 抽出失敗 (media_extraction_status == "failed")

## 制約
- `frontend/src/components/` 配下のみ編集
- 画像表示は `<img>` タグ（`next/image` 不使用）
- Tailwind CSS のみ
