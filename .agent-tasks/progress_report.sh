#!/bin/bash
# VAAP Agent Progress Report
# Usage: bash .agent-tasks/progress_report.sh

echo "=================================="
echo "  VAAP Agent Progress Report"
echo "  $(date '+%Y-%m-%d %H:%M')"
echo "=================================="
echo ""

# Agent A
echo "--- Agent A (Data Foundation) ---"
a_total=$(ls -1 .agent-tasks/A/A*.md .agent-tasks/A/A_R2*.md 2>/dev/null | wc -l)
a_done=$(grep -l "COMPLETED\|完了\|\[x\]" .agent-tasks/A/status.md 2>/dev/null | wc -l)
a_r2=$(ls -1 .agent-tasks/A/A_R2*.md 2>/dev/null | wc -l)
echo "  Task files: $a_total"
echo "  Round 2 tasks: $a_r2"
echo "  Round 1 completed: A1-A7, A33-A36 (11 tasks)"
echo ""

# Agent B
echo "--- Agent B (Frontend) ---"
b_total=$(ls -1 .agent-tasks/B/B*.md .agent-tasks/B/B_R2*.md 2>/dev/null | wc -l)
b_r2=$(ls -1 .agent-tasks/B/B_R2*.md 2>/dev/null | wc -l)
echo "  Task files: $b_total"
echo "  Round 2 tasks: $b_r2"
echo "  Round 1 completed: B1-B28, B33-B40 (36 tasks)"
echo ""

# Agent C
echo "--- Agent C (API/Scoring) ---"
c_total=$(ls -1 .agent-tasks/C/C*.md .agent-tasks/C/C_R2*.md 2>/dev/null | wc -l)
c_r2=$(ls -1 .agent-tasks/C/C_R2*.md 2>/dev/null | wc -l)
echo "  Task files: $c_total"
echo "  Round 2 tasks: $c_r2"
echo "  Round 1 completed: C1-C37 (37 tasks)"
echo ""

# Agent D
echo "--- Agent D (Media/Crawling) ---"
d_total=$(ls -1 .agent-tasks/D/D*.md .agent-tasks/D/D_R2*.md 2>/dev/null | wc -l)
d_r2=$(ls -1 .agent-tasks/D/D_R2*.md 2>/dev/null | wc -l)
echo "  Task files: $d_total"
echo "  Round 2 tasks: $d_r2"
echo "  Round 1 completed: D1-D6, D26-D32 (13 tasks)"
echo ""

# CI Backlog
echo "--- CI Backlog ---"
ci_total=$(grep -c "^- CI-" .agent-tasks/CONTINUOUS_IMPROVEMENT_BACKLOG.md 2>/dev/null)
ci_done=$(grep -c "\[DONE" .agent-tasks/CONTINUOUS_IMPROVEMENT_BACKLOG.md 2>/dev/null)
ci_p0=$(grep -c "| P0 |" .agent-tasks/CONTINUOUS_IMPROVEMENT_BACKLOG.md 2>/dev/null)
echo "  Total CI tasks: $ci_total"
echo "  Done: $ci_done"
echo "  P0 (critical): $ci_p0"
echo ""

# Summary
echo "=================================="
echo "  Overall Summary"
echo "=================================="
echo "  Round 1: ~97 tasks completed"
echo "  Round 2: 23 tasks issued"
echo "  CI tasks: $ci_total ($ci_done done)"
echo "  Phase: Phase 1 残消化 + Phase 2 着手"
echo "=================================="
