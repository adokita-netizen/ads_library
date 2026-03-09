# B65: ScenarioBuilder API統合

## 優先度: 🅱️ B（重要）

## 問題
- ScenarioBuilder.tsxに複数のTODO API呼び出しが残っている
- A/Bテストシナリオ機能が実データで動作しない

## 対象ファイル
- `frontend/src/components/ScenarioBuilder.tsx`
- `frontend/src/lib/api.ts`

## タスク

### Task 1: API呼び出し実装
- シナリオ作成: `POST /api/scenarios`
- シナリオ一覧: `GET /api/scenarios`
- シナリオ更新: `PUT /api/scenarios/{id}`
- シナリオ削除: `DELETE /api/scenarios/{id}`
- シナリオ実行: `POST /api/scenarios/{id}/run`

### Task 2: フォーム→APIペイロード変換
- UIフォームの入力値をAPI仕様に合わせて変換
- バリデーションエラーのUI表示

### Task 3: 結果表示
- シナリオ実行結果のリアルタイム表示
- 比較グラフ・テーブルの実データ反映

## 完了条件
- [ ] ScenarioBuilder内のTODOコメントが0件
- [ ] シナリオCRUD操作が実APIで動作
- [ ] エラー時のユーザーフィードバックが適切

## 連携
- Agent C: scenarios APIエンドポイント(C19)の実装状況確認
