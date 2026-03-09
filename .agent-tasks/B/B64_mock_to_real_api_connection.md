# B64: モックデータ→実API接続（20+箇所）

## 優先度: 🅱️ B（重要）

## 問題
- 20以上のフロントエンドコンポーネントがハードコードされたモックデータを使用
- 実APIが存在するにもかかわらず接続されていない
- ユーザーに実データが表示されない

## 対象ファイル（主要）
- `frontend/src/components/ActivityFeed.tsx` — API未実装コメントあり
- `frontend/src/components/AdTimeline.tsx` — モックデータ使用中
- `frontend/src/components/AdvertiserProfile.tsx` — モックプレースホルダー
- `frontend/src/components/ElementAnalysis.tsx` — 5+ TODO項目
- `frontend/src/components/SavedScenarios.tsx` — モックデータ全体
- `frontend/src/components/ScenarioBuilder.tsx` — 複数TODO API呼び出し
- `frontend/src/components/SuccessFailureAnalysis.tsx` — モックデータ+TODO

## タスク

### Task 1: API接続ポイント調査
- 全コンポーネントの `TODO` / `mock` / `ダミー` コメントを検索
- 対応するバックエンドAPIエンドポイントの存在確認
- APIが未実装の場合はAgent Cに連携依頼

### Task 2: 共通API呼び出しパターン適用
- `frontend/src/lib/api.ts` の既存フェッチ関数を活用
- ローディング状態・エラー状態の表示
- 空データ時の空状態(Empty State)表示

### Task 3: 段階的置換（優先順位）
1. **ActivityFeed** → `/api/notifications` or `/api/activity`
2. **AdTimeline** → `/api/ads/{id}/timeline`
3. **AdvertiserProfile** → `/api/ads/advertiser/{name}`
4. **ElementAnalysis** → `/api/rankings/analysis`
5. **SuccessFailureAnalysis** → `/api/rankings/hit-analysis`
6. 残りのコンポーネント

### Task 4: フォールバック処理
- API接続失敗時はモックデータにフォールバック（開発時のみ）
- 本番環境ではエラー状態を表示

## 完了条件
- [ ] モックデータ使用箇所が0件（TODO検索結果0件）
- [ ] 各コンポーネントがローディング・エラー・空状態を適切に表示
- [ ] API接続で実データが表示される
- [ ] APIが未実装の箇所はAgent Cへの連携チケットが作成済み

## 連携
- Agent C (C61/C62): 不足APIエンドポイントの実装依頼
- API_CONTRACT_REGISTRY.md の契約に準拠すること
