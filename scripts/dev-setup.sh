#!/bin/bash
# A32 (CI-034): Quick local development setup (<10 min)
#
# Usage:
#   bash scripts/dev-setup.sh          # Full setup (DB + backend + frontend)
#   bash scripts/dev-setup.sh backend  # Backend only (API + DB)
#   bash scripts/dev-setup.sh check    # Check prerequisites only
#
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

log()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
step()  { echo -e "\n${GREEN}==>${NC} $1"; }

# ── Prerequisites check ──
check_prereqs() {
    step "Checking prerequisites..."
    local ok=true

    command -v python >/dev/null 2>&1 && log "Python: $(python --version 2>&1)" || { warn "Python not found"; ok=false; }
    command -v pip >/dev/null 2>&1 && log "pip: available" || { warn "pip not found"; ok=false; }
    command -v node >/dev/null 2>&1 && log "Node.js: $(node --version 2>&1)" || warn "Node.js not found (frontend won't work)"
    command -v docker >/dev/null 2>&1 && log "Docker: $(docker --version 2>&1 | head -1)" || warn "Docker not found (use local DB instead)"

    if [ "$ok" = false ]; then
        fail "Missing critical prerequisites"
    fi
}

# ── Backend setup ──
setup_backend() {
    step "Setting up backend..."
    cd "$ROOT_DIR/backend"

    # Create .env if not exists
    if [ ! -f .env ]; then
        cat > .env << 'ENVEOF'
# VAAP Development Environment
APP_ENV=development
DEBUG=true
DATABASE_URL=postgresql+asyncpg://vaap:vaap_password@localhost:5432/vaap_db
SECRET_KEY=dev-only-not-for-production-use-change-me-32chars
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
STORAGE_BACKEND=minio
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
ENVEOF
        log "Created backend/.env"
    else
        log "backend/.env already exists"
    fi

    # Install Python dependencies
    step "Installing Python dependencies..."
    pip install -r requirements.txt --quiet 2>/dev/null && log "Dependencies installed" || warn "Some dependencies failed (non-critical)"

    # Create exports directory
    mkdir -p exports models media_cache
    log "Created data directories"
}

# ── Database setup ──
setup_db() {
    step "Setting up database..."

    if command -v docker >/dev/null 2>&1; then
        # Start only PostgreSQL and Redis via docker-compose
        docker compose up -d postgres redis 2>/dev/null || docker-compose up -d postgres redis 2>/dev/null || true
        log "PostgreSQL + Redis containers started"

        # Wait for PostgreSQL
        echo -n "  Waiting for PostgreSQL..."
        for i in $(seq 1 30); do
            if docker compose exec -T postgres pg_isready -U vaap -d vaap_db >/dev/null 2>&1 || \
               docker-compose exec -T postgres pg_isready -U vaap -d vaap_db >/dev/null 2>&1; then
                echo ""
                log "PostgreSQL is ready"
                break
            fi
            echo -n "."
            sleep 1
        done
    else
        warn "Docker not available — backend will use SQLite fallback"
    fi
}

# ── Frontend setup ──
setup_frontend() {
    step "Setting up frontend..."
    cd "$ROOT_DIR/frontend"

    if [ ! -f package.json ]; then
        warn "No package.json found in frontend/"
        return
    fi

    if command -v npm >/dev/null 2>&1; then
        npm install --quiet 2>/dev/null && log "Frontend dependencies installed" || warn "npm install had warnings"
    elif command -v yarn >/dev/null 2>&1; then
        yarn install --silent 2>/dev/null && log "Frontend dependencies installed" || warn "yarn install had warnings"
    else
        warn "Neither npm nor yarn found — skip frontend setup"
    fi
}

# ── Run smoke tests ──
run_smoke() {
    step "Running smoke tests..."
    cd "$ROOT_DIR/backend"
    python -m pytest tests/test_smoke.py -v --tb=short -q 2>/dev/null && log "Smoke tests passed" || warn "Some smoke tests failed"
}

# ── Main ──
MODE="${1:-full}"

echo "=============================="
echo "  VAAP Development Setup"
echo "  Mode: $MODE"
echo "=============================="

check_prereqs

case "$MODE" in
    check)
        log "Prerequisites check complete"
        ;;
    backend)
        setup_backend
        setup_db
        step "Start the API server:"
        echo "  cd backend && uvicorn app.main:app --reload --port 8000"
        ;;
    full)
        setup_backend
        setup_db
        setup_frontend
        step "Start the services:"
        echo "  Terminal 1: cd backend && uvicorn app.main:app --reload --port 8000"
        echo "  Terminal 2: cd frontend && npm run dev"
        echo "  API docs:   http://localhost:8000/api/docs"
        echo "  Frontend:   http://localhost:3000"
        ;;
    *)
        echo "Usage: bash scripts/dev-setup.sh [full|backend|check]"
        exit 1
        ;;
esac

echo ""
log "Setup complete!"
