# Task Assignment (2026-03-03) — Browser Stability Wave

目的: 「ブラウザでは時々動かない」症状を再現可能にし、UI/API/データの境界で安定化する。

## Agent B (Frontend)
1. B-BRW-1: クロール検索窓の入力安定化
- Enter実行、全角スペース正規化、空入力バリデーションを統一

2. B-BRW-2: E2E追加
- `e2e/crawl-search.spec.ts` を追加
- 検証ケース:
  - Enter送信でクロール発火
  - 全角スペースを含む入力の正規化
  - 空(全角スペースのみ)入力のエラーメッセージ

## Agent C (API)
1. C-BRW-1: quick-crawl契約明文化
- リクエスト `query/limit` の契約をAPI契約書へ追記
- 4xx/5xxの返却形式を統一

2. C-BRW-2: 監視ログ強化
- quick-crawl 受信 query の監査ログ（PII配慮）
- failed理由コードをダッシュボードで参照可能化

## Agent D (Crawling)
1. D-BRW-1: quick-crawl実行健全性
- timeout/retry/fallbackの境界を確認
- 失敗時の reason code を標準化

2. D-BRW-2: ブラウザ実行時の再現手順整備
- 取得不能時の再現手順（媒体/キーワード/時間帯）をテンプレート化

## Agent A (Data Foundation)
1. A-BRW-1: クロール実行メタデータ品質
- ad_metadata 内 `crawl_query` と取得件数の整合チェック
- 空クエリ保存の禁止ルールを追加

2. A-BRW-2: 失敗分析用集計
- 日次で quick-crawl 成功率/失敗理由を集計

## 必須テスト
- Frontend type check: `npx tsc --noEmit`
- Contracts: `npm run test:contracts`
- Browser E2E (new): `npx playwright test e2e/crawl-search.spec.ts`
- Regression table E2E: `npm run test:e2e:table`

## 実行結果 (2026-03-03)
- `npx tsc --noEmit` PASS
- `npm run test:contracts` PASS
- `npx playwright test e2e/crawl-search.spec.ts` PASS (2/2)
- `npm run test:e2e:table` PASS (3/3)
