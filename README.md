# Video Ad Analysis AI Platform (VAAP)

動画広告分析AIプラットフォーム - 競合広告の収集・分析・生成を統合した自社向けソリューション

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                     │
│  Dashboard / Ad Library / Analysis / Creative Studio     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                  API Gateway (FastAPI)                    │
│  REST API / WebSocket / Authentication                   │
└──────┬───────┬───────┬───────┬───────┬──────────────────┘
       │       │       │       │       │
┌──────▼──┐ ┌─▼────┐ ┌▼─────┐ ┌▼────┐ ┌▼──────────┐
│Crawling │ │  CV  │ │Audio │ │GenAI│ │Prediction │
│Service  │ │Engine│ │Engine│ │Engine│ │  Engine   │
└─────────┘ └──────┘ └──────┘ └─────┘ └───────────┘
       │       │       │       │       │
┌──────▼───────▼───────▼───────▼───────▼──────────────────┐
│              Task Queue (Celery + Redis)                  │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│          Data Layer (PostgreSQL + MinIO + Redis)          │
└─────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ / FastAPI / Celery |
| Frontend | Next.js 14 / React 18 / TypeScript |
| Database | PostgreSQL 15 + pgvector |
| Cache | Redis 7 |
| Object Storage | MinIO (S3 compatible) |
| Task Queue | Celery + Redis |
| CV Engine | YOLOv8 / OpenCV / PySceneDetect |
| Audio Engine | OpenAI Whisper / librosa |
| OCR | EasyOCR / PaddleOCR |
| GenAI | OpenAI GPT / Anthropic Claude / Stable Diffusion |
| ML | scikit-learn / XGBoost / PyTorch |
| Monitoring | Prometheus + Grafana |

## Modules

### 1. Data Infrastructure (`backend/app/services/crawling/`)
- Web scraping engine for ad platforms
- ETL pipeline for data normalization
- Ad metadata collection and storage

### 2. Computer Vision (`backend/app/services/cv/`)
- Scene detection and shot boundary analysis
- Object/product/logo detection (YOLOv8)
- Composition analysis (face close-up ratio, UI display ratio)
- Color palette extraction
- OCR text detection

### 3. Audio Analysis (`backend/app/services/audio/`)
- Automatic speech recognition (Whisper)
- Tone and sentiment analysis
- Keyword extraction and CTA detection
- Hook word analysis

### 4. Generative AI (`backend/app/services/generative/`)
- Video script generation
- Short video storyboard creation
- Ad copy generation
- Banner/creative generation
- A/B test variation generation

### 5. Predictive Modeling (`backend/app/services/prediction/`)
- CTR/CVR prediction
- Winning creative prediction
- Ad fatigue detection
- Optimal duration prediction

### 6. Analytics & Reporting (`backend/app/services/analytics/`)
- Competitor dashboard
- Trend analysis
- Automated report generation
- Cross-platform unified analytics

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd ads_library

# Backend setup
cd backend
pip install -r requirements.txt
cp .env.example .env

# Start infrastructure
docker-compose up -d postgres redis minio

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload

# Start workers
celery -A app.tasks.worker worker --loglevel=info

# Frontend setup
cd ../frontend
npm install
npm run dev
```

## Project Structure

```
ads_library/
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Config, security, dependencies
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   │   ├── crawling/   # Ad collection
│   │   │   ├── cv/         # Computer vision
│   │   │   ├── audio/      # Audio analysis
│   │   │   ├── generative/ # AI generation
│   │   │   ├── prediction/ # ML prediction
│   │   │   └── analytics/  # Reporting
│   │   ├── tasks/          # Celery tasks
│   │   └── utils/          # Shared utilities
│   ├── tests/
│   ├── migrations/
│   └── ml_models/          # Trained model files
├── frontend/
│   └── src/
│       ├── app/            # Next.js pages
│       ├── components/     # React components
│       ├── lib/            # Utilities
│       └── hooks/          # Custom hooks
├── docker/                 # Docker configs
├── scripts/                # Utility scripts
└── docs/                   # Documentation
```

## License

Proprietary - Internal Use Only
