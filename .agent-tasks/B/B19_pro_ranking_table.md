# Agent B Task: Professional Ranking Table (Like 動画広告分析プロ)

## Reference
Replicate the EXACT look and feel of professional ad analysis tools.

### Key Features
1. **Hit Line badge** - "ヒットライン超え" badge on ads exceeding the hit line threshold
2. **Search autocomplete** - Type keyword, see genre/product/advertiser suggestions dropdown
3. **Search collection save** - Save filter presets, recall with one click
4. **Pro database table** - Ranked list with metrics and bar charts

## What to do

### 1. Pro ranking table
Create `frontend/src/components/dashboard/ProRankingTable.tsx`:

Table design (match reference image exactly):
| 順位 | サムネイル | 媒体 | 商材名 | 遷移先タイプ | ジャンル種別 | 管理番号 | 再生増加数 | 累計再生回数 | 予想消化増加額 | 累計予想消化額 | いいね増加数 |
|------|-----------|------|--------|------------|------------|---------|-----------|-------------|--------------|--------------|------------|

Per row:
- **順位**: Number (1, 2, 3...), bold
- **サムネイル**: Image with:
  - Video duration badge bottom-left ("0:29" format, dark bg, white text, rounded)
  - Platform icon bottom-right (blue F for Facebook, gradient circle for Instagram)
  - Cursor pointer, click opens detail modal
- **商材名**: Product name (bold, blue link color) + advertiser name (gray, small) below + company icon
- **媒体**: Platform icon only (Facebook blue F, Instagram gradient, TikTok music note)
- **遷移先タイプ**: Destination type text (公式サイト, 記事LP, ECサイト, LINE追加, アプリDL)
- **ジャンル種別**: Genre pill badge
- **管理番号**: Internal ID (N + ad_id format, e.g. "N00123")
- **再生増加数**: Number + thin blue bar chart below
- **累計再生回数**: Number (comma formatted) + blue bar chart (width proportional to max)
- **予想消化増加額**: ¥ formatted number
- **累計予想消化額**: ¥ formatted number + blue bar chart
- **いいね増加**: Number

If `is_above_hit_line == true`: Show "ヒットライン超え" badge (orange/gold) next to the rank or product name

Data from: GET /api/v1/rankings/pro-ranking

### 2. Smart search with autocomplete
Create `frontend/src/components/dashboard/SmartSearchBar.tsx`:
- Input field with search icon
- As user types, show dropdown with:
  - "○○ - すべてから検索" (gray, search icon)
  - Genre matches: "○○ で絞り込み" → ジャンル tag (blue)
  - Product matches: "○○ で絞り込み" → 商材 tag (green)
  - Advertiser matches: "○○ で絞り込み" → 広告主 tag (purple)
- Keyboard navigation (arrow keys, enter to select)
- Data from: GET /api/v1/rankings/smart-autocomplete?query=xxx

### 3. Genre sidebar/filter
- Left sidebar or top filter bar with genre categories
- Grouped by parent category (美容系, 健康系, ビジネス系, etc.)
- Each genre shows ad count badge
- Click to filter table
- "すべての広告" option at top
- Data from: GET /api/v1/rankings/genre-master

### 4. Search collection panel
- Save button (floppy disk icon) next to search bar
- Click to save current filters with a name
- Dropdown showing saved collections
- Click collection name to apply filters
- Delete button on each saved collection
- Data from: GET/POST/DELETE /api/v1/rankings/search-collections

### 5. Left sidebar navigation (like reference)
Sidebar with icons:
- 🔍 検索 (Search/PRO DATABASE) - active by default
- 📈 トレンド (Trend)
- 📊 分析 (Analysis)
- 👥 チームスペース (Team Space / Collections)
- 📋 マイリスト (My List / Bookmarks)
- 🔔 お知らせ (Notifications / Alerts)

### 6. Filter bar
Top bar with:
- "+検索条件を追加" button (add filter)
- "媒体: すべて" dropdown (platform filter)
- "除外設定: 0件" indicator
- View mode icons: list / card / grid

### 7. Period toggle and view mode
- Period: 日次 / 週次 / 月次 / 全期間
- Sort dropdown: 再生数順, 消化額順, いいね順, スコア順

### 6. Hit line indicator
At top of table or as a banner:
- "ヒットライン: 累計再生 X回以上" (show the threshold for current genre)
- Highlight color for rows above hit line (light gold/yellow background)

### 7. Number formatting (CRITICAL - Japanese style)
- Views: comma separated (10,997)
- Spend: ¥ prefix + comma (¥43,988)
- Duration: M:SS format (0:29)
- Increase: +X or 0
- Large numbers: 1.2万 for 12,000+

### 8. Integration
- This MUST be the DEFAULT primary view of the dashboard
- Tab navigation: PRO DATABASE | ギャラリー | 分析 | 競合 | レポート
- Replace or prioritize over existing HitAdAnalysisView

### 9. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Build MUST pass
- Make it look PROFESSIONAL and data-dense like the reference
