# 新規開発者オンボーディング視点 — 初めてこのコードベースを触る人へ

## 30秒で理解する VAAP

**VAAP = Video Ad Analysis AI Platform**
競合の動画広告を自動収集・分析して、ヒットパターンを見つけるSaaS。

```
クロール → 分析 → スコアリング → 表示
(Meta等から  (ジャンル分類  (ヒット判定    (PRO DATABASE
 広告収集)   メトリクス推定)  ランキング)    テーブル)
```

---

## 5分で理解するアーキテクチャ

```
[Next.js 14 Frontend]
  ↓ /api/v1/*
[CloudFront CDN]
  ├── /          → S3 (静的ファイル)
  └── /api/      → API Gateway
                    ↓
                  [Lambda: FastAPI]  ← API (105+ endpoints)
                    ↓
                  [RDS PostgreSQL]   ← DB (16 tables)
                    ↓
                  [SQS]              ← タスクキュー
                    ├── heavy → ECS Fargate Worker (Playwright, ML)
                    └── light → Lambda (ranking, alerts)
```

---

## ディレクトリ構成

```
ads_library/
├── frontend/                    ← Next.js 14 + Tailwind + TypeScript
│   ├── src/app/page.tsx         ← メインページ (22ビュー切替)
│   ├── src/components/          ← React コンポーネント群
│   ├── src/lib/api.ts           ← API クライアント
│   └── src/types/index.ts       ← 型定義
│
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI アプリ起動
│   │   ├── api/endpoints/       ← API ルーター (12モジュール)
│   │   │   ├── rankings.py      ← ★ 最大 (14,779行, 105+ endpoints)
│   │   │   └── media.py         ← ★ 2番目 (99,578行)
│   │   ├── models/              ← SQLAlchemy モデル (16テーブル)
│   │   ├── services/            ← ビジネスロジック
│   │   │   ├── crawling/        ← 10+ クローラー
│   │   │   ├── ranking/         ← ヒットスコア計算
│   │   │   ├── cv/              ← Computer Vision
│   │   │   ├── audio/           ← 音声分析
│   │   │   ├── generative/      ← AI コンテンツ生成
│   │   │   ├── lp_analysis/     ← LP分析
│   │   │   ├── meta_marketing/  ← Meta API
│   │   │   ├── competitive/     ← 競合分析
│   │   │   └── prediction/      ← ML予測
│   │   ├── tasks/               ← バックグラウンドタスク
│   │   └── core/                ← DB, config, auth
│   ├── scripts/                 ← データ品質スクリプト群
│   └── requirements.txt         ← Python 依存パッケージ
│
├── docker/
│   └── Dockerfile.worker        ← Worker コンテナ (Playwright入り)
│
├── terraform/                   ← AWS インフラ定義
│   ├── ecs.tf, sqs.tf, lambda.tf, rds.tf
│
└── .agent-tasks/                ← ★ タスク管理 (あなたが今読んでいる場所)
```

---

## 開発環境セットアップ

### バックエンド
```bash
cd C:/Users/ishit/ads_library/backend

# Python 仮想環境
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt

# 環境変数
export DATABASE_URL="postgresql://user:pass@localhost:5432/vaap"
export PYTHONIOENCODING=utf-8

# 起動
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 確認
curl http://localhost:8000/api/health
```

### フロントエンド
```bash
cd C:/Users/ishit/ads_library/frontend

npm install
npm run dev

# http://localhost:3000 でアクセス
# API は /api/* → localhost:8000 にプロキシ (next.config.js)
```

### Docker (ローカル全部入り)
```bash
cd C:/Users/ishit/ads_library
docker-compose up
```

---

## 最初に読むべきファイル (優先度順)

### 1. 全体像
- `.agent-tasks/README.md` ← タスク管理の構成
- `.agent-tasks/PLANNER_STRATEGY.md` ← 3プランナー戦略
- `.agent-tasks/VIEW_DATA_FLOW.md` ← データの流れ

### 2. フロントエンド
- `frontend/src/app/page.tsx` ← 22ビューのルーティング
- `frontend/src/components/common/Sidebar.tsx` ← ナビゲーション
- `frontend/src/lib/api.ts` ← API呼び出し関数

### 3. バックエンド
- `backend/app/main.py` ← FastAPI + ルーター登録
- `backend/app/models/ad.py` ← Ad モデル（最重要テーブル）
- `backend/app/api/endpoints/rankings.py` ← 最大のAPIファイル

### 4. インフラ
- `docker/Dockerfile.worker` ← Worker コンテナ
- `terraform/ecs.tf` ← ECS 定義
- `terraform/sqs.tf` ← キュー定義

---

## エージェント分担（コンフリクト防止）

```
Agent A: backend/scripts/ (データ品質), backend/app/tasks/metrics_tasks.py
Agent B: frontend/ (全域)
Agent C: backend/app/services/ranking/, backend/app/api/endpoints/rankings.py
Agent D: backend/app/services/crawling/, backend/app/services/media_extraction.py
```

**重要**: 他のエージェントの領域は読み取り専用。書き込み禁止。

---

## よくあるハマりポイント

### 1. ad_metadata の更新
```python
# ❌ これだと JSONB が更新されない
ad.ad_metadata["key"] = "value"
session.commit()

# ✅ 必ずこのパターン
from sqlalchemy.orm.attributes import flag_modified
meta = dict(ad.ad_metadata or {})
meta["key"] = "value"
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()
```

### 2. フロントのフィールド名
```
バックエンド (snake_case)  →  フロントエンド (camelCase)
image_url                  →  imageUrl
hit_score                  →  hitScore
```
両方を `||` で受ける: `data.image_url || data.imageUrl`

### 3. Lambda のコールドスタート
初回リクエストが5-15秒かかる。フロントの `api.ts` にリトライロジックがある。

### 4. Windows パス
```bash
# Git Bash では / を使う
cd C:/Users/ishit/ads_library/backend

# Python では os.path or pathlib を使う
from pathlib import Path
base = Path("C:/Users/ishit/ads_library/backend")
```

---

## 困ったら

1. `.agent-tasks/VIEW_ERROR_RECOVERY.md` ← エラー復旧ガイド
2. `.agent-tasks/VIEW_MONITORING.md` ← 監視・ログ確認方法
3. `.agent-tasks/COORDINATION_LOG.md` ← 他プランナーの作業状況
