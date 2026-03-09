# Quality Gate Checklist

最終更新: 2026-03-01

## 目的
各エージェントのタスク完了時に満たすべき品質基準を定義する。
「完了」の定義を統一し、残タスクの漏れを防止する。

---

## Gate 1: コード品質（全エージェント共通）

- [ ] Linter エラーゼロ（Python: ruff/flake8, TypeScript: ESLint）
- [ ] 型エラーゼロ（Python: mypy --ignore-missing-imports, TypeScript: tsc --noEmit）
- [ ] 未使用 import が無い
- [ ] ハードコードされた秘密情報（API キー、パスワード）が無い
- [ ] TODO/FIXME/HACK コメントに issue 番号が付いている
- [ ] print デバッグが残っていない（logger 使用を推奨）

---

## Gate 2: Agent A (Data Foundation)

### バッチスクリプト
- [ ] `--dry-run` オプションがある（データ変更スクリプト）
- [ ] 冪等性: 同じスクリプトを2回実行しても結果が変わらない
- [ ] `session.rollback()` が例外ハンドラ内にある
- [ ] `flag_modified(ad, "ad_metadata")` が ad_metadata 更新後にある
- [ ] 処理件数のサマリーログ出力がある
- [ ] 英語のみの print 文（cp932 対策）

### DB 変更
- [ ] Alembic マイグレーションファイルがある（カラム追加時）
- [ ] ロールバック手順が明文化されている
- [ ] インデックスが必要なカラムに追加されている
- [ ] NOT NULL 制約は既存データとの互換性を確認済み

### テスト
- [ ] smoke テストで主要パスが通る
- [ ] エッジケース（NULL データ、空テーブル）を処理できる

---

## Gate 3: Agent B (Frontend)

### ビルド
- [ ] `npx next build --no-lint` が成功する
- [ ] First Load JS が 160kB 以下
- [ ] 新規 `any` 型の使用が無い（既存の型定義を使用）
- [ ] `next/image` を使っていない（`<img>` タグを使用）

### コンポーネント
- [ ] ローディング状態がある（スケルトン UI）
- [ ] エラー状態がある（再試行ボタン付き）
- [ ] 空状態がある（データ 0 件時のメッセージ）
- [ ] レスポンシブ対応（sm/md/lg のブレークポイント）
- [ ] Tailwind CSS のみ使用（カスタム CSS 追加なし）
- [ ] `e.stopPropagation()` がボタン onClick にある（テーブル行内）

### API 連携
- [ ] API フィールドは `||` フォールバック（snake_case || camelCase）
- [ ] API 失敗時にフォールバック表示がある
- [ ] AbortController / タイムアウトがある
- [ ] debounce が検索入力にある（250ms 以上）

### UX
- [ ] キーボード操作（Escape でモーダル閉じる、Enter で送信）
- [ ] 二重送信防止（ボタン disabled + loading spinner）
- [ ] toast 通知（成功/失敗のフィードバック）

---

## Gate 4: Agent C (API / Scoring)

### API エンドポイント
- [ ] OpenAPI スキーマが生成可能（FastAPI の自動生成）
- [ ] ページネーションがある（limit/offset, MAX_PAGE_SIZE=100）
- [ ] 入力バリデーションがある（Pydantic スキーマ）
- [ ] エラーレスポンスが統一形式 `{"detail": str, "code": str}`
- [ ] N+1 クエリが無い（joinedload/selectinload 使用）
- [ ] EXPLAIN ANALYZE でフルスキャンが無いことを確認

### スコアリング
- [ ] hit_score の計算ロジックが説明可能（シグナル別スコア）
- [ ] score_breakdown がレスポンスに含まれる
- [ ] 閾値変更の影響範囲を事前確認済み

### セキュリティ
- [ ] SQL インジェクション対策（パラメータバインド使用）
- [ ] パストラバーサル対策（ファイルパスのサニタイズ）
- [ ] レート制限の検討

---

## Gate 5: Agent D (Media / Crawling)

### クローリング
- [ ] 重複ガード（同一 ad_id のクロール重複防止）
- [ ] レートリミット対応（429 時の Retry-After 遵守）
- [ ] トークン期限切れ対応（401 時の critical ログ）
- [ ] タイムアウト設定がある
- [ ] robots.txt / 利用規約の遵守を確認

### メディア処理
- [ ] Playwright の `browser.close()` が `finally` ブロック内にある
- [ ] ファイルサイズ上限がある（画像: 10MB, 動画: 100MB）
- [ ] 画像品質チェック（最小解像度 200x200）
- [ ] S3 アップロード後の URL 検証

### データ整合性
- [ ] `_merge_crawled_data()` パターン使用（NULL で上書きしない）
- [ ] `flag_modified(ad, "ad_metadata")` 使用
- [ ] Agent A/C の ad_metadata キーを上書きしない
- [ ] 英語のみの print 文（cp932 対策）

---

## デプロイ前チェック（全体）

### 必須
- [ ] 全エージェントの Gate が通過
- [ ] 統合スモークテスト通過（`integration_smoke.sh`）
- [ ] DB マイグレーションが適用済み
- [ ] 環境変数の差分確認
- [ ] CloudFront キャッシュ無効化計画

### 推奨
- [ ] パフォーマンスバジェット確認
- [ ] API レスポンスサイズ確認
- [ ] バンドルサイズ確認
- [ ] エラー率ベースライン記録

---

## 使い方

1. タスク完了時に、該当 Gate のチェックリストを確認
2. 全項目を満たしたら `status.md` に「Gate X 通過」を記録
3. 未達項目がある場合は理由と対策を記録
4. デプロイ前に全体チェックを実施
