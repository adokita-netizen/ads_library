# Agent A タスク: LP検証実行 & データ補完

## 背景
Agent CがLP到達性検証スクリプトを作成済み。実行して結果を確認する。
また、データヘルスレポートで判明した欠損フィールドを補完する。

## やること

### 1. LP到達性検証スクリプト実行
```bash
cd C:/Users/ishit/ads_library/backend && python scripts/check_lp_health.py
```
- 全176件のdestination_urlの到達性を検証
- 結果をad_metadataに記録
- 実行結果をサマリー報告

### 2. last_seen_at の補完
`backend/scripts/fix_last_seen_at.py` を新規作成。
- last_seen_at が NULL の広告（151件）に対して補完
- is_still_running == True の場合 → last_seen_at = 今日の日付
- is_still_running == False の場合 → last_seen_at = survival_checked_at の日付
- 両方ない場合 → last_seen_at = updated_at

### 3. longevity_class の全件付与
`backend/scripts/fix_longevity_class.py` を新規作成。
- longevity_class が未設定の165件に対して付与
- days_running に基づく分類:
  - 0-7日: "flash"
  - 8-30日: "short"
  - 31-90日: "medium"
  - 91日+: "long"
- ad_metadataに `longevity_class` を記録

### 4. 生存チェック改善版の実行
```bash
cd C:/Users/ishit/ads_library/backend && python scripts/check_ad_survival.py
```

## 制約
- INSTRUCTIONS.md のコンフリクト防止ルール厳守
- print文は英語のみ
- 新規スクリプトは `backend/scripts/` に作成
- 既存スクリプトの構造に合わせる
