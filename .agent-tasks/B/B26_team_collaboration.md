# Agent B Task: Team Collaboration & Annotation UI

## What to do

### 1. Ad Annotation Panel
Create `frontend/src/components/dashboard/AdAnnotations.tsx`:
- Comment/note system for individual ads
- Add note with text + tag (学び, アイデア, 要注意, 参考)
- Notes list with author avatar, timestamp, tag badge
- Edit/delete own notes
- Store in localStorage for now (TODO: API integration)
- Integrate into AdDetailModal or ProductDetailModal

### 2. Shared Collection Creator
Create `frontend/src/components/dashboard/SharedCollectionCreator.tsx`:
- Modal to create a new shared collection
- Fields: コレクション名, 説明, タグ (multi-select), 公開範囲 (自分のみ/チーム全体)
- Drag-and-drop ad reordering within collection
- Collection card preview with cover thumbnails
- Share link generation (mock)

### 3. Team Activity Dashboard
Create `frontend/src/components/dashboard/TeamActivity.tsx`:
- Recent team activity feed:
  - "[User] が [collection] にアドを追加しました"
  - "[User] が [ad] にコメントしました"
  - "[User] が新しいコレクションを作成しました"
- Team member avatars with online status
- Weekly activity summary: active members, notes added, collections shared
- Mock data with realistic Japanese content

### 4. Bulk Actions Bar
Create `frontend/src/components/dashboard/BulkActionsBar.tsx`:
- Sticky bottom bar that appears when ads are selected (checkbox)
- Actions: コレクションに追加, エクスポート, 比較, タグ追加, 削除
- Selected count badge
- "全選択" / "選択解除" buttons
- Integrate with ProRankingTable (add checkboxes to rows)

### 5. Integration
- Add AdAnnotations to existing ad detail views
- Wire up TeamActivity to "チームスペース" view in page.tsx (replace or enhance TeamSpaceView)
- Add BulkActionsBar to ProRankingView

### 6. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS
- Build MUST pass
- Japanese UI text
- localStorage for persistence (TODO comments for API)
