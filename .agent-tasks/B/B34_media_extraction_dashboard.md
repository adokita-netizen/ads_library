# B34: メディア抽出ステータスダッシュボード

## 目的
メディア抽出パイプラインの進捗をリアルタイムに確認できるダッシュボードUI。
管理者がどの広告が抽出済み/保留中/失敗かを一目で把握できる。

## タスク

### 1. MediaExtractionDashboard コンポーネント
- `frontend/src/components/dashboard/MediaExtractionDashboard.tsx` を新規作成

#### 表示内容
- **サマリーカード** (4枚横並び):
  - 抽出完了: completed + enriched 件数 (緑)
  - 保留中: pending + pending_heavy 件数 (黄)
  - 実行中: dispatched 件数 (青, アニメーション)
  - 失敗: failed 件数 (赤)

- **進捗バー**: 全広告中の抽出完了率 (%)

- **広告テーブル**: media_extraction_status でフィルタ可能
  | ID | タイトル | 広告主 | ステータス | クリエイティブ種別 | 画像 | 動画 | 操作 |
  |----|---------|--------|-----------|-----------------|------|------|------|
  - ステータスバッジ: completed=緑, pending=黄, failed=赤, dispatched=青
  - 操作: 「再抽出」ボタン（failedの場合）、「詳細」リンク

- **バッチ操作ボタン**:
  - 「保留中を一括抽出」→ POST /api/v1/ads/batch-extract-media
  - 「失敗を再試行」→ POST /api/v1/ads/retry-failed-media

### 2. API連携
```typescript
// frontend/src/lib/api.ts に追加

// GET /rankings/media-extraction-status — C32が作成するAPI
export const fetchMediaExtractionStatus = () =>
  fetchApi('/rankings/media-extraction-status');

// POST /rankings/batch-extract-media — C32が作成するAPI
export const triggerBatchExtraction = (limit: number) =>
  fetchApi('/rankings/batch-extract-media', {
    method: 'POST',
    body: JSON.stringify({ limit }),
  });
```

### 3. サイドバーにメニュー追加
- `frontend/src/components/common/Sidebar.tsx` に「メディア管理」メニュー項目追加
- アイコン: `Image` (lucide-react)
- 位置: 「設定」の上

## デザイン仕様
- カラー: 既存パレット準拠 (#4A7DFF プライマリ)
- サマリーカード: `bg-white rounded-lg shadow-sm p-4`
- テーブル: 既存の HitAdAnalysisView のテーブルスタイル踏襲
- 進捗バー: `bg-gray-200 rounded-full h-2` の中に `bg-green-500`

## 依存
- **C32** のメディア抽出ステータスAPIが先に必要
- APIが未完成の場合はモックデータで先行実装可

## 制約
- `frontend/src/components/dashboard/` にのみファイル作成
- `frontend/src/lib/api.ts` にfetch関数追加
- `frontend/src/components/common/Sidebar.tsx` にメニュー追加
- Tailwind CSS のみ使用
