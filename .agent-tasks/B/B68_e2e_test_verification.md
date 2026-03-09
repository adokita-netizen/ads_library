# B68: E2Eテスト全通し確認・修正

## 優先度: 🅱️ B（重要）

## 問題
- 7つのE2Eテストスイートが存在するが、全通し確認が未実施
- フロントエンド変更により既存テストが壊れている可能性

## 対象ファイル
- `frontend/e2e/smoke.spec.ts` (@smoke)
- `frontend/e2e/table-operations.spec.ts` (@table)
- `frontend/e2e/state-sync.spec.ts` (@state)
- `frontend/e2e/visual-regression.spec.ts` (@visual)
- `frontend/e2e/slow-network.spec.ts` (@slow)
- `frontend/e2e/contrast-tokens.spec.ts` (@a11y-contrast)
- `frontend/e2e/crawl-search.spec.ts`

## タスク

### Task 1: 全テスト実行
```bash
cd frontend
npx playwright test --reporter=html
```

### Task 2: 失敗テストの修正
- セレクタ変更による失敗 → セレクタ更新
- API変更による失敗 → モック/フィクスチャ更新
- タイミング問題 → waitFor/retry追加

### Task 3: テストレポート確認
- 全テストがGreenになることを確認
- ビジュアルリグレッションのスナップショット更新

### Task 4: CI統合確認
- GitHub ActionsでE2Eテストが自動実行されることを確認

## 完了条件
- [ ] 7テストスイート全てがPASS
- [ ] テストレポートが生成される
- [ ] CI上での実行が確認される

## 制約
- テスト対象のコンポーネントは変更しない（テストコードのみ修正）
