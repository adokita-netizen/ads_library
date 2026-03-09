# A42: Ad Copy Taxonomy + Medical Signal Dictionary

## 目的
広告文/CR画像/OCR/LPテキストを統合して、医療系に限らない全カテゴリを高精度に抽出する。
さらに「何がHITに寄与しているか（訴求軸・オファー・表現要素）」まで判定可能にする。

## タスク
1. ドメイン横断シグナル辞書を作成
- 医療: `glp-1`, `aga`, `faga`, `美容医療`, `自由診療`
- 金融: `NISA`, `投資`, `保険見直し`, `資産運用`
- 教育: `英会話`, `資格`, `リスキリング`
- EC/D2C: `初回限定`, `定期`, `返金保証`
- アプリ: `無料DL`, `課金`, `サブスク`
- 同義語/表記ゆれ/半角全角/英数ハイフンを正規化

2. マルチモーダル分類器を実装（ルール + スコア）
- 入力: `title`, `description`, `ocr_text`, `lp_text`, `creative_visual_labels`
- 出力:
  - `detected_topics[]`
  - `confidence`
  - `evidence_terms[]`
  - `hit_drivers[]`（訴求軸/オファー/CTA/ビジュアル要素）

3. 誤分類監査（全カテゴリ）
- 主要カテゴリ語を含むのに未分類だった広告を抽出
- `false_negative_report` を日次生成

4. バックフィル（全件）
- 既存広告に再分類を実行
- `ad_metadata.topic_tags` と `topic_evidence` を保存
 - `ad_metadata.hit_drivers` を保存

## 完了条件
- [ ] 全カテゴリ辞書が管理可能な形式で作成される
- [ ] 医療以外も含めた見逃し率が改善
- [ ] 日次で誤分類監査レポートを出せる

## 対象
- `backend/scripts/reclassify_genres.py`
- `backend/scripts/audit_top30_collection.py`
- `backend/scripts/validate_metadata_schema.py`
