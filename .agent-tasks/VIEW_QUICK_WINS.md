# Quick Wins 視点 — 30分以内で完了してインパクトが大きいもの

## ★★★ 最大効果（5分で完了）

### QW-1: CORS を本番ドメインに制限
**ファイル**: `backend/app/main.py`
**変更**: `allow_origins=["*"]` → `allow_origins=["https://d3qlbagx7gq5sp.cloudfront.net", "http://localhost:3000"]`
**効果**: セキュリティ改善
**担当**: Planner 2 (Agent C)

### QW-2: 既存58件のジャンル分類実行
**コマンド**: `cd backend && python -m scripts.classify_ads`
**効果**: PRO DATABASE のジャンルサイドバーが機能する
**担当**: Planner 1 (Agent A)

### QW-3: タイトル・URL修正実行
**コマンド**:
```bash
cd backend
python -m scripts.fix_titles
python -m scripts.fix_destination_urls
```
**効果**: テーブルに「タイトルなし」が減る、LPボタンが機能する
**担当**: Planner 1 (Agent A)

---

## ★★ 高効果（15分で完了）

### QW-4: ヒットスコア再計算
**コマンド**: `cd backend && python -m scripts.recompute_hit_scores`
**効果**: ランキング順位が付く、HITバッジが表示される
**担当**: Planner 2 (Agent C)

### QW-5: dashboard-summary エンドポイント動作確認
**コマンド**: `curl http://localhost:8000/api/v1/rankings/dashboard-summary | python -m json.tool`
**効果**: フロントのKPIカードに数値が入る
**担当**: Planner 2 (Agent C)

### QW-6: 壊れたビューの非表示化
**ファイル**: `frontend/src/components/common/Sidebar.tsx`
**変更**: API未実装で白画面になるビューをSidebarから一時的にコメントアウト
**効果**: ユーザーが壊れた画面に遷移しない
**担当**: Planner 3 (Agent B)

### QW-7: フロントのビルド確認
**コマンド**: `cd frontend && npx next build --no-lint`
**効果**: 型エラーの早期発見
**担当**: Planner 3 (Agent B)

---

## ★ 中効果（30分で完了）

### QW-8: 配信日付収集
**コマンド**: `cd backend && python -m scripts.collect_delivery_dates`
**効果**: 配信日数カラムに数値が入る、カレンダービューが機能する
**担当**: Planner 1 (Agent A)

### QW-9: 広告生存チェック
**コマンド**: `cd backend && python -m scripts.check_ad_survival`
**効果**: 「配信中」ステータスが正確になる
**担当**: Planner 1 (Agent A)

### QW-10: サムネイル修復
**コマンド**: `cd backend && python -m scripts.fix_bad_thumbnails`
**効果**: テーブルのサムネイルが表示される
**担当**: Planner 1 (Agent D)

### QW-11: genre-master エンドポイント確認
**コマンド**: `curl http://localhost:8000/api/v1/rankings/genre-master | python -m json.tool`
**効果**: サイドバーのジャンルツリーが正確になる
**担当**: Planner 2 (Agent C)

### QW-12: ProRankingView のデフォルト表示確認
**手順**: `npm run dev` → ブラウザで http://localhost:3000 → PRO DATABASE が表示されるか
**効果**: ファーストインプレッションの確認
**担当**: Planner 3 (Agent B)

---

## 実行順序（依存関係考慮）

```
[同時実行可能]
  QW-1 (CORS) ─── Planner 2
  QW-2 (分類)  ─── Planner 1
  QW-7 (ビルド) ── Planner 3

[QW-2 完了後]
  QW-3 (タイトル/URL) ── Planner 1
  QW-4 (スコア再計算) ── Planner 2 ← QW-2のジャンルデータ使う
  QW-6 (壊れビュー非表示) ── Planner 3

[QW-4 完了後]
  QW-5 (dashboard確認) ── Planner 2
  QW-11 (genre-master確認) ── Planner 2
  QW-12 (PRO DATABASE確認) ── Planner 3

[独立実行可能]
  QW-8 (配信日付) ── Planner 1
  QW-9 (生存チェック) ── Planner 1
  QW-10 (サムネイル) ── Planner 1
```

**全部やっても1-2時間。PRO DATABASE が「それっぽく」動く状態になる。**
