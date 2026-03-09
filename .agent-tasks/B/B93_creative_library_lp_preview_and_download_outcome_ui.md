# B93: Creative Library LP Preview & Download Outcome UI

## 優先度: 🅰️ A（クリティカル）

## 目的
- ユーザーが広告ごとに「CR確認」「その場DL」「LP遷移先確認」を迷わず完了できる UI に仕上げる

## 対象ファイル
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/components/dashboard/CreativeGalleryView.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/lib/media.ts`
- `frontend/src/types/index.ts`

## 実装タスク
1. 一覧カードと詳細で `downloadable / viewable / has_lp` をバッジ化し、優先順を `DL > 見る > LP` で固定
2. `lp_info.destination_url / domain / destination_type / lp_status / lp_score` を、詳細でリンク・ドメイン・状態として表示
3. `download_url` がある広告は 1 クリック DL、ない広告は `missing_reasons` をその場表示
4. 一括DL後に `requested_count / downloaded_count / skipped_ids` から結果サマリを表示
5. LP遷移先がある広告には `LPを開く` と `ドメインコピー` を出し、CR確認と導線を分断しない

## 完了条件
- [ ] 一覧でも詳細でも DL 可否と LP 有無が即わかる
- [ ] 直接DLできる広告は最短導線で保存できる
- [ ] DL不可やLP欠損の理由が利用者に伝わる

## 制約
- 既存 UI の visual language は維持
- backend の推測ロジックを frontend に持ち込まず、API 契約をそのまま使う
