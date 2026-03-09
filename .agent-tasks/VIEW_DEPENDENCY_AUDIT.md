# 依存パッケージ監査視点 — 本当に全部必要か？

## 現状: requirements.txt が巨大

Lambda + Worker が同じ requirements.txt を共有している（推定）。
結果: Lambda のデプロイパッケージが巨大 → コールドスタート遅延。

---

## パッケージ分類

### Lambda に必要（API サーバーのみ）

```
# Web フレームワーク
fastapi==0.109.2
uvicorn[standard]==0.27.1
pydantic==2.6.1
python-multipart==0.0.9

# DB
sqlalchemy==2.0.46
psycopg2-binary==2.9.9
alembic==1.13.1

# HTTP
httpx==0.27.0
requests==2.31.0

# AWS
boto3==1.34.34

# AI API (軽量)
openai==1.12.0
anthropic==0.18.1

# ユーティリティ
python-jose[cryptography]==3.3.0  # JWT
passlib[bcrypt]==1.7.4             # パスワード
structlog==24.1.0                  # ログ
python-dateutil==2.8.2
pillow==10.2.0                     # 画像リサイズのみ

# 合計: ~50MB (圧縮後)
```

### Worker のみに必要（重いML/CV）

```
# ML フレームワーク (~1.5GB)
torch==2.2.0+cpu
torchvision==0.17.0+cpu
torchaudio==2.2.0+cpu

# NLP (~500MB)
transformers==4.38.1
fugashi==1.3.0
mecab-python3==1.0.8

# 音声 (~1GB)
openai-whisper  # (git install)
librosa==0.10.1
soundfile==0.12.1
pydub==0.25.1

# Computer Vision (~300MB)
ultralytics==8.1.0      # YOLOv8
easyocr==1.7.1
opencv-python-headless==4.9.0.80
scenedetect==0.6.2
scikit-image==0.22.0

# 画像生成 (~300MB)
diffusers==0.26.3

# ブラウザ自動化 (~50MB)
playwright==1.41.2
selenium==4.18.0
beautifulsoup4==4.12.3

# ML (~100MB)
scikit-learn==1.4.0
xgboost==2.0.3
lightgbm==4.3.0

# 合計: ~3-4GB
```

---

## 問題: Lambda に全部入れている

### 影響
- Lambda デプロイパッケージサイズ: 250MB制限を超える可能性
- コールドスタート: 5-15秒（体感的にフリーズ）
- メモリ使用量: import だけで数百MB消費

### フロントの対策（既に実装済み）
```typescript
// api.ts にリトライロジック
// 502/503/504 → exponential backoff で再試行
// → Lambdaコールドスタートの回避策
```

---

## 対策: requirements を分離

### requirements-lambda.txt （API 用）
```
fastapi==0.109.2
uvicorn[standard]==0.27.1
pydantic==2.6.1
sqlalchemy==2.0.46
psycopg2-binary==2.9.9
alembic==1.13.1
httpx==0.27.0
boto3==1.34.34
openai==1.12.0
anthropic==0.18.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
structlog==24.1.0
python-dateutil==2.8.2
pillow==10.2.0
python-multipart==0.0.9
```

### requirements-worker.txt （Worker 用）
```
-r requirements-lambda.txt

# ML/CV/NLP (Worker only)
torch==2.2.0+cpu
transformers==4.38.1
openai-whisper @ git+...
ultralytics==8.1.0
easyocr==1.7.1
opencv-python-headless==4.9.0.80
playwright==1.41.2
selenium==4.18.0
beautifulsoup4==4.12.3
scikit-learn==1.4.0
xgboost==2.0.3
librosa==0.10.1
diffusers==0.26.3
scenedetect==0.6.2
fugashi==1.3.0
```

### Dockerfile 変更

**Dockerfile.lambda** (新規 or 修正):
```dockerfile
COPY requirements-lambda.txt .
RUN pip install -r requirements-lambda.txt
```

**Dockerfile.worker** (既存):
```dockerfile
COPY requirements-worker.txt .
RUN pip install -r requirements-worker.txt
```

### 効果
- Lambda コールドスタート: 5-15秒 → 1-3秒
- Lambda メモリ使用量: 500MB → 150MB
- Lambda デプロイサイズ: 200MB → 50MB

---

## 条件付きインポートの問題

### 現状（推定）
```python
# rankings.py のトップレベル
from app.services.prediction.performance_predictor import PerformancePredictor
# → PerformancePredictor が sklearn, torch を import
# → Lambda で import エラー or メモリ爆発
```

### 対策: 遅延インポート
```python
# エンドポイント内でインポート
@router.get("/rankings/predict/{ad_id}")
async def predict(ad_id: int):
    from app.services.prediction.performance_predictor import PerformancePredictor
    predictor = PerformancePredictor()
    return predictor.predict(ad_id)
```

### または: try/except インポート
```python
try:
    from app.services.prediction.performance_predictor import PerformancePredictor
    HAS_ML = True
except ImportError:
    HAS_ML = False

@router.get("/rankings/predict/{ad_id}")
async def predict(ad_id: int):
    if not HAS_ML:
        raise HTTPException(503, "ML features not available in this environment")
    ...
```

---

## セキュリティ: 脆弱性チェック

```bash
cd C:/Users/ishit/ads_library/backend

# pip audit (脆弱性スキャン)
pip install pip-audit
pip-audit -r requirements.txt

# safety check
pip install safety
safety check -r requirements.txt
```

### 注意すべきパッケージ
- `pillow`: 画像処理ライブラリ、CVE頻出 → 最新版維持
- `requests`: HTTP リダイレクト攻撃 → 最新版維持
- `cryptography` (python-jose 依存): 暗号ライブラリ → 最新版維持
- `torch`: セキュリティパッチが遅い → バージョン固定の上注意
