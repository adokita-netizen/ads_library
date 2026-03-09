# Planner 3: FRONTEND E2E — Round 2
# 担当: Agent B (フロントエンド)
# 更新: 2026-03-01

## ★ Round 1 完了サマリー ★

### Agent B 完了分
- [x] B1-B12: CreativeViewer, トレンド, 勝ちパターン, パクりガイド, ダッシュボード強化, API連携, 広告詳細, LP表示, 画像修正, クリエイティブ分析, クロールUI, Production UI, Analytics, Ad比較
- [x] B13-B28: 全15コンポーネント検証完了 (コレクション, AI分析, LP分析, 競合, レポート, フィルタ, シナリオ, 成功/失敗分析, KPI, 比較ツール, カレンダー, チーム, 設定, ブリーフ生成)
- [x] B33-B40: dispatcher修正, メディア抽出ダッシュボード, バッチ操作, CreativeViewer強化, メモリリーク修正, エラーハンドリング, パフォーマンス最適化, 型安全性
- 成果: 22ビュー実装, First Load JS 150kB, ビルド成功

---

## Round 2 タスクマップ

```
Phase 1 残:
B-R2-1 ダークモード (P1) ─── 全画面に影響
  ↓
B-R2-2 ヒートマップ (P1) ─── 新コンポーネント
B-R2-3 テーブルUX (P1) ──── ProRankingTable改善
B-R2-4 ジャンルフィルタ (P1) ─ ProRankingView改善

Phase 2:
B-R2-5 オンボーディング (P2) ─── 初回体験
B-R2-6 通知センター (P2) ────── C-R2-2 API依存
```

## ファイル変更計画

### B-R2-1: Dark Mode
```
新規:
  frontend/src/hooks/useTheme.ts
  frontend/src/components/common/ThemeToggle.tsx

修正 (dark: クラス追加):
  frontend/tailwind.config.js (darkMode: 'class')
  frontend/src/app/page.tsx
  frontend/src/components/common/Sidebar.tsx
  frontend/src/components/dashboard/ProRankingView.tsx
  frontend/src/components/dashboard/ProRankingTable.tsx
  frontend/src/components/dashboard/HitAdAnalysisView.tsx
  frontend/src/components/dashboard/AdDetailModal.tsx
```

### B-R2-2: Heatmap
```
新規:
  frontend/src/components/dashboard/HeatmapView.tsx

修正:
  frontend/src/app/page.tsx (ビュー追加)
```

### B-R2-3: Table UX
```
修正:
  frontend/src/components/dashboard/ProRankingTable.tsx
  frontend/src/components/dashboard/ProRankingView.tsx
```

### B-R2-4: Genre Filter
```
修正:
  frontend/src/components/dashboard/ProRankingView.tsx
```

### B-R2-5: Onboarding
```
新規:
  frontend/src/components/common/OnboardingWizard.tsx
  frontend/src/components/common/EmptyState.tsx
  frontend/src/components/common/SetupProgress.tsx

修正:
  frontend/src/app/page.tsx
```

### B-R2-6: Notification Center
```
新規:
  frontend/src/components/common/NotificationCenter.tsx

修正:
  frontend/src/app/page.tsx (ヘッダーに配置)
```

## Tailwind Dark Mode 置換パターン

### 背景
```
bg-white              → bg-white dark:bg-gray-900
bg-gray-50            → bg-gray-50 dark:bg-gray-800
bg-gray-100           → bg-gray-100 dark:bg-gray-700
```

### テキスト
```
text-gray-900         → text-gray-900 dark:text-gray-100
text-gray-700         → text-gray-700 dark:text-gray-300
text-gray-500         → text-gray-500 dark:text-gray-400
text-gray-400         → text-gray-400 dark:text-gray-500
```

### ボーダー
```
border-gray-200       → border-gray-200 dark:border-gray-700
border-gray-100       → border-gray-100 dark:border-gray-800
```

### ホバー
```
hover:bg-gray-50      → hover:bg-gray-50 dark:hover:bg-gray-800
hover:bg-gray-100     → hover:bg-gray-100 dark:hover:bg-gray-700
```

### インタラクティブ要素
```
ring-blue-500         → ring-blue-500 dark:ring-blue-400
focus:ring-blue-500   → focus:ring-blue-500 dark:focus:ring-blue-400
```

## Planner 2 → 3 のAPI依存

| C タスク | B タスク | API | 状態 |
|---------|---------|-----|------|
| C-R2-1 | B-R2-5/B43 | /ai-chat/message | C が先に実装 |
| C-R2-2 | B-R2-6 | /rankings/notifications | C が先に実装 |
| C-R2-3 | — | /integrations/* | UI は設定画面に統合 |

→ B はフォールバック実装で独立して進められる（API が無い場合は localStorage で代替）

## 完了基準 (Round 2 End)

- [ ] ダークモードトグルが動作し、5画面で正しく表示
- [ ] ヒートマップが SVG で描画される
- [ ] ProRankingTable: 固定ヘッダー + カラムトグル + URL同期
- [ ] ジャンルサイドバー: 検索 + アコーディオン + パンくず
- [ ] オンボーディングウィザードが初回表示される
- [ ] 通知ベルが動作する（API フォールバック含む）
- [ ] `npx next build --no-lint` 成功
- [ ] First Load JS: 160kB 以下を維持
