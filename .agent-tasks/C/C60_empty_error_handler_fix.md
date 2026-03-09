# C60: ads.py/media.py 空エラーハンドラ修正

## 優先度: 🅰️ A（クリティカル）

## 問題
- `ads.py` に約7箇所の空 `except: pass` がある
- `media.py` に約3箇所の空 `except: pass` がある
- エラーが黙殺され、デバッグ不可能・データ不整合の原因になりうる

## 対象ファイル
- `backend/app/api/endpoints/ads.py`
- `backend/app/api/endpoints/media.py`

## 修正方針

### 全箇所共通パターン
```python
# Before
try:
    ...
except Exception:
    pass

# After
try:
    ...
except Exception as e:
    logger.warning(f"Non-critical error in {context}: {e}", exc_info=True)
    # 必要に応じてHTTPErrorResponseを返す
```

### 分類ルール
1. **ユーザーリクエスト処理中のエラー** → 適切なHTTPステータス(400/404/500)を返す
2. **バックグラウンド処理のエラー** → ログ記録 + 処理続行
3. **クリーンアップ処理のエラー** → ログ記録のみ（メイン処理に影響させない）

### ads.py 修正箇所（7箇所）
1. 広告作成時のバリデーションエラー → 400 Bad Request
2. 広告更新時のDB書き込みエラー → 500 Internal Server Error
3. 広告削除時の存在確認エラー → 404 Not Found
4. メタデータパース失敗 → ログ + デフォルト値使用
5-7. その他 → 個別確認して適切な処理

### media.py 修正箇所（3箇所）
1. メディアファイルのS3フェッチ失敗 → 404/502
2. サムネイル生成失敗 → ログ + プレースホルダー返却
3. プロキシリクエスト失敗 → 502 Bad Gateway

## 完了条件
- [ ] ads.pyの全`pass`文が適切なエラーハンドリングに置換
- [ ] media.pyの全`pass`文が適切なエラーハンドリングに置換
- [ ] 各エラーがstructlogで記録される
- [ ] 本番環境でスタックトレースがユーザーに露出しない
- [ ] 既存の正常系テストが通過する

## 制約
- エンドポイントのURL/パラメータ仕様は変更しない
- 正常系の動作に影響を与えない
