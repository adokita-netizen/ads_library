# 日本語/i18n 視点 — 日本語特有の問題と対策

## VAAP は日本語ファーストのプロダクト

### 対象ユーザー
- 日本の広告運用者
- 広告タイトル・テキストは日本語
- UI も日本語

---

## 問題 1: cp932 エンコーディング (Windows)

### 症状
```
UnicodeEncodeError: 'cp932' codec can't encode character
```

### 発生箇所
- Python スクリプトの `print()` で日本語を出力した時
- Windows のコマンドプロンプト/PowerShell がcp932（Shift-JIS）

### 対策
```bash
# 環境変数で UTF-8 強制
export PYTHONIOENCODING=utf-8

# または PowerShell で
$env:PYTHONIOENCODING="utf-8"
chcp 65001
```

### Agent D の INSTRUCTIONS に記載済み
```python
# NG: print("動画抽出完了")
# OK: print("Video extraction complete")
```

### 全エージェント共通ルール
- バックエンドスクリプトの print は英語のみ
- ログ出力 (structlog) は英語のみ
- フロントエンドの日本語表示はJSX内で直接記述

---

## 問題 2: 日本語テキスト検索

### 現状
`/rankings/smart-autocomplete?query=美容` → 動くか未確認

### PostgreSQL の日本語検索
```sql
-- LIKE検索は動くが遅い
WHERE title ILIKE '%美容%'

-- pg_trgm は日本語に弱い（3文字グラム）
-- "美容液" → "美容", "容液" の2グラム → マッチしにくい

-- 全文検索は日本語tokenizer が必要
-- pg_bigm がベター
CREATE EXTENSION IF NOT EXISTS pg_bigm;
CREATE INDEX idx_ads_title_bigm ON ads USING gin(title gin_bigm_ops);
```

### 対策の優先度
1. **今**: ILIKE で十分（58件なら問題なし）
2. **500件**: pg_trgm or pg_bigm の追加を検討
3. **5000件**: ElasticSearch + kuromoji tokenizer

---

## 問題 3: 日本語ジャンル名の一貫性

### 現状のジャンル分類
```
美容, 健康食品, ダイエット, 育毛, サプリメント, コスメ, 脱毛,
スキンケア, 転職, 副業, 投資, 不動産, 保険, 教育, 趣味...
```

### 問題
- `classify_ads.py` のキーワードマッチと `genre-master` のカテゴリ名が一致しない可能性
- "健康食品" vs "ヘルスケア" vs "サプリ" → 表記揺れ
- フロントのジャンルサイドバーとバックエンドの分類が不一致

### 対策
- genre-master に正規化マッピングを定義
- classify_ads.py で genre-master のカテゴリ名のみ使用
- フロントはAPIから取得した名前をそのまま表示（ハードコードしない）

---

## 問題 4: 日本語フォント・レンダリング

### フロントの日本語表示
- Tailwind CSS の `font-sans` → OSのシステムフォント
- macOS: ヒラギノ, Windows: メイリオ/游ゴシック

### 問題が出やすい箇所
- テーブルの列幅: 日本語は英語の2倍幅 → カラムが溢れる
- `text-[11px]`: 日本語だと読みにくい → 最低12px推奨
- `truncate` (text-overflow): 日本語の単語境界が不自然

### 確認ポイント
- PRO DATABASE テーブルの「商材名」カラム: 長い日本語タイトルが切れないか
- 広告主名: 「株式会社〇〇〇〇〇〇〇」が溢れないか
- ジャンルバッジ: 「健康食品」がバッジ内に収まるか

---

## 問題 5: 日本語CSVエクスポート

### 問題
- UTF-8 で出力 → Excel (日本語版) で開くと文字化け
- Excel は BOM (Byte Order Mark) 付き UTF-8 を期待

### 対策
```python
# CSV出力時に BOM を付ける
import csv
import io

output = io.StringIO()
output.write('\ufeff')  # BOM
writer = csv.writer(output)
writer.writerow(['商材名', '広告主', 'ジャンル', 'ヒットスコア'])
# ...
```

### 確認ポイント
- `/rankings/export/csv` のレスポンスに BOM が付いているか
- Content-Type ヘッダー: `text/csv; charset=utf-8-sig`

---

## 問題 6: 日本語NLP (Agent A/C)

### 使用ライブラリ
- **Fugashi + MeCab**: 日本語形態素解析
- **Transformers**: 日本語BERT等

### 問題
- MeCab辞書のインストール: Docker内で `mecab-ipadic-neologd` が必要
- 広告テキストは口語体/広告体 → 標準辞書だとトークン化が不正確
  - 例: "ぷるぷるお肌" → "ぷるぷる" + "お" + "肌" (正しい)
  - 例: "お肌の曲がり角" → "お肌" + "の" + "曲がり角" (慣用句)

### Dockerfile.worker の確認
```dockerfile
# MeCab + 辞書がインストールされているか
RUN apt-get install -y mecab libmecab-dev mecab-ipadic-utf8
```

---

## 問題 7: Meta Ad Library の日本語データ

### 特徴
- 広告タイトル: 日本語 + 絵文字 + 記号混在
  - "【期間限定】92%OFFセール🎉✨"
- 広告主名: 「株式会社」「合同会社」が多い
- テキスト: 改行 + 箇条書き + URL 混在

### データクレンジングの注意
```python
# 絵文字は残す（クリエイティブ分析の特徴量になる）
# 記号は正規化（全角→半角、【】→[]）
# 空白は正規化（全角スペース→半角スペース）
import unicodedata
title = unicodedata.normalize('NFKC', title)
```

---

## チェックリスト

### バックエンド
- [ ] 全スクリプトの print が英語のみ
- [ ] PYTHONIOENCODING=utf-8 が設定されている
- [ ] CSV エクスポートに BOM が付いている
- [ ] PostgreSQL の日本語検索が動く（ILIKE最低限）
- [ ] MeCab + 辞書が Worker にインストールされている

### フロントエンド
- [ ] 日本語テキストが truncate で不自然に切れない
- [ ] テーブルカラム幅が日本語に適切
- [ ] フォントサイズ最低12px（テーブル以外）
- [ ] ジャンルバッジが日本語で収まる
- [ ] 検索入力で日本語IMEが正常動作

### API
- [ ] ジャンル名がバックエンドとフロントで一致
- [ ] オートコンプリートが日本語で動く
- [ ] エラーメッセージが日本語（ユーザー向け）/ 英語（ログ向け）で分離
