# Agent B タスク: 広告詳細モーダル & UX改善

## 方向性
テーブルに並んだ広告を「ざっと見る」体験は整った。
次は「気になった1件を深く見る」体験と、全体的なUXの底上げ。

## やってほしいこと（優先順に）

### 1. 広告詳細モーダル
テーブルの行をクリックしたら、その広告の全情報を見られるモーダルを作る。
- サムネイル/画像の大きな表示（動画URLがあればvideoタグ）
- タイトル、広告主、説明文の全文表示
- スコア内訳のビジュアル表示（既存のscore_breakdownデータを使う）
- メタ情報: creative_type, days_running, is_still_running, destination_url（リンク）
- estimated_spend, impressions等の数値データ
- destination_urlへの「LPを見る」ボタン
- モーダルは既存の ProductDetailModal.tsx のパターンを参考にしてよい
- 新コンポーネント `AdDetailModal.tsx` を dashboard/ に作成

### 2. ローディング & エラー状態の改善
- データ取得中のスケルトンUI（テーブル行のプレースホルダー）
- API失敗時のリトライボタン付きエラー表示
- 空データ時の分かりやすいメッセージ

### 3. レスポンシブ対応
- モバイル幅でもテーブルが崩れないようにする
- 小さい画面ではカード表示をデフォルトにする
- モーダルもモバイル対応

## 制約
- INSTRUCTIONS.md のコンフリクト防止ルール厳守
- バックエンドは一切触らない
- 外部ライブラリ追加不可（Tailwind CSSのみ）
- 既存コンポーネントのパターン（fetchApi使用等）に合わせる
- ビルド確認: `cd C:/Users/ishit/ads_library/frontend && npx next build --no-lint`
