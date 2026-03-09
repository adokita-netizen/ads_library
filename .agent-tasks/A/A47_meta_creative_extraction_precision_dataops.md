# A47: Meta Creative/Video Extraction Precision (DataOps)

## 目的
Meta広告ライブラリーの `ad_id` 粒度で、画像/動画/本文の抽出成功率を引き上げる。

## タスク
1. 抽出監査データ基盤
- `ad_id` 単位で抽出結果を記録
- `extract_source` (`api_render_ad`, `browser_overlay`, `snapshot_parse`, `fallback`) 保存
- `extract_quality_score`（解像度/長さ/欠損率）を算出

2. 低品質素材の自動再抽出キュー
- 条件: 小さすぎる画像、空動画URL、本文欠損
- 再抽出時は優先順を固定（render_ad優先）

3. 粒度監査レポート
- `ad_id` ごとの `creative_complete` 判定
- 失敗理由ランキングを日次出力

## 完了条件
- [ ] ad_id単位の抽出結果が追跡できる
- [ ] 低品質素材が自動再抽出される
- [ ] 日次で失敗要因が可視化される

