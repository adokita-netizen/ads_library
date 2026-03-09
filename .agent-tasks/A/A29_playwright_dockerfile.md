# A29: Dockerfile.worker に Playwright + Chromium 追加

## 目的
ECS Fargate 上の Worker コンテナで Playwright (Chromium) を動かし、
Meta 広告ライブラリの JS レンダリングページからメディア URL を抽出できるようにする。

## 対象ファイル
- `docker/Dockerfile.worker`

## タスク

### 1. PLAYWRIGHT_BROWSERS_PATH 環境変数を追加
- `WORKDIR /app` の直後に追加
```dockerfile
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
```

### 2. apt-get に Chromium 依存パッケージを追加
既存の `apt-get install` ブロックの末尾（`libxrender-dev \` の後）に以下を追記：
```
# Playwright Chromium dependencies
libgbm1 \
libnss3 \
libnss3-tools \
libatk1.0-0 \
libatk-bridge2.0-0 \
libcups2 \
libdrm2 \
libxkbcommon0 \
libxcomposite1 \
libxdamage1 \
libxrandr2 \
libpango-1.0-0 \
libcairo2 \
libasound2 \
libatspi2.0-0 \
libgtk-3-0 \
fonts-liberation \
fonts-noto-cjk \
```
- `--no-install-recommends` は維持
- `fonts-noto-cjk` は日本語広告スクレイピングに必須

### 3. Playwright Chromium ブラウザバイナリをインストール
`pip install -r requirements.txt` の後、`COPY backend/ .` の前に追加：
```dockerfile
RUN playwright install chromium
```

### 4. appuser に Playwright ディレクトリの権限付与
既存の `chown` 行を修正：
```dockerfile
RUN mkdir -p ml_models data \
    && groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app \
    && chown -R appuser:appuser ${PLAYWRIGHT_BROWSERS_PATH}
```

## 完成イメージ

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    # Playwright Chromium dependencies
    libgbm1 \
    libnss3 \
    libnss3-tools \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    fonts-liberation \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir torch==2.2.0 torchvision==0.17.0 numpy==1.26.4
RUN pip install --no-cache-dir git+https://github.com/openai/whisper.git
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser binary
RUN playwright install chromium

RUN pip install --no-cache-dir boto3==1.34.44 mangum==0.17.0

COPY backend/ .

RUN mkdir -p ml_models data \
    && groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app \
    && chown -R appuser:appuser ${PLAYWRIGHT_BROWSERS_PATH}

USER appuser

ENTRYPOINT ["python", "-m", "app.tasks.runner"]
```

## 確認方法
```bash
docker build -f docker/Dockerfile.worker -t vaap-worker .
docker run --rm vaap-worker python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

## 制約
- `docker/Dockerfile.worker` のみ編集
- 既存の pip install 順序を壊さない
