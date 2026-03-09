# B66: SavedScenarios 永続化実装

## 優先度: 🅱️ B（重要）

## 問題
- SavedScenarios.tsxが全面的にモックデータを使用
- 保存したシナリオがページリロードで消える

## 対象ファイル
- `frontend/src/components/SavedScenarios.tsx`
- `frontend/src/lib/api.ts`

## タスク

### Task 1: API接続
- 保存済みシナリオ一覧取得: `GET /api/scenarios?saved=true`
- シナリオ保存: `POST /api/scenarios/{id}/save`
- シナリオ削除: `DELETE /api/scenarios/{id}`

### Task 2: ローカルステート→API同期
- モックデータ配列をuseState→useSWRまたはuseEffect+fetchに置換
- オプティミスティック更新の実装

### Task 3: UI改善
- ローディングスケルトン表示
- 保存成功/失敗のトースト通知
- 空リスト時の案内表示

## 完了条件
- [x] SavedScenarios内のモックデータが完全除去
- [x] ページリロード後もシナリオが永続化されている
- [x] CRUD操作がAPI経由で動作

## 連携
- B65 (ScenarioBuilder API統合) と同時に進行可能
