# Agent B Task: Creative Brief Generator & Template Library

## What to do

### 1. Creative Brief Generator
Create `frontend/src/components/dashboard/CreativeBriefGenerator.tsx`:
- Form-based brief creation:
  - ジャンル選択 (dropdown from genre master)
  - ターゲット層 (text input + suggestions: 20代女性, 30代男性, etc)
  - 目的 (認知拡大/CV獲得/ブランディング/リマーケティング)
  - 予算帯 (低/中/高)
  - 参考広告 (search and add existing ads as reference)
- Generated brief includes:
  - 推奨フック (based on genre's top hook types)
  - 推奨CTA (based on genre's top CTAs)
  - パワーワード候補 (from power words DB)
  - 構成案 (from scenario templates)
  - 推定パフォーマンス (score prediction)
- Export brief as markdown/text
- Save brief to localStorage

### 2. Template Library
Create `frontend/src/components/dashboard/TemplateLibrary.tsx`:
- Gallery of ad templates derived from winning patterns
- Cards with:
  - Template name (e.g., "美容系・質問型フック・限定CTA")
  - Hit rate badge
  - Preview of structure (sections timeline)
  - Genre tags
  - "このテンプレートを使う" button → opens ScenarioBuilder with preset
- Filter by genre, archetype, hit rate
- Sort by hit rate, usage count, newest
- Fetch from `/api/v1/rankings/scenario-templates`

### 3. Copy Variations Generator
Create `frontend/src/components/dashboard/CopyVariations.tsx`:
- Input: original ad title/description
- Generate 5 variations using different:
  - Hook types (質問, 数字, 問題提起, etc)
  - Tone (カジュアル, 専門的, 緊急, etc)
  - Length (短い/標準/長い)
- Each variation shows predicted effectiveness score
- Copy to clipboard button
- "この組み合わせで保存" button
- Pure frontend logic using pattern templates (no AI API needed)

### 4. Integration
- Add "creative-brief" view type to page.tsx
- Add "ブリーフ作成" to Sidebar
- Link from ScenarioBuilder to CreativeBriefGenerator
- Link from TemplateLibrary to ScenarioBuilder

### 5. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Build MUST pass
- Japanese UI text
- Template logic is frontend-only (pattern matching from fetched data)
