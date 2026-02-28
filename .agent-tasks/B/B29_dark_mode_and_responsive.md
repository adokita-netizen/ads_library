# Agent B Task: Dark Mode & Responsive Design

## What to do

### 1. Dark Mode Toggle
Create `frontend/src/components/common/ThemeProvider.tsx`:
- Context provider for theme state (light/dark)
- Read initial theme from localStorage
- Toggle function exposed via useTheme() hook
- Apply 'dark' class to html element
- Persist preference to localStorage

### 2. Dark Mode Styles
Update these components to support dark mode using Tailwind dark: prefix:
- Sidebar.tsx: dark:bg-gray-900 dark:text-gray-100 dark:border-gray-700
- ProRankingView.tsx: dark backgrounds, light text
- ProRankingTable.tsx: dark table rows, borders
- ReportsView.tsx: dark cards
- AlertsPanel.tsx: dark panel
- ScenarioBuilder.tsx: dark wizard steps

For each file, add dark: variants to existing Tailwind classes:
- bg-white → bg-white dark:bg-gray-900
- text-gray-900 → text-gray-900 dark:text-gray-100
- border-gray-200 → border-gray-200 dark:border-gray-700
- bg-gray-50 → bg-gray-50 dark:bg-gray-800

### 3. Dark Mode Toggle Button
Add toggle to Sidebar footer (next to user avatar):
- Sun/moon icon button
- Smooth transition (transition-colors duration-200)

### 4. Responsive Improvements
Update ProRankingView.tsx:
- Mobile: stack sidebar + main content vertically
- Tablet: collapse sidebar to icons only
- Desktop: full layout
Add to ProRankingTable.tsx:
- Horizontal scroll on mobile
- Condensed columns on small screens
- Sticky first column (title)

### 5. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS
- Build MUST pass
- Use Tailwind dark: prefix (class-based dark mode)
- Add dark mode to tailwind.config if needed (darkMode: 'class')
