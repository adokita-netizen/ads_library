# 無料デプロイガイド（Render + Supabase + Upstash + Vercel）

月額 **$0** でVAAPを動かす構成です。

## 構成図

```
[ブラウザ] → [Vercel (Next.js)] → [Render (FastAPI)] → [Supabase (PostgreSQL)]
                                                     → [Upstash (Redis)]
```

---

## 1. Supabase（PostgreSQL）セットアップ

1. https://supabase.com にアクセス → **Start your project**
2. GitHub でログイン → 新しいプロジェクト作成
   - Name: `vaap`
   - Database Password: 安全なパスワードを設定（控えておく）
   - Region: **Northeast Asia (Tokyo)**
3. プロジェクト作成後 → **Settings** → **Database**
4. **Connection string** → **URI** をコピー
   - 形式: `postgres://postgres.[ref]:[password]@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres`
   - **この URL を控えておく**（Render の DATABASE_URL に使う）

> **注意**: Supabase 無料プランは 500MB ストレージ、2プロジェクトまで

---

## 2. Upstash（Redis）セットアップ

1. https://upstash.com にアクセス → **Sign Up**
2. **Create Database** をクリック
   - Name: `vaap-redis`
   - Region: **ap-northeast-1 (Tokyo)**
   - TLS: **有効**
3. 作成後 → **Details** タブ → **Redis URL** をコピー
   - 形式: `rediss://default:[password]@[host].upstash.io:6379`
   - **この URL を控えておく**（Render の REDIS_URL に使う）

> **注意**: Upstash 無料プランは日1万コマンド、256MB ストレージ

---

## 3. Render（FastAPI バックエンド）セットアップ

### 方法A: render.yaml で自動デプロイ

1. https://render.com にアクセス → GitHub でログイン
2. **New** → **Blueprint** → このリポジトリを選択
3. `render.yaml` が自動検出される → **Apply**
4. 環境変数を設定:
   - `DATABASE_URL`: Step 1 の Supabase URL
   - `REDIS_URL`: Step 2 の Upstash URL

### 方法B: 手動セットアップ

1. **New** → **Web Service** → このリポジトリを選択
2. 設定:
   - **Name**: `vaap-api`
   - **Region**: Oregon
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements-deploy.txt`
   - **Start Command**: `gunicorn app.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120`
   - **Plan**: **Free**
3. **Environment** タブで環境変数を追加:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Supabase の接続 URL |
| `REDIS_URL` | Upstash の Redis URL |
| `SECRET_KEY` | ランダムな文字列（`openssl rand -hex 32` で生成） |
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `CORS_ORIGINS` | `*`（後で Vercel の URL に変更推奨） |
| `DB_POOL_SIZE` | `3` |
| `DB_MAX_OVERFLOW` | `2` |
| `PYTHON_VERSION` | `3.11.7` |

4. **Create Web Service** をクリック
5. デプロイ完了後、URL が発行される（例: `https://vaap-api.onrender.com`）
6. `https://vaap-api.onrender.com/health` でヘルスチェック確認

---

## 4. Vercel（Next.js フロントエンド）セットアップ

1. https://vercel.com にアクセス → GitHub でログイン
2. **Add New Project** → このリポジトリを選択
3. 設定:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
4. **Environment Variables** を追加:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_URL` | Render の URL（例: `https://vaap-api.onrender.com`） |

5. **Deploy** をクリック
6. デプロイ完了後 → URL にアクセスして動作確認

---

## 5. 動作確認チェックリスト

- [ ] Render: `https://[your-app].onrender.com/health` → `{"status":"healthy","database":"ok","redis":"ok"}`
- [ ] Render: `https://[your-app].onrender.com/api/docs` → Swagger UI 表示
- [ ] Vercel: ダッシュボードが表示される
- [ ] Vercel: API プロキシ経由でデータ取得できる

---

## 費用まとめ

| サービス | プラン | 月額 | 制限 |
|----------|--------|------|------|
| Supabase | Free | $0 | 500MB DB, 2プロジェクト |
| Upstash | Free | $0 | 日1万コマンド, 256MB |
| Render | Free | $0 | 15分アイドルでスリープ, 750h/月 |
| Vercel | Hobby | $0 | 100GB帯域/月 |
| **合計** | | **$0** | |

---

## 注意事項

### Render 無料プランの制限
- **15分間アクセスがないとスリープ**（次のアクセスで30秒のコールドスタート）
- 月750時間まで（1サービスなら十分）
- ディスクは永続化されない（DB は Supabase に外出ししているので問題なし）

### 使えない機能（無料構成）
- **Celery ワーカー**: 非同期タスク（動画分析、クローリング）は動かない
- **MinIO**: 動画ファイルのストレージは使えない
- **ML 推論**: YOLOv8, Whisper 等の重い処理は除外
- これらは有料プランに移行時に追加可能

### Supabase 90日ルール
- 90日間アクセスがないとDBが一時停止（ダッシュボードから再開可能）
- 定期的にアクセスするか、cron で `/health` を叩く

---

## スリープ対策（オプション）

Render のスリープが気になる場合、UptimeRobot（無料）で定期 ping:

1. https://uptimerobot.com にアクセス
2. **Add New Monitor** → HTTP(s)
3. URL: `https://[your-app].onrender.com/health`
4. Interval: **5 minutes**

> ただし Render の利用規約上、無料プランでの常時起動は非推奨です。
