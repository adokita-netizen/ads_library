# Agent B Task: Ad Scenario Builder UI

## Concept
「圧倒的に削減。誰でも簡単に広告のシナリオが作成できる！」
Visual step-by-step wizard for creating ad scenarios/scripts.

## What to do

### 1. Scenario Builder Page
Create `frontend/src/components/dashboard/ScenarioBuilder.tsx`:

#### Step 1: Genre & Product Selection
- Genre dropdown (from /api/v1/rankings/genre-master or scenario-templates)
- Product name input field
- Target audience input (e.g., "30代女性")
- Key benefit input (e.g., "1ヶ月で-5kg")

#### Step 2: Archetype Selection
- Card grid showing available archetypes from /api/v1/rankings/scenario-archetypes
- Each card shows:
  - Archetype icon (emoji or SVG)
  - Japanese name (e.g., "Before/After変身型")
  - Hit rate badge (green if >60%, yellow if >40%)
  - Brief description
  - Example count
- Click to select (highlighted border)

#### Step 3: Customize
- Hook type selector (radio buttons with examples)
- CTA type selector (dropdown with examples)
- Platform selector (Facebook/Instagram/TikTok)
- Duration selector (15s/30s/60s)
- Tone selector (formal/casual/urgent)

#### Step 4: Generate & Preview
- "シナリオ生成" button → POST /api/v1/rankings/generate-scenario
- Loading spinner during generation
- Preview panel showing:
  - Timeline visualization (Hook→Problem→Solution→Proof→CTA)
  - Each section with:
    - Time range (0:00-0:03)
    - Section label with color coding
    - Generated text
    - Edit button (inline editing)
  - Title options (radio select from 3 options)
  - Power words highlighted in text (orange badges)
  - Predicted score gauge (0-100, color coded)

#### Step 5: Variations
- "バリエーション生成" button → POST /api/v1/rankings/scenario-variations
- Side-by-side comparison of variations
- Each variation shows predicted score
- Select best variation

#### Step 6: Save & Export
- "保存" button → POST /api/v1/rankings/saved-scenarios
- Name input modal
- Export options:
  - Copy to clipboard (full script text)
  - Download as text file
  - Download as PDF-like formatted view

### 2. Saved Scenarios Panel
Create `frontend/src/components/dashboard/SavedScenarios.tsx`:
- List of saved scenarios from /api/v1/rankings/saved-scenarios
- Each row: name, genre badge, archetype badge, predicted score, saved date
- Click to load into builder
- Delete button with confirmation
- Search/filter by genre

### 3. Scenario Performance Checker
Add to ScenarioBuilder.tsx:
- "パフォーマンス予測" button for custom text
- Text input area (paste any ad text)
- POST /api/v1/rankings/predict-scenario-performance
- Results:
  - Predicted score gauge
  - Hit probability %
  - Strengths (green checkmarks)
  - Weaknesses (red X marks)
  - Suggestions (yellow lightbulb)

### 4. Integration
- Add to main navigation as "シナリオ作成" tab
- HitAdAnalysisView.tsx: Add "シナリオ" tab in section navigation
- ProRankingView.tsx (if exists): Add "シナリオ作成" in sidebar

### 5. Reference Ad Examples
When showing scenario templates:
- Display thumbnail of top-performing reference ads
- Click to open AdDetailModal
- "この広告を参考にシナリオ作成" button on each ad → pre-fills builder

### 6. Design
- Clean, wizard-like step indicator at top (Step 1/6, Step 2/6...)
- Blue accent color for active step
- Gray for incomplete steps
- Green checkmark for completed steps
- Mobile responsive (single column on small screens)
- Japanese UI text throughout (all labels in Japanese)
- Tailwind CSS only

### 7. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Build MUST pass
- Data from API endpoints (scenario-templates, generate-scenario, scenario-variations, saved-scenarios)
- If APIs not available yet, use mock data with TODO comments
