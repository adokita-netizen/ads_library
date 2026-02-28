# Agent B: 指示書

## あなたの役割
フロントエンドエンジニア。
UI/UX改善・ダッシュボード構築を担当する。

## タスク一覧（上から順に実行）

### 済 ~~1. クリエイティブビューワー~~
- 指示書: `B_クリエイティブビューワー.md`
- CreativeViewer.tsx 作成済み、ProductDetailModal.tsx に統合済み

### 済 ~~2. トレンドレーダー / 勝ちパターン分析 / パクりガイド~~
- log.md / status.md 参照
- TrendView.tsx, HitAdAnalysisView.tsx, ProductDetailModal.tsx 修正済み

### 済 ~~3. 分析ダッシュボード強化~~
### 済 ~~4. 新API連携~~

### 済 ~~5. 広告詳細モーダル & UX改善~~

### 6. LP遷移先表示 & ダッシュボード改善 ← 現在のタスク
- 指示書: `B6_LP表示とダッシュボード改善.md`
- テーブルにLP遷移先カラム追加
- AdDetailModalにLP情報統合
- dashboard-summary API連携
- ジャンル比較チャート

## 作業開始前に必ず読むファイル
```
frontend/src/components/dashboard/HitAdAnalysisView.tsx  ← ヒット広告テーブル（自分が既に修正済み）
frontend/src/components/dashboard/AdLibraryTable.tsx      ← LP遷移ボタンの実装参考
frontend/src/components/analysis/ProductDetailModal.tsx   ← 詳細モーダル（自分が既に修正済み）
frontend/src/components/common/CreativeViewer.tsx         ← 自分が作成済み
frontend/src/components/dashboard/TrendView.tsx           ← チャート実装参考
frontend/src/lib/api.ts                                   ← APIクライアント
frontend/src/lib/constants.ts                             ← 定数
frontend/src/lib/format.ts                                ← フォーマット関数
frontend/src/types/index.ts                               ← 型定義
```

---

## ★★★ コンフリクト防止ルール ★★★

### 触っていいファイル（Agent B の専有領域）
```
frontend/src/components/                    ← 全コンポーネント修正・作成OK
frontend/src/lib/                           ← ユーティリティ修正OK
frontend/src/types/                         ← 型定義の追加OK（既存削除NG）
frontend/src/app/                           ← ページ修正OK
frontend/public/                            ← 静的ファイル追加OK
```

### 絶対に触ってはいけないファイル
```
# Agent A の領域（バックエンドデータ）
backend/scripts/                            ← 触るな
backend/app/tasks/                          ← 触るな
backend/app/services/crawling/              ← 触るな
backend/app/services/media_extraction.py    ← 触るな

# Agent C の領域（スコアリング）
backend/app/services/ranking/               ← 触るな
backend/app/api/endpoints/rankings.py       ← 触るな
backend/app/services/competitive/           ← 触るな
backend/app/services/prediction/            ← 触るな

# バックエンド全般
backend/                                    ← 一切触るな
```

### APIレスポンスのフィールド名に注意
```
バックエンド (snake_case)    フロントエンド
─────────────────────────   ─────────────
image_url                   imageUrl
video_url                   videoUrl
snapshot_url                snapshotUrl
thumbnail_url               thumbnailUrl
creative_type               creativeType
destination_url             destinationUrl
hit_score                   hitScore
score_breakdown             scoreBreakdown
estimation_method           estimationMethod
days_running                daysRunning
is_still_running            isStillRunning

→ 両方を || で受ける:
  imageUrl={data.image_url || data.imageUrl}
```

### スタイリング規則
- Tailwind CSS のみ使用（カスタムCSS追加NG）
- フォントサイズ: `text-[11px]`, `text-[12px]`, `text-[13px]` 等の既存パターンに合わせる
- カラー: `#4A7DFF`（プライマリ青）, `text-gray-900`, `text-gray-400` 等
- `next/image` は使わない → 通常の `<img>` タグ
- `e.stopPropagation()` でボタンクリック時の行クリック伝播を防止

## 作業ディレクトリ
`C:/Users/ishit/ads_library/frontend`

## 完了報告
作業が終わったら `B/status.md` を更新すること。
