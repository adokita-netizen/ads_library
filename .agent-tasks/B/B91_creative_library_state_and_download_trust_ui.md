# B91: Creative Library State & Download Trust UI

## 優先度: 🅱️ B（重要）

## 問題
- いまは「押せばDLできる」前提が強く、素材なし・ZIP未生成・LPなしの状態差が弱い
- ユーザーは「この広告は中で見れるのか」「DLできるのか」「LPまで揃っているのか」を一覧で判断したい

## 対象ファイル
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/components/dashboard/CreativeGalleryView.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/types/index.ts`

## 実装方針

### 1. 状態バッジを追加
- `閲覧可`
- `DL可`
- `LPあり`
- `素材不足`

### 2. DL失敗時の表示を改善
- 単に toast 失敗ではなく、理由を短文で出す
- 例:
  - `保存済み素材がありません`
  - `ZIPの生成に失敗しました`

### 3. 一覧の優先導線を明確化
- 1次CTA: `見る`
- 2次CTA: `DL`
- 3次情報: `LPあり/なし`, `素材状態`

### 4. 詳細の信頼性表示
- クリエイティブビュー直下に
  - 閲覧状態
  - DL可否
  - LP可否
  を並べる

## 完了条件
- [x] 一覧で閲覧可否/DL可否/LP有無が見分けられる
- [x] DL失敗理由が利用者に分かる
- [x] 詳細モーダルで素材状態が明示される

## 制約
- 新しい状態値は C 側のAPI契約に合わせる
- 表示だけでごまかさず、未知状態は `不明` として出す
