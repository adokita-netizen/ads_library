# DPro差分埋め 実装設計書（Agent実行用 / v2）

最終更新: 2026-03-02  
対象: `ads_library` を動画広告分析Proの運用概念に近づけるための実装仕様

## 0. 本書の使い方
- 本書は「実装必須の指標定義」「UI操作要件」「期間再現モデル」「データ収集設計」を統合した仕様。
- 実装時は、**確定情報**と**推定アーキテクチャ**を混同しないこと。
- API/DB/UIを変更する全エージェントは本書を先に読むこと。

---

## 1. 指標体系（必須用語・式）

## 1.1 予想消化額（= 消化額の推定）
- 定義: 特定期間に広告配信へ使われた予算を予想した指標。
- 算出式: `予想消化額 = 再生増加数 × CPM`
- 運用解釈:
  - 予想消化額が高い: 配信が強い（売れている可能性）  
    ただし予算運用等の例外あり。
  - 予想消化額が低い: 案件選定/クリエイティブスタイル/ターゲット等の見直しシグナル。

## 1.2 CPMの扱い（推定値であることを明文化）
- CPMは媒体・時期で変動する。
- DPro互換方針として、ユーザー情報と媒体別CPMレンジを踏まえた平均推定値を採用。
- UI/ヘルプに必ず以下を表示:
  - `CPMは推測値であり、絶対額の保証ではありません`
  - `主用途は順位付け・相対比較です`

## 1.3 予想消化増加額（期間内の増加分）
- 定義: 指定期間で消化された広告費増加分の予想値。
- 表示式: `予想消化額 = 再生増加数 × CPM`
- 実務思想: 区切り期間の差分を見る。

## 1.4 再生増加数（コア差分指標）
- 定義: 指定期間の再生回数が、前の同様期間比でどれだけ増えたか。
- 用途:
  - 伸長期間の特定（キャンペーン/季節性/イベント影響）
  - いま伸びている広告の抽出（ランキング/検索根拠）

---

## 2. 期間モデル（区切り × version履歴）

## 2.1 区切り
- 目的: 当たり広告がどの期間で伸びたかを特定するための比較期間指定。
- 選択肢: `2日 / 1週間 / 2週間 / 1ヶ月`
- APIパラメータ: `period=2d|7d|14d|30d`

## 2.2 version履歴
- 定義: 指定日を最新版とした履歴再現（その日までに配信された広告を確認）。
- 操作:
  - version履歴で日付選択
  - 区切り設定
  - その時点基準の差分広告を表示
- 代表ユースケース:
  - 「去年の今頃は何が売れていたか」
  - 推奨: `version=去年同日付近` + `区切り=1週間 or 2週間`

---

## 3. UI/操作要件（リサーチ効率動線）

## 3.1 フィルター（検索条件保存）
- 要件:
  - 条件保存
  - 保存条件のワンクリック呼び出し
- 基本手順:
  - 媒体/ジャンル等を設定
  - フィルターで `+`
  - 名前入力で保存

## 3.2 表データ操作（並び替え・検索）
- 要件:
  - カラム（例: 予想消化額）クリックでソート
  - カラム内 `Search...` で絞り込み
  - 遷移先タイプ（記事LP/アンケートLP等）絞り込み

## 3.3 動画広告閲覧
- 要件:
  - 表から広告選択
  - `作品一覧` から動画と遷移先ページを確認可能

---

## 4. 遷移先タイプ（LP分析前提スキーマ）

## 4.1 定義
- 遷移先タイプ: 動画広告にリンクされたWebサイトの種類（LP/EC/アンケートLP等）。

## 4.2 代表分類
- アンケートLP:
  - アンケート回答後に商品LP/予約へ導くタイプ
- 記事LP:
  - 第三者視点コンテンツで商品LPの前段に置かれやすいタイプ
- 漫画記事LP:
  - 漫画形式ストーリーで伝える記事LP

---

## 5. 動画収集の設計（確定情報と推定実装を分離）

## 5.1 確定情報（資料で断定可能）
- 対象媒体として YouTube / TikTok / Pangle 等を収集しDB化する説明がある。
- 動画広告URLから再生数を直接観測する方式が説明されている。
- Pangleはアプリ内再生数表示制約があり、人手観測回数を再生数として掲載する運用説明がある。
- LIVE版は収集広告をリアルタイムにAI判別しDB反映、収集量増加の説明がある。
- 2024年機能として「動画広告の文字データ追加」「類似素材検出/購入（Pro Stock）」の説明がある。

## 5.2 推定アーキテクチャ（設計案として記述）
- 注意: 以下は一般に妥当な設計像。回避策や詳細手順には踏み込まない。

### A. 収集レイヤ
- 媒体別戦略分岐。
- URL観測可能媒体: クリエイティブURL起点で定期取得。
- アプリ内閉域媒体: オペレーション観測で補完。
- 最低収集項目:
  - `creative_id`
  - `media`
  - `creative_url`
  - `landing_url`
  - `observed_at`（version履歴用キー）

### B. 加工・正規化レイヤ
- 同一クリエイティブ重複排除（媒体横断・再出稿対応）。
- 典型要素:
  - 画像/動画知覚ハッシュ
  - 音声指紋（取得可能な場合）
  - OCR/ASRテキスト類似度

### C. 判別レイヤ
- 収集 -> AI判別 -> DB反映のストリーム処理。
- 判別タスク:
  - 商材/ジャンル分類
  - 遷移先タイプ分類

### D. テキスト化レイヤ
- OCR（画面文字）/ASR（音声文字起こし）を索引化。
- 目的:
  - 検索性向上
  - 類似判定精度向上

### E. 指標計算レイヤ
- `再生増加数`: 区切り差分
- `予想消化額`: `再生増加数 × CPM(推測平均)`
- `version履歴`: 観測スナップショット保持で過去再現

---

## 6. API実装要件

## 6.1 `GET /api/v1/rankings/pro-ranking` 拡張
- クエリ:
  - `period=2d|7d|14d|30d|90d|all`
  - `snapshot_date=YYYY-MM-DD`
  - `transition_type=survey_lp|article_lp|manga_lp|other`
  - `ad_format=video|banner|carousel|all`
  - `is_affiliate=true|false`
- 各広告レスポンス追加:
  - `comparison.current_date`
  - `comparison.previous_date`
  - `comparison.period_days`
  - `view_increase`
  - `estimated_spend_increase_jpy`
  - `cpm_jpy`
  - `transition_type`
  - `is_affiliate`

## 6.2 `search-collections` 拡張
- 保存対象filtersに追加:
  - `snapshot_date`
  - `transition_type`
  - `ad_format`
  - `is_affiliate`
  - `column_filters`
  - `column_sort`

## 6.3 `search/facets` 拡張
- 追加facet:
  - `transition_type` 件数
  - `ad_format` 件数
  - `is_affiliate` 件数

---

## 7. DB・データ処理要件

## 7.1 基本方針
- 一次ソース: `ad_daily_metrics`
- 補助属性は `ad_metadata` へ:
  - `transition_type`
  - `is_affiliate`
  - `cpm_jpy_applied`

## 7.2 version履歴再現
- 初期実装は `snapshot_date` 指定時再計算（新テーブルなし）。
- 性能課題時のみ materialized view を導入。

---

## 8. 受け入れ基準（DoD）
- 指標:
  - 予想消化額/再生増加数の式と文言がUI・ヘルプ・APIで一致。
  - CPMの「推測値」注記が表示される。
- 期間:
  - `区切り` と `version履歴` の組み合わせで結果が再現可能。
- UI:
  - 保存済み検索条件の再利用が1クリックで可能。
  - 表カラムソート/検索/遷移先タイプ絞り込みが機能。
- 技術:
  - backend/frontendテスト追加分が通過。

---

## 9. 実装タスク（Agent向け）

1. `DPRO-BE-001`: `pro-ranking` period/snapshot/transition/ad_format/is_affiliate対応  
2. `DPRO-BE-002`: search-collections 拡張 + 互換維持  
3. `DPRO-BE-003`: facets拡張 + テスト  
4. `DPRO-FE-001`: 区切り/version UI追加  
5. `DPRO-FE-002`: 表カラム操作（ソート/検索）統合  
6. `DPRO-FE-003`: フィルター保存再利用 + 作品一覧導線確認  
7. `DPRO-DATA-001`: transition_type/is_affiliate 欠損補完  
8. `DPRO-DATA-002`: CPM外れ値監査

---

## 10. 実装進捗（2026-03-02）

- 完了:
  - `DPRO-BE-001`
  - `DPRO-BE-002`
  - `DPRO-BE-003`
  - `DPRO-FE-001`
  - `DPRO-FE-002`
  - `DPRO-FE-003`
  - `DPRO-DATA-001`（`backend/scripts/backfill_transition_affiliate.py`）
  - `DPRO-DATA-002`（`backend/scripts/audit_cpm_outliers.py`）
- 運用コマンド:
  - `python -m scripts.backfill_transition_affiliate`
  - `python -m scripts.backfill_transition_affiliate --execute`
  - `python -m scripts.backfill_transition_affiliate --execute --fill-affiliate-default-false --fill-transition-default-other`
  - `python -m scripts.audit_cpm_outliers`
  - `python -m scripts.audit_cpm_outliers --json-report exports/cpm_outliers.json`
- ドライラン実測（ローカルDB）:
  - `backfill_transition_affiliate`
    - 対象広告: 1149
    - `transition_type` 補完候補: 1118
    - `is_affiliate` 補完候補: 59
  - `backfill_transition_affiliate --execute --fill-affiliate-default-false --fill-transition-default-other`
    - `transition unresolved`: 0
    - `affiliate unresolved`: 0
  - `audit_cpm_outliers --top 10`
    - CPM保有広告: 1126
    - 外れ値検出: 0（主要2媒体とも `estimated_cpm_jpy=800` に集中）
