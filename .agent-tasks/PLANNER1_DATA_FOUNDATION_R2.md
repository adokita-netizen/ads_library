# Planner 1: DATA FOUNDATION — Round 2
# 担当: Agent A (データ基盤) + Agent D (メディア・クロール)
# 更新: 2026-03-01

## ★ Round 1 完了サマリー ★

### Agent A 完了分
- [x] A1-A7: サムネイル修復, メトリクス収集, データ品質, 鮮度管理, データ補完, 構造解析, 新データ分析
- [x] A33-A36: コード品質改修 (database.py, config.py, lambda_handler.py, sqs_ecs_trigger.py)
- 成果: 176件の広告データの基本項目は90%以上充填済み

### Agent D 完了分
- [x] D1-D6: メディア品質, クローリング改善, 画像プロキシ, サムネイル再取得, フレッシュクロール, メディアパイプライン
- [x] D26-D32: Playwright最適化, クロールスケジューラ, メディアバリデーション, セッション/リトライ, リソースリーク, データ整合性, レート制限
- 成果: 176件のimage_url=100%, video=98件, サムネイルキャッシュ済み

---

## Round 2 タスクマップ

```
Agent A:                          Agent D:
A-R2-1 データ品質修正 (P0)         D-R2-1 定期クロール (P0)
  ↓                                 ↓
A-R2-2 デルタ計算 (P0)             D-R2-2 動画処理 (P0)
  ↓                                 ↓
A-R2-3 パイプライン一括 (P1)       D-R2-3 メディア精度 (P1)
  ↓                                 ↓
A-R2-4 DBリトライ (P0/CI)          D-R2-4 LPクローラ (P1)
  ↓                                 ↓
A-R2-5 メタデータ検証 (P0/CI)      D-R2-5 オーケストレータ (P2)
  ↓                                 ↓
A-R2-6 アラートエンジン (P2)       D-R2-6 動画解析 (P2)
```

## 実行順序（推奨）

### Day 1: 基盤修正
```
Agent A: A-R2-1 → A-R2-4 (並行可)
Agent D: D-R2-1 → D-R2-2 (並行可)
```

### Day 2: データ充実
```
Agent A: A-R2-2 → A-R2-3
Agent D: D-R2-3
```

### Day 3: 品質向上
```
Agent A: A-R2-5
Agent D: D-R2-4
```

### Day 4-5: Phase 2
```
Agent A: A-R2-6
Agent D: D-R2-5 → D-R2-6
```

## クロスエージェント連携

### A → D
- A-R2-1 でcreative_type NULL を発見 → D に fix_creative_types.py 実行を依頼
- A-R2-3 でクロール後の分析パイプライン → D-R2-1 のクロール完了後に実行

### D → A
- D-R2-1 で新規広告クロール → A に classify_ads, fix_titles 等を依頼
- D-R2-4 で LP メタ情報取得 → A が ad_metadata 品質スコアに反映

### A → C (Planner 2)
- A-R2-2 でデルタフィールド追加 → C に pro-ranking API のレスポンスに含めるよう依頼
- A-R2-5 でバリデーション結果 → C がスコア再計算の入力品質確認に利用

### D → C (Planner 2)
- D-R2-2 で duration_seconds 追加 → C がスコア計算に動画長を加味
- D-R2-4 で lp_status 取得 → C の既存 lp_status ロジックと統合

## 完了基準 (Round 2 End)

- [ ] 全176件の ad_metadata 必須キー欠落: 0件
- [ ] view_count_increase, spend_increase: 全レコードで計算済み
- [ ] 定期クロールが動作し、新規広告 50件以上追加
- [ ] 動画広告の duration_seconds: 90%以上取得済み
- [ ] LP のステータス (alive/dead): 全 destination_url で確認済み
- [ ] DB接続リトライが統一され、テスト済み
- [ ] metadata バリデーションスクリプトが daily 実行可能

## 注意事項
- database.py の structlog バグは Agent D が修正済み (COORDINATION_LOG 参照)
- logger.warning("msg", key=val) → logger.warning("msg key=%s", val) に統一すること
