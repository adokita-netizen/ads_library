# Agent B Task: Settings Dashboard & Onboarding Flow

## What to do

### 1. User Settings Panel
Create `frontend/src/components/settings/UserPreferences.tsx`:
- 通知設定: toggle for each alert type (新規ヒット, スコア変動, 競合, クロール完了)
- ウォッチリスト: add/remove watched advertisers and genres
- 表示設定: default items per page (10/20/50), default sort, default period
- 自動更新: toggle + interval selector (30s/60s/5min)
- テーマ: ライト/ダーク toggle (dark mode prep - just store preference)
- Save to localStorage + POST to /api/v1/rankings/user-preferences
- Toast notification on save success

### 2. Onboarding Tour
Create `frontend/src/components/common/OnboardingTour.tsx`:
- First-time user guided tour (show once, remember in localStorage)
- 5 steps highlighting key features:
  1. PRO DATABASE - "ここで全広告を一覧できます"
  2. 検索 - "キーワード、ジャンル、広告主で絞り込み"
  3. シナリオ作成 - "ヒットパターンから広告シナリオを自動生成"
  4. レポート - "パフォーマンスレポートとエクスポート"
  5. お知らせ - "新着ヒット広告やスコア変動をリアルタイム通知"
- Spotlight overlay (dark backdrop with highlighted area)
- Next/Skip/Complete buttons
- "もう一度見る" button in settings

### 3. Keyboard Shortcuts
Create `frontend/src/components/common/KeyboardShortcuts.tsx`:
- Global keyboard shortcut handler
- Shortcuts:
  - Ctrl+K: Open search (focus SmartSearchBar)
  - Ctrl+/: Show shortcuts help modal
  - 1-9: Switch views (1=PRO DB, 2=検索, etc)
  - Esc: Close modals
  - j/k: Navigate ad list up/down
  - Enter: Open selected ad detail
  - b: Bookmark selected ad
- Help modal listing all shortcuts
- Register/cleanup event listeners properly

### 4. Integration
- Add UserPreferences to settings view in page.tsx
- Add OnboardingTour to Home component (show on first visit)
- Add KeyboardShortcuts to root layout

### 5. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS
- Build MUST pass
- Japanese UI text
- localStorage for state persistence
