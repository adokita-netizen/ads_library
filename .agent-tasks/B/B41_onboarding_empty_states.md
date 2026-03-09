# B41: プログレッシブオンボーディング & スマート空状態

## 概要
初回ユーザーが「何をすればいいかわからない」状態をゼロにする。
データがない状態でも価値を感じさせ、自然にデータ収集→分析の流れに誘導する。

## 背景
現在58件しか広告データがなく、多くのビューが空表示になる。
新規ユーザーは「壊れている？」と感じてしまう。
空状態をチャンスに変え、プロダクトの可能性を伝えるUXが必要。

## タスク

### Task 1: ウェルカムモーダル（初回のみ）
```
場所: frontend/src/components/common/WelcomeModal.tsx (新規)

表示条件: localStorage.getItem('vaap_onboarding_completed') === null

内容:
┌──────────────────────────────────────────────────┐
│  VAAP へようこそ                                   │
│                                                    │
│  広告クリエイティブの分析AIプラットフォーム            │
│                                                    │
│  [1] 広告を収集する                                 │
│      Meta/YouTube/TikTok から自動収集               │
│                                                    │
│  [2] AIが自動分析                                   │
│      ヒットスコア・勝ちパターンを検出                 │
│                                                    │
│  [3] 勝ちクリエイティブを発見                        │
│      ランキング・比較・ブリーフ生成                   │
│                                                    │
│  ┌─────────────────┐  ┌──────────────────┐        │
│  │ まず広告を収集する │  │ デモデータで試す  │        │
│  └─────────────────┘  └──────────────────┘        │
└──────────────────────────────────────────────────┘

「まず広告を収集する」→ CrawlPanel にフォーカス
「デモデータで試す」→ デモモードON（後述）
```

### Task 2: デモモード
```
場所: frontend/src/lib/demoData.ts (新規)

- DEMO_ADS: 10件のサンプル広告データ（実在しないダミー）
- DEMO_RANKINGS: ランキングデータ
- DEMO_TRENDS: トレンドデータ

localStorage.getItem('vaap_demo_mode') === 'true' のとき:
- API呼び出しの代わりにデモデータを返す
- 画面右上に「デモモード」バッジ表示
- 「実データに切り替え」ボタン常時表示
```

### Task 3: コンテキスト対応の空状態
各ビューの空状態を、ただの「データがありません」から改善:

```
PRO DATABASE (空の場合):
┌──────────────────────────────────────────────────┐
│  📊 ランキングを表示するには広告データが必要です      │
│                                                    │
│  1. サイドバーの「クロール」で広告を収集             │
│  2. 自動でAI分析が実行されます                      │
│  3. ここにランキングが表示されます                   │
│                                                    │
│  [今すぐ広告を収集する →]                           │
│                                                    │
│  💡 ヒント: 「美容」「健康食品」などのキーワードで    │
│     検索すると効率的に広告を収集できます              │
└──────────────────────────────────────────────────┘

トレンド分析 (空の場合):
- 「1週間分のデータが蓄積されるとトレンド分析が利用可能になります」
- プログレスバーで「現在 58/200件 (29%)」

クリエイティブスタジオ (空の場合):
- 「ヒット広告のパターンを学習するには最低50件の分析済み広告が必要です」
```

### Task 4: セットアップ進捗トラッカー
```
場所: frontend/src/components/common/SetupProgress.tsx (新規)

サイドバー上部に表示（全ステップ完了まで）:

セットアップ進捗 [███░░░░░] 40%
☑ アカウント作成
☑ APIキー設定
☐ 初回クロール実行
☐ 50件以上の広告を収集
☐ ランキング計算完了

各ステップにツールチップで次のアクションを案内
```

### Task 5: フィーチャーディスカバリーツールチップ
```
場所: frontend/src/components/common/FeatureTooltip.tsx (新規)

初回訪問時のみ各ビューで1回表示（localStorage管理）:

PRO DATABASE: 「スコアでソートすると、今最も注目すべき広告が見つかります」
HIT分析: 「広告をクリックすると詳細分析が表示されます」
トレンド: 「週次データが溜まるとトレンドラインが表示されます」
```

## 完了条件
- [ ] WelcomeModal が初回のみ表示される
- [ ] デモモードでダミーデータが表示される
- [ ] 各空状態がコンテキスト対応メッセージを表示する
- [ ] SetupProgress がサイドバーに表示される
- [ ] FeatureTooltip が初回訪問時に表示される
- [ ] `npx next build --no-lint` 成功

## 触っていいファイル
- frontend/src/components/common/WelcomeModal.tsx (新規)
- frontend/src/components/common/SetupProgress.tsx (新規)
- frontend/src/components/common/FeatureTooltip.tsx (新規)
- frontend/src/lib/demoData.ts (新規)
- frontend/src/app/page.tsx (WelcomeModal統合)
- frontend/src/components/common/Sidebar.tsx (SetupProgress統合)
- frontend/src/components/dashboard/ProRankingView.tsx (空状態改善)
- frontend/src/components/dashboard/HitAdAnalysisView.tsx (空状態改善)
