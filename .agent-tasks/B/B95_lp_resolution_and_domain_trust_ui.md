# B95: LP Resolution & Domain Trust UI

## 優先度: 🅱️ B（重要）

## 目的
- LP 遷移先が「ある」だけでなく、「どこへ飛ぶのか」「信頼できるか」が UI で判断できるようにする

## 対象ファイル
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/types/index.ts`

## 実装タスク
1. `resolved_url / domain / destination_type / lp_status / lp_score` を信頼表示に変換
2. リダイレクトや短縮URLは `最終遷移先` を優先表示
3. `domain mismatch / unresolved / dead` を視覚的に区別する

## 完了条件
- [ ] LP 遷移先の信頼状態が UI で分かる
- [ ] 短縮URLや中継URLでも最終遷移先を把握できる
