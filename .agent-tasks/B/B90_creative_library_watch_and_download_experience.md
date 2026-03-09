# B90: Creative Library Watch & Download Experience

## 目的
広告ライブラリを「見つける場所」ではなく「その場で確認して持ち帰れる場所」に引き上げる。

## 背景
- クリエイティブ閲覧自体は既にあるが、一覧と詳細で導線が散っている。
- 複数件DLが単発ダウンロードの繰り返しで、実運用の収集体験として弱い。
- 「ここで見れる」「ここからDLできる」が一目で伝わる必要がある。

## 実装スコープ
1. 一覧画面の CTA を `見る / DL / 保存` に統一
2. 詳細モーダルのクリエイティブ直下に `クリエイティブDL / 別タブで確認` を追加
3. 選択広告の一括DLを ZIP 化し、単発タブ連打を廃止
4. ダウンロード失敗時に `素材なし` を明示

## 完了条件
- カード一覧から 1 クリックで詳細確認できる
- カード一覧から 1 クリックで単体DLできる
- 複数選択時に ZIP 1本でDLできる
- 詳細モーダル内で「見る」「DLする」が迷わない位置にある

## 対象ファイル
- `frontend/src/components/dashboard/CreativeGalleryView.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/lib/media.ts`

## 検証
- `npx tsc --noEmit`
- 一覧 -> 詳細 -> DL
- 複数選択 -> ZIP DL
