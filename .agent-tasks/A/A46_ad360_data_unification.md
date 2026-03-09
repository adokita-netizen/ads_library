# A46: Ad360 Data Unification (Per-Ad Complete Record)

## 目的
1広告単位で必要情報を欠損なく揃えるため、データ統合スキーマを確立する。

## タスク
1. Ad360必須項目定義
- 基本: title/advertiser/platform/first_seen/last_seen/status
- クリエイティブ: thumbnail/image/video/snapshot/orientation/duration
- テキスト: description/ocr_text/lp_text/transcript
- 分析: topic_tags/topic_evidence/hit_drivers/hit_score
- 遷移先: destination_url/final_url/lp_meta

2. 欠損補完パイプライン
- 欠損項目を日次補完
- 補完不能は reason_code 付きで隔離

3. Ad360品質監査
- ad_id単位で completeness% を算出
- 80%未満を再処理キューへ投入

## 完了条件
- [ ] Ad360項目定義が固定される
- [ ] 欠損補完が定期実行される
- [ ] completeness監査が回る

