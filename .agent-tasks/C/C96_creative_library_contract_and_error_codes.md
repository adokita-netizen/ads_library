# C96: Creative Library Contract Hardening & Error Codes

## 優先度: 🅰️ A（クリティカル）

## 問題
- フロントが「見れる/DLできる/素材不足」を安定表示するには、API契約の固定が必要
- `media.py` と `rankings.py` で素材関連フィールドが散っており、UIが推測で補完している
- DL失敗時の理由コードがUIに渡っていない

## 対象ファイル
- `backend/app/api/endpoints/media.py`
- `backend/app/api/endpoints/rankings.py`
- `backend/app/schemas/ad.py`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装方針

### 1. 広告単位の素材状態を固定構造で返す
返却候補:

```json
{
  "media_status": {
    "viewable": true,
    "downloadable": true,
    "has_lp": true,
    "primary_type": "video",
    "missing_reasons": []
  }
}
```

### 2. ダウンロード失敗理由コードを標準化
- `no_cached_media`
- `zip_creation_failed`
- `invalid_ad_ids`
- `download_file_missing`

### 3. rankings 系レスポンスへ同梱
- 一覧カード/詳細が追加APIなしで描画できる最小限の状態を `rankings` 側でも返す
- `download_urls` と別に `media_status` を返す

### 4. 契約書更新
- `API_CONTRACT_REGISTRY.md` にレスポンス例を追加
- B が参照すべき必須フィールドを明文化

## 完了条件
- [x] `viewable/downloadable/has_lp/primary_type/missing_reasons` が固定構造で返る
- [x] DL失敗理由コードがUIに渡せる
- [x] `rankings.py` と `media.py` の素材契約が揃う
- [x] `API_CONTRACT_REGISTRY.md` が更新される

## 制約
- B が既に読んでいる既存フィールドは削除しない
- snake_case を正とする
