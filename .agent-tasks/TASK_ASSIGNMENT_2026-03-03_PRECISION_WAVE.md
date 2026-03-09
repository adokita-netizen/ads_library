# Task Assignment (2026-03-03) — Precision Improvement Wave

対象: `INC-2026-03-03-CREATIVE-FETCH`
目的: 取得精度・誤紐付け防止・監査可能性を短期で引き上げる。

## Agent A (Data Foundation)
1. A-0303-P1: 保存前品質ゲートの強制化
- `ad_id` 不一致: 保存拒否
- `creative_fetch_source` 空: 保存拒否
- `orientation` は `vertical|horizontal|square|unknown` のみ許可

2. A-0303-P2: 理由コード辞書の単一ソース化
- `creative_fetch_reason` の許容値を定数化
- 未定義コードは `unknown_schema` に正規化

## Agent C (API)
1. C-0303-P1: API契約テスト追加
- 詳細APIで `creative_fetch_*` と `orientation` の必須返却を自動テスト
- 欠損時は 5xx ではなく安全に欠損理由を返す

2. C-0303-P2: 未取得一覧APIの優先度付け
- 理由コードごとに再取得優先度を返却
- `unknown_schema` を最優先監視に設定

## Agent D (Media/Crawling)
1. D-0303-P1: フォールバック実行制御
- API失敗時のみ実行
- ad単位の実行回数上限 + cooldown 導入

2. D-0303-P2: orientation判定の二段化
- 第一判定: ffprobe
- width/height欠損時は `unknown` 固定（推定判定禁止）

3. D-0303-P3: 監査サンプル自動出力
- `horizontal` と `fallback` を日次N件抽出して監査レポート化

## Agent B (Frontend)
1. B-0303-P1: 欠損表示の安全化
- 取得失敗時に理由コードを必ず表示
- 値欠損時は `unknown` を明示

2. B-0303-P2: 運用フィルタ強化
- 「未取得理由コード」フィルタ
- 「fallback取得のみ」フィルタ

## 共通SLOチェック (EOD)
- `ad_id` 誤紐付け: 0件
- `unknown_schema` 比率: 5%未満
- クリエイティブ取得成功率: 80%以上
- `horizontal` 件数は原因分類付きで100%説明可能
