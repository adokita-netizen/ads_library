# B44: ダッシュボードカスタマイゼーション & セーブドビュー

## 概要
ユーザーが自分の作業スタイルに合わせてダッシュボードをカスタマイズできる機能を構築。
フィルター条件・表示設定の保存、ワンクリック切り替えを実現する。

## 背景
現在は全ユーザーに同じダッシュボードが表示される。
広告代理店のメディアバイヤーとクリエイティブディレクターでは見たいデータが異なる。
「自分だけのビュー」を保存できることで、日常的な使いやすさが大幅に向上する。

## タスク

### Task 1: セーブドビュー（フィルタープリセット保存）
```
場所: frontend/src/components/common/SavedViews.tsx (新規)

PRO DATABASE / HIT分析の上部に表示:

┌──────────────────────────────────────────────────┐
│ 📁 マイビュー:                                     │
│ [美容HIT広告 ▼] [動画広告のみ] [競合A監視] [+ 新規] │
└──────────────────────────────────────────────────┘

各ビューに保存される設定:
- ジャンルフィルター
- プラットフォームフィルター
- スコア範囲
- ソート順
- 表示モード（テーブル/カード/ギャラリー）
- 期間フィルター
- カスタム検索クエリ

保存先: localStorage + API（ログイン時）
```

### Task 2: クイックフィルターバー
```
場所: frontend/src/components/common/QuickFilterBar.tsx (新規)

ProRankingView / HitAdAnalysisView の直下に配置:

よく使うフィルター:
[HIT広告のみ] [動画のみ] [配信中] [今週の新着] [スコア70+]

クリックでトグルON/OFF（青ハイライト）
複数同時選択可能
カスタムフィルター追加可能（+ ボタン）
```

### Task 3: カラム表示カスタマイズ
```
場所: ProRankingTable / HitAdAnalysisView に統合

テーブルヘッダー右端に歯車アイコン:

表示カラム設定:
☑ 順位
☑ サムネイル
☑ 商材名
☑ ジャンル
☐ 広告主         ← 非表示にできる
☑ スコア
☐ 消化額         ← 非表示にできる
☑ 再生数
☐ いいね数       ← 非表示にできる
☑ 配信日数
☐ CTA            ← 新規追加
☐ フックタイプ   ← 新規追加

カラム順序もドラッグ&ドロップで変更可能（将来）
設定は localStorage に保存
```

### Task 4: ホーム画面 KPI カスタマイズ
```
場所: frontend/src/components/dashboard/CustomKPICards.tsx (新規)

サマリーカード（現在固定6枚）をカスタマイズ可能に:

利用可能なKPI:
- 総広告数 / アクティブ広告数
- 平均スコア / HIT率
- 新着広告数（今週）
- トップジャンル / トップ広告主
- 平均配信日数
- 推定総消化額
- メディア完全率
- 前週比成長率

ユーザーが4~8枚を選択して表示順を設定
「デフォルトに戻す」ボタン付き
```

## 完了条件
- [ ] セーブドビューの保存・読み込み・削除が動作する
- [ ] クイックフィルターバーが動作する
- [ ] カラム表示のカスタマイズが動作する
- [ ] 設定が localStorage に永続化される
- [ ] `npx next build --no-lint` 成功

## 触っていいファイル
- frontend/src/components/common/SavedViews.tsx (新規)
- frontend/src/components/common/QuickFilterBar.tsx (新規)
- frontend/src/components/dashboard/CustomKPICards.tsx (新規)
- frontend/src/components/dashboard/ProRankingView.tsx (統合)
- frontend/src/components/dashboard/ProRankingTable.tsx (カラム設定)
- frontend/src/components/dashboard/HitAdAnalysisView.tsx (統合)
