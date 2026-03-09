# Task Assignment (2026-03-03) — Open Slot Fill (A/B/C)

## 追加配分（空き枠）
- A41: `A41_volume_gap_investigation_and_recovery.md`
- B47: `B47_creative_clarity_and_refresh_validation.md`
- C43: `C43_quick_crawl_contract_and_quality_fix.md`

## 目的
- 広告数不足の根因調査と回復
- クリエイティブ不鮮明の再発抑止
- quick-crawl仕様とUI挙動のズレ解消
- Instagram を含む Meta2面の取得不足を解消

## 依存順
1. C43 でAPI契約を確定
2. A41 で件数回復ロジックを適用
3. B47 でUI/ブラウザ確認と回帰テスト固定

## DoD
- [x] GLP-1等の指定クエリで取得〜表示の経路が説明可能
- [x] 低件数/不鮮明の原因がログで追える
- [x] Facebook/Instagram の両方で件数改善が確認できる
- [x] APIテスト + E2Eテストで再発防止

## 2026-03-03 完了ログ追記
- Backend contract tests:
  - `python -m pytest tests/test_quick_crawl_contract.py tests/test_c50_retry_topic_contract.py tests/test_c44_topic_classification_contract.py tests/test_c46_quality_gate_contract.py -q`
  - result: `11 passed`
- Frontend E2E tests:
  - `CI=1 npx playwright test e2e/state-sync.spec.ts --reporter=line`
  - `CI=1 npx playwright test e2e/crawl-search.spec.ts --reporter=line`
  - result: `4 passed` + `5 passed`
- Stabilization fix:
  - `frontend/src/components/dashboard/ProRankingTable.tsx`
  - Added `refresh_nonce` query param to force re-fetch after retry action even with cached API layer.
