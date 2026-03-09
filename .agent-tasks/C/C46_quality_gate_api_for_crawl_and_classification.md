# C46: Quality Gate API for Crawl + Classification

## 目的
クロール結果と分類結果に品質ゲートを入れて、低品質データの流入を防ぐ。

## タスク
1. `POST /rankings/quality-gate/evaluate` 追加
2. ゲート判定:
- 最低件数
- 必須項目充足率
- 画像品質スコア
- 分類信頼度
3. NG時は理由コードを返却し、再処理提案を返す
4. 契約テスト追加

## 完了条件
- [x] 品質ゲートの判定がAPI化される
- [x] NG理由が構造化で返る


