# Agent B タスク: LP遷移先表示 & ダッシュボード精度改善

## 方向性
ユーザーが広告を見て「このLPどんなページ？」とすぐ確認できるようにする。
また、ダッシュボード全体でデータの信頼性が一目で分かるようにする。

## やってほしいこと（優先順に）

### 1. テーブルにLP遷移先カラム追加（最優先）
HitAdAnalysisView.tsx のテーブルに destination_url を表示するカラムを追加。
- URLを短縮表示（ドメイン部分のみ、例: "example.com"）
- クリックで新しいタブでLPを開く（target="_blank", rel="noopener noreferrer"）
- ツールチップで完全URLを表示
- アイコン付き（外部リンクアイコン: ↗ や SVGアイコン）
- URLがない場合は「-」表示

### 2. 広告詳細モーダルにLP情報統合
B5で作ったAdDetailModal（もし作成済みなら）に：
- destination_urlの完全表示 + 「LPを開く」ボタン
- 説明文（description）の全文表示
- もしAPIから `lp_status` が取れれば、LP到達性ステータスも表示（200=緑, 404=赤）

### 3. サマリーカードにC5のdashboard-summary APIを統合
`GET /rankings/dashboard-summary` から取得したデータをサマリーカードに表示：
- 総広告数、アクティブ広告数
- ヒット数、メガヒット数
- 平均スコア
- トップジャンル、トップクリエイティブタイプ
- 現在のローカル計算をAPI呼び出しに置き換えるか、併用する

### 4. ジャンル比較チャート
`GET /rankings/genre-comparison` のデータを使って、ジャンル別の比較チャートを追加。
- 横棒グラフ: 各ジャンルの広告数 or 平均スコア
- サマリーエリアかタブ内に配置

## 制約
- INSTRUCTIONS.md のコンフリクト防止ルール厳守
- バックエンドは一切触らない
- 外部ライブラリ追加不可
- ビルド確認: `cd C:/Users/ishit/ads_library/frontend && npx next build --no-lint`
