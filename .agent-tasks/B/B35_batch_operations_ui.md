# B35: バッチ操作管理UI

## 目的
管理者が一括操作（メディア抽出、クロール、スコア再計算等）をUI上からトリガーできる管理画面。

## タスク

### 1. BatchOperationsPanel コンポーネント
- `frontend/src/components/dashboard/BatchOperationsPanel.tsx` を新規作成

#### 表示内容
- **操作カード** (グリッド表示):

  | 操作名 | API | 説明 |
  |-------|-----|------|
  | メディア一括抽出 | POST extract_media | pending広告のメディアを一括抽出 |
  | 広告クロール | POST crawl | キーワード指定で新規広告クロール |
  | スコア再計算 | POST compute_rankings | 全広告のヒットスコアを再計算 |
  | データヘルスチェック | GET data-health | DB品質サマリーを取得 |

- 各カード:
  - 操作名 + 説明
  - パラメータ入力 (limit数値、キーワードテキスト等)
  - 「実行」ボタン (確認ダイアログ付き)
  - 実行結果表示 (成功件数/エラー件数)
  - ローディングスピナー

### 2. 実行履歴パネル
- 直近の操作履歴をリスト表示
- ローカルストレージに保存 (最大20件)
- 各行: 操作名 / 実行日時 / 結果サマリー

### 3. ページ統合
- Settings ページ内のタブとして追加、または独立ページ `/admin`
- サイドバー: 「管理ツール」として追加

## API連携
```typescript
// Lambda direct invoke 相当のAPI
// C32/C31 が作成する各エンドポイントを呼ぶ

// 例: メディア一括抽出
const result = await fetchApi('/rankings/batch-extract-media', {
  method: 'POST',
  body: JSON.stringify({ limit: 50, statuses: ['pending'] }),
});
```

## 制約
- `frontend/src/components/dashboard/` にのみファイル作成
- 破壊的操作には必ず確認ダイアログを表示
- Tailwind CSS のみ
