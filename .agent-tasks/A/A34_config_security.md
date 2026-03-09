# A34: config.py シークレット安全性強化

## 問題
- `secret_key` のデフォルトが固定文字列 → 本番で使用されるリスク
- APIトークンが環境変数に平文保存 → Secrets Manager一元化すべき
- `_resolve_db_secret()` 失敗時にwarning出して続行 → 本番では即エラーにすべき

## 対象ファイル
- `backend/app/core/config.py`

## 修正

### 1. 本番環境でのデフォルト値排除
```python
@field_validator("secret_key")
@classmethod
def _validate_secret_key(cls, v):
    if v == "change-this-to-a-secure-random-string":
        import os
        if os.getenv("APP_ENV") == "production":
            raise ValueError("SECRET_KEY must be set in production")
        # 開発環境ではランダム生成
        import secrets
        return secrets.token_urlsafe(32)
    return v
```

### 2. DB シークレット解決失敗時の本番エラー
```python
# _resolve_db_secret 内
except Exception as e:
    if os.getenv("APP_ENV") == "production":
        raise ValueError(f"Failed to resolve DB secret: {e}")
    logger.warning(...)
```

### 3. ログからのシークレットフィルタリング
lambda_handler.pyの`_test_network()`でトークンがレスポンスに含まれないよう、出力をマスク。

## 制約
- `config.py` のバリデータ追加のみ
- 開発環境の動作は変更しない
