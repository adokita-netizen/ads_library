# Agent B: 指示書

## あなたの役割
フロントエンドエンジニア。
UI/UX改善・ダッシュボード構築を担当する。

## ★ 現在の方針 (Round 2) ★
**PLANNER3_FRONTEND_E2E_R2.md + B_R2_*.md を参照して作業すること。**
Round 2 タスク (B-R2-1〜6) を優先。ダークモード→テーブルUX→Phase 2。

---

## タスク一覧

### 済
- ~~B1: クリエイティブビューワー~~
- ~~B2: トレンドレーダー / 勝ちパターン分析~~
- ~~B3: 分析ダッシュボード強化~~
- ~~B4: 新API連携~~
- ~~B5: 広告詳細モーダル & UX改善~~
- ~~B6: LP遷移先表示 & ダッシュボード改善~~
- ~~B7: 画像表示修正~~
- ~~B8: クリエイティブ分析ダッシュボード~~
- ~~B9: クロールUI & ポリッシュ~~
- ~~B10: Production UI & Download~~
- ~~B11: Analytics Dashboard~~
- ~~B12: Ad Comparison & Similar Ads~~
- ~~B19: Pro Ranking Table~~ (コンポーネント作成済み、page.tsx統合は要確認)

### 済（検証完了）
- ~~B13: bookmarks_and_download~~ ✓
- ~~B14: ai_insights_ui~~ ✓
- ~~B15: lp_analysis_ui~~ ✓
- ~~B16: competitor_ui~~ ✓
- ~~B17: reports_ui~~ ✓
- ~~B18: precision_ui~~ ✓
- ~~B20: scenario_builder_ui~~ ✓
- ~~B21: advanced_filters_and_failure_analysis~~ ✓
- ~~B22: reports_and_export_ui~~ ✓
- ~~B23: realtime_dashboard~~ ✓
- ~~B24: ad_comparison_ui~~ ✓
- ~~B25: calendar_and_timeline~~ ✓
- ~~B26: team_collaboration~~ ✓
- ~~B27: settings_and_onboarding~~ ✓
- ~~B28: creative_brief_generator~~ ✓

### 継続改善タスク（B担当・追加）
`CONTINUOUS_IMPROVEMENT_BACKLOG.md` のうち、B担当分を優先実行する。

- ~~B45: CI-019 主要画面のローディング/空状態/失敗状態を統一（P0）~~ ✓
- ~~B46: CI-020 API遅延時のUIブロッキングを削減（P0）~~ ✓
- B47: CI-031 frontend最重要E2Eを `smoke` として固定（P0）
- ~~B48: CI-037 一覧画面の初回描画体感速度改善（P0）~~ ✓
- ~~B49: CI-053 クリティカル操作に二重送信防止を実装（P0）~~ ✓
- B50: CI-021 テーブル操作のE2E追加（P1）
- B51: CI-022 モバイル表示崩れの優先修正（P1）
- B52: CI-023 アクセシビリティ監査（P1）
- B53: CI-041 グラフ表示コンポーネントのエラー耐性向上（P1）
- B54: CI-045 検索条件のURL同期改善（P1）
- B55: CI-057 共通テーブルのカラム設定永続化（P1）
- B56: CI-049 コンポーネント単位の視覚回帰テスト導入（P2）

着手順（推奨）:
1. B45
2. B46
3. B47
4. B48
5. B49

### 継続改善タスク（B担当・第3弾）
`CONTINUOUS_IMPROVEMENT_BACKLOG.md` の Batch 3 から B 担当分を追加。

- B70: CI-063 大規模テーブルの仮想スクロール最適化（P0）
- B71: CI-079 画面単位のError Boundaryを統一（P0）
- B72: CI-067 フィルタプリセット共有リンク機能を改善（P1）
- B73: CI-071 キーボードショートカット導線を追加（P1）
- B74: CI-083 低速回線想定のUI回帰シナリオ追加（P1）
- B75: CI-087 コンポーネント契約テスト（Props/型）を追加（P1）
- B76: CI-075 デザイン/コンポーネントトークン棚卸し（P2）

着手順（推奨）:
1. B70
2. B71
3. B72
4. B73
5. B74

### 継続改善タスク（B担当・第4弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 4 から B 担当分を追加。

- B80: CI-093 主要画面の初回データ取得をプリフェッチ最適化（P0）
- B81: CI-109 クリティカル導線のE2Eを毎日定時実行（P0）
- B82: CI-097 一覧/詳細の状態同期バグを回帰テスト化（P1）
- B83: CI-101 検索体験の遅延入力(debounce)を統一（P1）
- B84: CI-113 フィルタ条件保存の上限/整合バリデーション追加（P1）
- B85: CI-117 画面単位のローディング時間計測を可視化（P1）
- B86: CI-105 カラートークンのコントラスト検証自動化（P2）

着手順（推奨）:
1. B80
2. B81
3. B82
4. B83
5. B85

### 🅱️ ABC優先度タスク（2026-03-05 追加）

**Priority B（重要）:**
- B64: モックデータ→実API接続（20+箇所のモック除去）
- B65: ScenarioBuilder API統合（A/Bテストシナリオの実データ接続）
- B66: SavedScenarios永続化（DB保存/読み込み実装）
- B67: フロントエンドバグ修正（BUG-2,3,4修正）
- B68: E2Eテスト全通し確認（7テストスイート全パス）

着手順（推奨）:
1. **B64**（最大インパクト：20+箇所のモック除去）
2. B67（バグ修正は小さいが即効果あり）
3. B65
4. B66
5. B68

### 継続改善タスク（B担当・第6弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 6 から B 担当分を追加。

- B87: CI-130 Error Boundaryのエラーログをバックエンドに送信（P0）
- B88: CI-134 ServiceWorkerによるオフラインキャッシュ基盤導入（P1）
- B89: CI-138 Storybook による UI コンポーネントカタログ構築（P2）
- B90: Creative Library の閲覧/DL導線を再設計し、ZIP一括DLを標準化（P0）
- B91: Creative Library の素材状態とDL信頼性をUIで明示（P0）
- B92: CR / LP visibility と DL 完了状態を UI 表示（P0）
- B93: LP preview と DL 結果サマリまで含めて Creative Library 導線を完成（P0）
- B94: Creative Library の E2E smoke と empty state を固定（P0）
- B95: LP 解決先とドメイン信頼性の UI 表示を追加（P1）
- B96: 復旧待ち広告フィルタと manual retry 導線の UI 受け皿を整備（P1）
- B97: Creative Library の回帰監視ダッシュボードを追加（P1）

着手順（推奨）:
1. B90
2. B91
3. B92
4. B93
5. B87

### Phase 2（プロダクト強化）— 完了
- ~~B41: onboarding_empty_states~~ ✓
- ~~B42: notification_center~~ ✓
- ~~B43: ai_chat_interface~~ ✓
- ~~B44: dashboard_customization~~ ✓

### コード品質改修（完了）
- ~~B37: メモリリーク修正~~ ✓
- ~~B38: エラーハンドリング改善~~ ✓
- ~~B39: パフォーマンス最適化~~ ✓
- ~~B40: TypeScript型安全性強化~~ ✓

---

## 作業開始前に必ず読むファイル
```
frontend/src/components/dashboard/HitAdAnalysisView.tsx
frontend/src/components/dashboard/AdLibraryTable.tsx
frontend/src/components/analysis/ProductDetailModal.tsx
frontend/src/components/common/CreativeViewer.tsx
frontend/src/components/dashboard/TrendView.tsx
frontend/src/components/dashboard/ProRankingView.tsx
frontend/src/lib/api.ts
frontend/src/lib/constants.ts
frontend/src/lib/format.ts
frontend/src/types/index.ts
```

---

## ★★★ コンフリクト防止ルール ★★★

### 触っていいファイル（Agent B の専有領域）
```
frontend/src/components/
frontend/src/lib/
frontend/src/types/          ← 型定義の追加OK（既存削除NG）
frontend/src/app/
frontend/public/
frontend/next.config.js
frontend/package.json
frontend/tailwind.config.js
```

### 絶対に触ってはいけないファイル
```
backend/                     ← 一切触るな
docker/                      ← 触るな
terraform/                   ← 触るな
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
- フォントサイズ: `text-[11px]`, `text-[12px]`, `text-[13px]` 等の既存パターン
- カラー: `#4A7DFF`（プライマリ青）, `text-gray-900`, `text-gray-400`
- `next/image` は使わない → 通常の `<img>` タグ
- `e.stopPropagation()` でボタンクリック時の行クリック伝播を防止

## 作業ディレクトリ
`C:/Users/ishit/ads_library/frontend`

## 完了報告
作業が終わったら `B/status.md` を更新すること。
