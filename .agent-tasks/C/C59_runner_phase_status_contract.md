# C59: Runner Phase Status Contract

## Objective
scheduled runner の phase 戻り値形式を整え、状態判定を一貫化する。

## Scope
- crawl/analysis/media phase に `status` を付与
- `_require_phase_success` で phase fail 判定を統一

## Acceptance Criteria
- phaseの成否が log_entry から機械判定可能
- strict/lenient で期待どおり分岐する

## Status
Completed (2026-03-03)
