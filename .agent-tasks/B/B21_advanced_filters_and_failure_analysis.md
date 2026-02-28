# Agent B Task: Advanced Filter Panel & Success/Failure Analysis

## Reference (from screenshot)
The professional tool has a comprehensive "詳細な設定" (Advanced Settings) panel with:

### Filter Categories (MUST implement all):
1. **動画フォーマットの設定** (Video Format Settings)
   - 動画形式 dropdown: 動画 / 静止画 / カルーセル / すべて

2. **除外設定** (Exclusion Settings)
   - Show count of excluded items (e.g., "除外設定：0件")
   - Ability to exclude specific advertisers, domains, genres

3. **メイン設定** (Main Settings)
   - Platform filter: すべての広告 / Facebook / Instagram / TikTok
   - 全媒体 dropdown

4. **公開日設定** (Published Date Settings)
   - Date range picker (from/to)
   - Quick presets: 過去7日 / 過去30日 / 過去90日 / 全期間

5. **再生回数を設定** (View Count Settings)
   - Min/Max range inputs
   - Quick presets: 1,000+ / 10,000+ / 100,000+ / 1,000,000+

6. **いいね数を設定** (Like Count Settings)
   - Min/Max range inputs

7. **遷移先サイトの設定** (Destination Site Settings) ★CRITICAL★
   - 遷移先タイプ (Destination Type): text input with autocomplete
     - Options: 公式サイト, 記事LP, ECサイト, LINE追加, アプリDL, SNS
   - ドメイン検索 (Domain Search): text input
     - Type domain to filter ads going to specific domains

8. **クリア** button to reset all filters

### Left Sidebar Navigation (match reference):
- 🔍 検索 (Search) — PRO DATABASE view
- 📈 トレンド (Trend)
- 📊 分析 (Analysis)
- 🤖 AI専門家（β版）(AI Expert - Beta)
- 👥 チームスペース (Team Space)
- 📋 マイリスト (My List)
- 🔔 お知らせ (Notifications)

### View Mode Toggle (top right):
- リスト表示 (List) ≡
- カード表示 (Card) □≡
- グリッド表示 (Grid) ⊞

## What to do

### 1. Advanced Filter Panel Component
Create `frontend/src/components/dashboard/AdvancedFilterPanel.tsx`:

- Slide-in panel from left/right (or dropdown overlay) when filter icon clicked
- Dark background theme (matching reference: dark gray bg, white text)
- Each filter section is collapsible (accordion style)
- Each section has a header with expand/collapse arrow
- "クリア" (Clear) button at top right to reset ALL filters
- "× 詳細な設定" close button at top left
- Sticky apply button at bottom

Filter state object:
```typescript
interface AdvancedFilters {
  videoFormat: 'all' | 'video' | 'image' | 'carousel';
  excludedAdvertisers: string[];
  excludedDomains: string[];
  platform: 'all' | 'facebook' | 'instagram' | 'tiktok';
  dateRange: { from: string | null; to: string | null };
  viewCountMin: number | null;
  viewCountMax: number | null;
  likeCountMin: number | null;
  likeCountMax: number | null;
  destinationType: string | null;  // 公式サイト, 記事LP, etc.
  destinationDomain: string | null; // specific domain filter
  spendMin: number | null;
  spendMax: number | null;
}
```

### 2. Success & Failure Analysis View
Create `frontend/src/components/dashboard/SuccessFailureAnalysis.tsx`:

- Split view: Left = Hit ads (成功), Right = Non-hit ads (失敗)
- For each side, show:
  - Ad count and percentage
  - Common patterns (hook_type, cta_type, offer_type distribution)
  - Average metrics (views, spend, likes, score)
  - Top 5 representative ads with thumbnails
- Comparison highlights:
  - "成功広告の特徴" (Characteristics of successful ads) - green section
  - "失敗広告の特徴" (Characteristics of failed ads) - red section
  - "即転用できるポイント" (Points for immediate reuse) - blue section

Data from: GET /api/v1/rankings/hit-ads (filter by score ranges)

### 3. Element Analysis Panel
Create `frontend/src/components/dashboard/ElementAnalysis.tsx`:

For the current filtered set of ads:
- Break down by element:
  - Hook type distribution (bar chart)
  - CTA type distribution (bar chart)
  - Offer type distribution (bar chart)
  - Emotion type distribution (bar chart)
- Each element shows: hit rate vs overall, sample count
- Click on element → filter table to show only ads with that element
- "即転用" (Immediate Reuse) badge on high-performing elements

### 4. Integration
- Add filter icon (フィルター) button to ProRankingTable.tsx / ProRankingView.tsx header
- Advanced filter panel opens on click
- Integrate SuccessFailureAnalysis into "分析" tab
- Active filter count badge on filter icon (e.g., "フィルター (3)")
- Filter chips below search bar showing active filters (removable with X)

### 5. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Build MUST pass
- Dark theme for filter panel (bg-gray-900, text-white) to match reference
- All text in Japanese
