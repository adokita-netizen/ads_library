# Agent Operating Notes (`ads_library`)

## 1) DPro差分埋めタスクの必読資料
- エージェントは、DPro互換/差分埋めに関わる作業を始める前に
  `.agent-tasks/DPRO_PARITY_IMPLEMENTATION_SPEC.md`
  を必ず読むこと。

## 2) 設計書準拠ルール
- 指標定義は必ず以下に一致させる:
  - `予想消化額 = 再生増加数 × CPM`
  - CPMは推測値（絶対額保証なし）として扱う
- 期間比較は `区切り × version(snapshot_date)` の組み合わせで実装する。
- 仕様追加時は、UI/Backend/テスト/設計書を同時更新する。

## 3) 変更時の最低チェック
- Backend:
  - `python -m py_compile backend/app/api/endpoints/rankings.py`
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_search_collections_validation.py -q`
- Frontend:
  - `npx tsc --noEmit` (`frontend` ディレクトリ)

## 4) ドキュメント更新
- DPro関連の要件を追加・変更した場合は、設計書のDoDと実装タスク欄を更新すること。
- 大きい実装を完了したら `.agent-tasks/README.md` の参照リンクが維持されていることを確認すること。

