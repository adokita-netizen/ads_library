# B97: Creative Library Regression Dashboard

## 優先度: 🅱️ B（重要）

## 目的
- プロダクト側から、CR/DL/LP の欠損や悪化傾向を見つけやすくする

## 対象ファイル
- `frontend/src/components/dashboard/`
- `frontend/src/lib/api.ts`
- `frontend/src/types/index.ts`

## 実装タスク
1. A 側の監査 JSON を受けて `viewable/downloadable/lp_resolved` の KPI を表示
2. `Top regressions / Top recoveries` をダッシュボード表示
3. 媒体別・ジャンル別の悪化をひと目で見えるようにする

## 完了条件
- [ ] 画面から改善状況と悪化傾向が分かる
- [ ] 復旧優先度の高い広告に遷移できる
