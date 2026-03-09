# A41: Volume Gap Investigation + Recovery

## 目的
「広告数が足りない」原因を定量で特定し、回復施策を実装する。

## タスク
1. 直近7日で `query x platform x country` の取得件数を監査
 - Metaは `facebook` と `instagram` を分離して集計
2. `GLP-1` など指定キーワードで取得ゼロ/低件数の原因分類
3. 低件数時の再試行戦略（補助クエリ・媒体分散）を実装
4. 回復結果を `before/after` でレポート化

## 完了条件
- [ ] 低件数の主因が分類済み
- [ ] 回復ロジックで件数が改善
- [ ] Instagram の件数不足が可視化・改善される
- [ ] 監査レポートが日次で再実行可能

## 対象
- `backend/scripts/*crawl*`
- `backend/scripts/audit_ads_volume_errors.py`
