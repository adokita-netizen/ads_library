# Planner 3: FRONTEND E2E VERIFICATION & POLISH
# 担当: Agent B (フロントエンド)

## あなたの使命
**22のビュー全てが実データで正しく表示されることを保証する。**
新しいビューは作らない。既存ビューを「検証・修正・磨く」。

---

## 現状把握

### 既にあるもの（膨大）
- ✅ 22のViewType: pro-database, search, trend, analysis, 等
- ✅ 全てルーティング済み (page.tsx renderView)
- ✅ 全てlazy import (dynamic import, SSR無効)
- ✅ Sidebar: 4セクション21項目、全ナビゲーション動作
- ✅ ConnectivityBanner: バックエンド接続チェック
- ✅ ProRankingView/Table/SmartSearchBar: 作成済み
- ✅ HitAdAnalysisView: 13回の修正を経て機能豊富
- ✅ AdDetailModal, CreativeViewer, 各種パネル
- ✅ api.ts: Axios + リトライ + 認証
- ✅ ビルド成功 (最終: 2026-03-01 09:37)

### 問題（推定）
- 22ビュー中、実データで動作確認されたのは一部のみ
- APIが返すフィールド名とフロント側の期待にズレがある可能性
- バックエンドが500を返すケースのUI表示が未確認
- 一部ビューはAPIが未実装で空状態になる可能性

---

## Phase 1: 全ビュー動作確認 (Day 1)

### Task 1-1: ビルド確認
```bash
cd C:/Users/ishit/ads_library/frontend
npx next build --no-lint
```
エラーがあれば修正。型エラーが多い場合は優先度順に対応。

### Task 1-2: 全22ビューの動作チェック

バックエンドを `http://localhost:8000` で起動した状態で、
`npm run dev` でフロントを起動し、全ビューを確認。

以下のチェックリストを埋める:

#### Priority 1: メインビュー（最初に見える画面）
| View | Route | 表示 | データ | 問題 |
|------|-------|------|--------|------|
| PRO DATABASE | pro-database | ? | ? | ? |
| 検索 | search | ? | ? | ? |
| ヒット広告分析 | hit-ads | ? | ? | ? |

#### Priority 2: 分析ビュー
| View | Route | 表示 | データ | 問題 |
|------|-------|------|--------|------|
| トレンド | trend | ? | ? | ? |
| 分析 | analysis | ? | ? | ? |
| LP分析 | lp-analysis | ? | ? | ? |
| 競合インテリジェンス | competitive | ? | ? | ? |
| 比較ツール | compare | ? | ? | ? |

#### Priority 3: ツールビュー
| View | Route | 表示 | データ | 問題 |
|------|-------|------|--------|------|
| AI専門家 | ai-expert | ? | ? | ? |
| クリエイティブ生成 | creative | ? | ? | ? |
| シナリオ作成 | scenario | ? | ? | ? |
| ブリーフ作成 | creative-brief | ? | ? | ? |

#### Priority 4: 管理ビュー
| View | Route | 表示 | データ | 問題 |
|------|-------|------|--------|------|
| 自社広告管理 | meta-ads | ? | ? | ? |
| レポート | reports | ? | ? | ? |
| カレンダー | calendar | ? | ? | ? |
| お知らせ | alerts | ? | ? | ? |
| コレクション | collections | ? | ? | ? |
| チームスペース | team | ? | ? | ? |
| キャンペーン | campaign | ? | ? | ? |
| マイリスト | mylist | ? | ? | ? |
| VAAPストア | store | ? | ? | ? |
| 設定 | settings | ? | ? | ? |

### チェック基準
- **表示**: コンポーネントがレンダリングされるか（白画面/エラーでないか）
- **データ**: API呼び出しが成功し、データが表示されるか
- **問題**: 目視で分かる問題（レイアウト崩れ、文字化け、無限ローディング等）

---

## Phase 2: PRO DATABASE ビュー完成 (Day 2)

### Task 2-1: ProRankingView 統合確認
`page.tsx` と `Sidebar.tsx` で PRO DATABASE が正しく統合されているか確認。
B19 status.md に書かれた統合手順:

1. `page.tsx`:
   - `import ProRankingView` がある
   - `ViewType` に `"pro-database"` がある
   - デフォルトが `"pro-database"`
   - `renderView()` の switch に case がある

2. `Sidebar.tsx`:
   - `{ id: "pro-database", label: "PRO DATABASE", icon: "chart", badge: "HOT" }` がある

### Task 2-2: PRO DATABASE データフロー確認

```
ProRankingView
  → /rankings/genre-master (サイドバーのジャンル一覧)
  → ProRankingTable
    → /rankings/pro-ranking (テーブルデータ)
  → SmartSearchBar
    → /rankings/smart-autocomplete (検索サジェスト)
```

各APIが実際にデータを返し、テーブルに正しく表示されることを確認。

### Task 2-3: 数値フォーマット確認
PRO DATABASEテーブルの各カラム:
- 再生数: `10,997` / `+10,997` (カンマ区切り、増分は+付き)
- 消化額: `¥43,988` (円記号付き)
- 動画長: `0:29` (分:秒)
- 大きい数値: `1.2万` (万単位)

### Task 2-4: HITLINE表示確認
- ヒットライン超え行: 金色背景 + HITLINEバッジ
- ヒットスコアバッジ: 色分け（赤/黄/青）

---

## Phase 3: 壊れたビューの修正 (Day 3-4)

### Task 3-1: APIエラー時のフォールバック

全ビューで以下のパターンを確認:
1. **ローディング中**: スケルトンUI or スピナーが表示される
2. **APIエラー**: エラーメッセージ + 再試行ボタンが表示される
3. **データ空**: 「データがありません」メッセージが表示される
4. **API未実装 (404)**: フォールバック表示がある

### Task 3-2: 画像/動画表示修正

全ビューでメディア表示を確認:
- サムネイル: `/api/v1/media/thumbnail/{ad_id}` プロキシURL使用
- フォールバック: proxy → thumbnail → image_url → snapshot_url → プレースホルダー
- `loading="lazy"` が設定されている
- `onError` ハンドラーがある

### Task 3-3: レスポンシブ確認
- デスクトップ (1920px)
- タブレット (768px)
- モバイル (375px)

PRO DATABASE と HitAdAnalysisView を最低限確認。

---

## Phase 4: UXポリッシュ (Day 5)

### Task 4-1: ナビゲーションの整理
22ビューは多すぎる可能性。以下を検討:
- 未実装/空のビューは非表示にする（コメントアウト）
- 「NEW」バッジの見直し
- デフォルトビューの確認（pro-database で正しいか）

### Task 4-2: コンソールエラー確認
DevTools Console を開いて:
- React warning
- API 404/500 エラー
- TypeScript 型エラー
- 不要な console.log

### Task 4-3: パフォーマンス確認
- 初期ロード時間
- lazy import が正しく効いているか
- 不要なAPI呼び出しがないか

---

## ファイル所有権（厳守）

### Agent B が触れるファイル
```
frontend/src/components/  (全コンポーネント)
frontend/src/lib/         (ユーティリティ)
frontend/src/types/       (型定義の追加のみ)
frontend/src/app/         (ページ)
frontend/public/          (静的ファイル)
frontend/next.config.js
frontend/package.json
frontend/tailwind.config.js
```

### 絶対触るな
```
backend/                  ← Planner 1 & 2 の領域
docker/                   ← Planner 1 の領域
terraform/                ← インフラ領域
```

---

## Planner 2 (API) との連携ポイント

以下の場合は `COORDINATION_LOG.md` 経由で Planner 2 に連絡:

1. **APIレスポンスにフィールドが足りない**
   例: `/pro-ranking` に `duration_seconds` が無い → Planner 2 に追加依頼

2. **APIレスポンスの型が違う**
   例: `hit_score` が string で返るが number が必要 → Planner 2 に修正依頼

3. **新しいAPIが必要**
   → 既存105+エンドポイントに無いか先に確認。大抵はある。

---

## 完了基準

- [ ] `npx next build --no-lint` が成功
- [ ] PRO DATABASE ビューで実データがテーブル表示される
- [ ] 22ビュー中、白画面/クラッシュするビューが0
- [ ] 壊れたビューはエラーメッセージ表示 or フォールバック表示
- [ ] 画像/動画のフォールバックチェーンが動作
- [ ] コンソールにcriticalなエラーが無い

## 報告先
- `B/status.md` を更新
- クロスプランナー連絡: `.agent-tasks/COORDINATION_LOG.md` に記載
