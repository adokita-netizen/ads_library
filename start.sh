#!/bin/bash
# ─── Ads Library Platform — Full startup script ───
# Usage: bash start.sh
# Starts: PostgreSQL, Redis, FastAPI backend, Next.js frontend

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=== Ads Library Platform Startup ==="
echo "Project: $PROJECT_DIR"
echo ""

# ─── 1. PostgreSQL ───
echo "[1/4] Starting PostgreSQL..."
if pg_isready -h localhost -q 2>/dev/null; then
  echo "  PostgreSQL already running."
else
  sudo -u claude /usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/16/main start -l /tmp/postgresql.log -w 2>/dev/null || \
    sudo pg_ctlcluster 16 main start 2>/dev/null || \
    echo "  WARNING: Could not start PostgreSQL (may need manual intervention)"
  sleep 2
  if pg_isready -h localhost -q 2>/dev/null; then
    echo "  PostgreSQL started."
  else
    echo "  WARNING: PostgreSQL may not be ready."
  fi
fi

# ─── 2. Redis ───
echo "[2/4] Starting Redis..."
if redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "  Redis already running."
else
  redis-server --daemonize yes --loglevel warning 2>/dev/null || true
  sleep 1
  if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "  Redis started."
  else
    echo "  WARNING: Redis may not be ready."
  fi
fi

# ─── 3. FastAPI Backend ───
echo "[3/4] Starting FastAPI backend on :8000..."
# Kill any existing uvicorn
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

cd "$BACKEND_DIR"
PYTHONPATH="$BACKEND_DIR" nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend to be ready
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "  Backend ready."
    break
  fi
  sleep 1
done

if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  echo "  WARNING: Backend not responding yet (check /tmp/backend.log)"
fi

# ─── 4. Next.js Frontend ───
echo "[4/4] Starting Next.js frontend on :3000..."
# Kill any existing Next.js
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Clear stale Next.js cache for clean build
rm -rf "$FRONTEND_DIR/.next" 2>/dev/null || true

cd "$FRONTEND_DIR"
nohup npx next dev --hostname 0.0.0.0 --port 3000 > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# Wait for frontend to be ready
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo "  Frontend ready."
    break
  fi
  sleep 2
done

if ! curl -sf http://localhost:3000 > /dev/null 2>&1; then
  echo "  WARNING: Frontend not responding yet (check /tmp/frontend.log)"
fi

# ─── Summary ───
echo ""
echo "=== Startup Complete ==="
echo "  PostgreSQL: $(pg_isready -h localhost -q 2>/dev/null && echo 'OK' || echo 'WARN')"
echo "  Redis:      $(redis-cli ping 2>/dev/null | grep -q PONG && echo 'OK' || echo 'WARN')"
echo "  Backend:    $(curl -sf http://localhost:8000/health > /dev/null 2>&1 && echo 'OK (:8000)' || echo 'WARN')"
echo "  Frontend:   $(curl -sf http://localhost:3000 > /dev/null 2>&1 && echo 'OK (:3000)' || echo 'STARTING...')"
echo ""
echo "  Logs: /tmp/backend.log, /tmp/frontend.log"
echo "  Health: http://localhost:3000/api/health"
