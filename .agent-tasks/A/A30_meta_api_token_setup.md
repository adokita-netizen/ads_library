# A30: Meta APIトークン更新・設定

## 目的
現在無効になっている Meta API トークンを更新し、DB + 環境変数に設定する。
Playwright メディア抽出パイプラインの `render_ad` URL 生成に必須。

## 背景
- 現在のトークンは **無効** (2026-03-01時点)
- `media_tasks.py` の `_build_render_ad_url()` がトークンを使って `render_ad` URL を構築
- トークンがないと snapshot_url フォールバック（精度が落ちる）

## タスク

### 1. ユーザーからトークンを受領
- Facebook Developer Console → Graph API Explorer でトークン生成
- 必要なスコープ: `ads_read`, `business_management`
- 長期トークン (60日) を推奨

### 2. DB に保存
```bash
cd C:/Users/ishit/ads_library/backend
python -c "
from app.core.database import SyncSessionLocal
from sqlalchemy import text

session = SyncSessionLocal()

# 既存トークンを無効化
session.execute(text(\"\"\"
    UPDATE platform_api_keys
    SET is_active = false
    WHERE platform = 'meta' AND key_name = 'access_token'
\"\"\"))

# 新トークンを挿入
session.execute(text(\"\"\"
    INSERT INTO platform_api_keys (platform, key_name, key_value, is_active, created_at)
    VALUES ('meta', 'access_token', :token, true, NOW())
\"\"\"), {'token': 'NEW_TOKEN_HERE'})

session.commit()
session.close()
print('Token updated successfully')
"
```

### 3. Lambda 環境変数にも設定
```bash
aws lambda update-function-configuration \
  --function-name vaap-production-api \
  --environment "Variables={META_ACCESS_TOKEN=NEW_TOKEN_HERE,...既存変数...}"
```

### 4. トークン有効性テスト
```bash
aws lambda invoke --function-name vaap-production-api \
  --payload '{"action": "test_network"}' \
  output.json
cat output.json | python -m json.tool
```
- `meta_stored_token.status` が `200` であること
- `meta_app_token.status` が `200` であること

## 確認項目
- [ ] DB の `platform_api_keys` に有効なトークンが存在
- [ ] Lambda 環境変数に `META_ACCESS_TOKEN` がセット済み
- [ ] `test_network` アクションで Meta API が正常応答

## 制約
- トークン値はログ・コミットに含めないこと
- `.env` にもコミットしない
