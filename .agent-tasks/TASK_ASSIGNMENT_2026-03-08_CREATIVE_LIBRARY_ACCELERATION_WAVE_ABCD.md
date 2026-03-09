# TASK ASSIGNMENT 2026-03-08: CREATIVE LIBRARY ACCELERATION WAVE (ABCD)

## Goal
広告ライブラリを「広告CRをここで見れる、DLできる、状態が分かる」本番運用レベルまで引き上げる。

## Phase Order
1. **D96**: 素材回収率とDL完全性を上げる
2. **C96**: API契約と失敗理由コードを固定する
3. **B90 / B91**: 見る・DLする・状態確認するUIを完成させる
4. **A101**: 監査KPIで改善効果を継続追跡する

## Assigned Tasks

### Agent D
- **D96**: Creative Library Recovery & Download Completeness
- 目的:
  - `downloadable=false` 広告を減らす
  - snapshot only 状態の復旧ルートを作る

### Agent C
- **C96**: Creative Library Contract Hardening & Error Codes
- 目的:
  - `media_status` 契約を固定
  - DL失敗理由コードをUIへ返す

### Agent B
- **B90**: Watch & Download Experience
- **B91**: State & Download Trust UI
- 目的:
  - 一覧/詳細で `見る/DL/状態` を迷わせない

### Agent A
- **A101**: Coverage Audit & Recovery KPI
- 目的:
  - 欠損率を数値で追い、復旧優先度を日次で示す

## DoD
- 一覧で「見れる/DLできる/LPあり」が分かる
- 複数選択で ZIP DL が安定する
- API が素材状態と失敗理由を固定構造で返す
- 日次監査で欠損率の改善を確認できる
