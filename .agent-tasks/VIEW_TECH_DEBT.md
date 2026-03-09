# 技術的負債視点 — 放置するとヤバいもの

## Critical: 今すぐ対処が必要

### 1. rankings.py が14,779行の神ファイル
**場所**: `backend/app/api/endpoints/rankings.py`
**問題**: 105+エンドポイントが1ファイルに集中。修正時のコンフリクトリスク極大。
**影響**: Agent C が触るたびに巨大diffが発生、レビュー不可能
**対策案**:
```
backend/app/api/endpoints/
  rankings/
    __init__.py          ← router定義
    core.py              ← pro-ranking, hit-ads, products
    analytics.py         ← dashboard-summary, genre-comparison, trends
    export.py            ← CSV/JSON/report export
    search.py            ← autocomplete, collections, filters
    scenario.py          ← scenario templates, generation
    competitive.py       ← creative-dna, hit-factors, winning-patterns
```
**優先度**: Phase 2 以降（今は機能優先）

### 2. media.py が99,578行
**場所**: `backend/app/api/endpoints/media.py`
**問題**: rankings.py 以上に巨大。何が入っているか把握困難。
**対策**: 同様に分割が必要

### 3. CORS が wildcard (*)
**場所**: `backend/app/main.py`
**問題**: 本番環境で `allow_origins=["*"]` はセキュリティリスク
**対策**: CloudFront ドメインのみ許可
```python
allow_origins=["https://d3qlbagx7gq5sp.cloudfront.net"]
```

### 4. APIキーがDB平文保存の可能性
**場所**: `backend/app/api/endpoints/settings.py` L444 `load_api_keys_from_db`
**確認**: Meta/OpenAI/Anthropic のAPIキーが暗号化されているか
**対策**: KMS or 環境変数に移行

---

## High: 早めに対処すべき

### 5. print文のエンコーディング問題
**Agent D INSTRUCTIONS より**: `print("動画抽出完了")` → cp932エラー
**場所**: 各スクリプト
**対策**: `PYTHONIOENCODING=utf-8` を環境変数に設定、または全print英語化

### 6. 同期/非同期の混在
**問題**:
- `SyncSessionLocal` と `AsyncSession` が共存
- Playwright は async だが media_tasks.py で `loop.run_until_complete()` で呼び出し
**リスク**: イベントループの二重起動、デッドロック
**対策**: worker は sync 統一 or async 統一

### 7. JSON ファイルベースのストレージ
**場所**:
- `backend/data/collections.json` — 検索条件保存
- `backend/data/saved_searches.json` — 保存済み検索
**問題**: Lambda の `/tmp` は一時的。複数Lambda呼び出しでデータ消失。
**対策**: DB テーブルに移行

### 8. ハードコードされたURL/ID
**確認が必要な場所**:
- CloudFront distribution ID
- ECR リポジトリURL
- RDS ホスト名
- S3 バケット名
**対策**: 全て環境変数 or Terraform output 参照

---

## Medium: 時間があるときに

### 9. テストがない（推定）
**確認**: `tests/` ディレクトリの状態
- pytest, factory-boy, respx は requirements.txt にある
- 実際にテストが書かれているか不明
**対策**: 最低限 E2E API テストを追加

### 10. alembic マイグレーション状態
**確認**: `alembic/versions/` に何個のマイグレーションがあるか
- モデル変更とマイグレーションが同期しているか
- 本番DBに未適用のマイグレーションがないか

### 11. 依存関係の重さ
**問題**: requirements.txt に PyTorch, Whisper, YOLOv8, Transformers, Diffusers が全部入り
- Lambda デプロイパッケージが巨大になる
- Lambda は軽量であるべき（API のみ）
**確認**: Lambda にCVML系が不要なら分離

### 12. エラーハンドリングの一貫性
**問題**: 各エンドポイントで try/except の粒度がバラバラ（推定）
- 一部は生の500を返す
- 一部は `{"detail": "..."}` を返す
- フロントが統一的に処理できない

### 13. ログの構造化
**場所**: `backend/app/main.py` — structlog 使用
**確認**: 全サービスで統一的にログが出ているか
**確認**: CloudWatch Logs Insights でクエリ可能か

---

## Low: 将来的に

### 14. フロントの HitAdAnalysisView.tsx が肥大化
**問題**: 13回以上の修正を経て巨大化（status.md 参照）
- タスク #3, #5, #6, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17 で修正
**対策**: 責務分離（データフェッチ/フィルター/テーブル/チャートを分割）

### 15. 22ビューの実用性
**問題**: 22ビュー中、実際に使うのは5-8個程度と推測
- 残りはプレースホルダー or 半完成
**対策**: 使わないビューは非表示にする

### 16. React Query のキャッシュ戦略
**確認**: staleTime, cacheTime の設定
**問題**: 全APIが毎回フェッチだと遅い
**対策**: ランキングデータは5分キャッシュ等

---

## 負債マップ（影響度 × 修正コスト）

```
影響度 高 │ [3.CORS]    [7.JSON保存]  [1.神ファイル]
          │ [4.API平文]               [2.media巨大]
          │
          │ [6.sync混在] [5.cp932]    [11.依存重い]
          │
影響度 低 │ [10.alembic] [12.エラー]  [14.肥大tsx]
          │              [13.ログ]    [15.22ビュー]
          └────────────────────────────────────────
            修正コスト低   修正コスト中   修正コスト高
```

**推奨順序**: 3 → 4 → 7 → 5 → 6 → 残り
