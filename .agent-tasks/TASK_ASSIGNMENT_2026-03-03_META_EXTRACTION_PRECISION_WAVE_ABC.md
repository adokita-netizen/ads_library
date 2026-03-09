# Task Assignment (2026-03-03) — Meta Extraction Precision Wave

## ゴール
Meta広告ライブラリー粒度（ad_id単位）で、クリエイティブ・動画・本文を高精度に取得する。

## 配分
- A47: `A47_meta_creative_extraction_precision_dataops.md`
- C49: `C49_meta_ad_granularity_extraction_api.md`
- B53: `B53_meta_extraction_quality_console.md`

## 実行順
1. C49: ad_id抽出API・再抽出API契約を固定
2. A47: 抽出監査/再抽出キュー/品質スコアを実装
3. B53: 取得状態と再抽出運用UIを実装

## DoD
- [ ] ad_id単位で抽出状態をAPI/UIで追跡できる
- [ ] 低品質/欠損素材の再抽出が回る
- [ ] 契約テスト + E2Eで再発防止

