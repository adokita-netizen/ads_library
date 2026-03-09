# B42: リアルタイム通知センター

## 概要
アラートエンジン（A37）が生成した通知をUI上で表示する通知センターを構築する。
ユーザーが「自分から情報を取りに行く」から「情報が来る」体験へ転換する。

## 背景
A37でバックエンドのアラートエンジンが構築される予定。
そのアラートをフロントエンドで表示する仕組みが必要。
また、クロール完了・分析完了・エクスポート完了なども通知に含める。

## タスク

### Task 1: 通知ベルアイコン + ドロップダウン
```
場所: frontend/src/components/common/NotificationBell.tsx (新規)

ヘッダー右上に配置:

  🔔(3)    ← 未読数バッジ
  ┌──────────────────────────────────────────┐
  │ 通知                        すべて既読  │
  ├──────────────────────────────────────────┤
  │ 🔴 新しいHIT広告を検出                   │
  │    美容液X - スコア: 85                  │
  │    2分前                                 │
  ├──────────────────────────────────────────┤
  │ ✅ クロール完了                           │
  │    23件の新しい広告を取得しました         │
  │    15分前                                │
  ├──────────────────────────────────────────┤
  │ 📊 ランキング更新完了                     │
  │    新しいランキングが利用可能です         │
  │    1時間前                               │
  ├──────────────────────────────────────────┤
  │        すべての通知を見る →               │
  └──────────────────────────────────────────┘

API: GET /api/v1/notifications/recent?limit=10
```

### Task 2: 通知一覧ページ
```
場所: frontend/src/components/dashboard/NotificationListView.tsx (新規)

page.tsx の "notifications" ビューとして統合

内容:
- フィルター: すべて / 未読のみ / アラート / システム
- 通知カード一覧（ページネーション）
- 各通知カード: アイコン + タイトル + 詳細 + 時刻 + 既読/未読インジケータ
- クリックで関連ページに遷移（ad_idがあればAdDetailModalを開く）
- 一括既読ボタン
- 通知設定リンク

API: GET /api/v1/notifications?page=1&per_page=20&filter=unread
     PUT /api/v1/notifications/{id}/read
     PUT /api/v1/notifications/read-all
```

### Task 3: トースト通知（リアルタイム）
```
場所: frontend/src/components/common/ToastNotification.tsx (新規)

画面右下にスライドイン表示:
- クロール完了時
- エクスポート完了時
- 新しいHIT広告検出時

30秒ポーリングで新着通知をチェック（WebSocketは将来対応）:
GET /api/v1/notifications/unread-count

新着があればトースト表示 + ベルのバッジ更新
```

### Task 4: 通知設定パネル
```
場所: frontend/src/components/settings/NotificationSettings.tsx (新規)

Settings ビューに統合:

通知設定
──────────────────────────
☑ 新しいHIT広告         (スコア 70 以上)
☑ トレンド急上昇        (前日比 +50% 以上)
☐ 競合の新広告          (広告主名を指定)
☑ クロール完了
☑ ランキング更新完了
☐ メール通知            (将来対応)
☐ Slack通知             (将来対応)

[保存]
```

## 完了条件
- [ ] NotificationBell がヘッダーに表示される
- [ ] 未読数バッジが表示される
- [ ] ドロップダウンで最新10件の通知が表示される
- [ ] NotificationListView で全通知一覧が見られる
- [ ] 通知クリックで関連ページに遷移する
- [ ] トースト通知が表示される
- [ ] 通知設定パネルが動作する
- [ ] `npx next build --no-lint` 成功

## 触っていいファイル
- frontend/src/components/common/NotificationBell.tsx (新規)
- frontend/src/components/common/ToastNotification.tsx (新規)
- frontend/src/components/dashboard/NotificationListView.tsx (新規)
- frontend/src/components/settings/NotificationSettings.tsx (新規)
- frontend/src/app/page.tsx (通知ビュー統合)
- frontend/src/components/common/Sidebar.tsx (通知ナビ追加)
- frontend/src/app/layout.tsx (NotificationBell統合)

## 依存
- A37 (AlertEngine) のAPI完成後にリアルデータ連携
- それまではモック/空状態で実装可能
