# B92: CR / LP Visibility & Download Completion UI

## 優先度: 🅰️ A（クリティカル）

## 目的
- 広告一覧と詳細で、CRが見れるか、DLできるか、LP遷移先が取れているかを即判断できるようにする

## 対象ファイル
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/components/dashboard/CreativeGalleryView.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/types/index.ts`

## 実装タスク
1. `media_status.viewable/downloadable/has_lp/missing_reasons` をUI表示
2. `lp_info.destination_url/domain/destination_type/lp_status/lp_score` を詳細に表示
3. DL不可時は `missing_reasons` を利用して理由表示
4. 一括DL後の結果表示を「成功件数 / スキップ件数」ベースに改善

## 完了条件
- [x] 一覧で CR可視 / DL可否 / LP有無 が分かる
- [x] 詳細で LP ドメイン・遷移種別・取得状態が分かる
- [x] DL失敗理由が利用者に伝わる
