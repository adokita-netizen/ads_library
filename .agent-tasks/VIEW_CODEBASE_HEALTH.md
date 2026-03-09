# コードベースヘルス視点 — コードの健全性を数値で把握する

## サイズ指標

### バックエンド
```
backend/app/api/endpoints/
  rankings.py      14,779 行  ← ★ RED: 分割必要
  media.py         99,578 行  ← ★ RED: 異常、要調査
  ads.py           ~1,000 行  ← OK
  settings.py      ~500 行    ← OK
  (他8ファイル)    ~300-800行  ← OK

backend/app/services/
  crawling/        10ファイル  ← OK (1クローラー1ファイル)
  cv/              7ファイル   ← OK
  audio/           4ファイル   ← OK
  generative/      3ファイル   ← OK
  lp_analysis/     4ファイル   ← OK
  meta_marketing/  8ファイル   ← OK
  competitive/     5ファイル   ← OK
  prediction/      3ファイル   ← OK
  ranking/         2ファイル   ← OK (ただし薄い → ロジックがrankings.pyに)

backend/scripts/   ~15ファイル ← OK (各スクリプト100-500行)
```

### フロントエンド
```
frontend/src/components/dashboard/
  HitAdAnalysisView.tsx  推定2000-3000行 ← ★ YELLOW: 肥大化
  ProRankingView.tsx     推定500-800行   ← OK
  ProRankingTable.tsx    推定400-600行   ← OK
  AdDetailModal.tsx      推定500-800行   ← OK
  (他15+コンポーネント) 各100-400行     ← OK

frontend/src/app/
  page.tsx               推定300-500行   ← YELLOW: 22個のimport + switch

frontend/src/lib/
  api.ts                 推定300-500行   ← OK
```

---

## 複雑度指標

### 高複雑度ファイル（推定）

| ファイル | 行数 | 関数数 | 問題 |
|---------|------|--------|------|
| rankings.py | 14,779 | 105+ | 関数あたり平均140行 → 高すぎ |
| media.py | 99,578 | 30+ | 1関数が数千行の可能性 → 異常 |
| HitAdAnalysisView.tsx | 2000+ | 15+ state | useState 20個以上 → 分割必要 |
| page.tsx | 300+ | - | 22個のdynamic import → 管理限界 |

### 循環依存の可能性
```
rankings.py → ranking_service.py → Ad model → ad_metadata
                                    ↑
                        rankings.py が直接Ad model も使う
```

---

## コード品質チェックコマンド

### Python
```bash
cd C:/Users/ishit/ads_library/backend

# 行数カウント
find app/ -name "*.py" | xargs wc -l | sort -n | tail -20

# 関数の長さ分析
grep -c "def " app/api/endpoints/rankings.py

# 未使用インポート
pip install autoflake
autoflake --check --remove-all-unused-imports app/api/endpoints/rankings.py

# 型ヒント カバレッジ
pip install mypy
mypy app/ --ignore-missing-imports --no-error-summary 2>&1 | tail -5

# コード複雑度
pip install radon
radon cc app/api/endpoints/rankings.py -s -n C  # C以上の複雑度を表示
radon mi app/api/endpoints/rankings.py           # メンテナビリティインデックス
```

### TypeScript/React
```bash
cd C:/Users/ishit/ads_library/frontend

# 行数カウント
find src/ -name "*.tsx" -o -name "*.ts" | xargs wc -l | sort -n | tail -20

# TypeScript エラー
npx tsc --noEmit 2>&1 | tail -20

# ESLint
npx eslint src/ --ext .tsx,.ts 2>&1 | tail -30

# 未使用エクスポート
npx ts-unused-exports tsconfig.json 2>&1 | head -20
```

---

## media.py 99,578行の調査

### なぜ99,578行になったか（仮説）
1. バイナリデータがBase64でソースに埋め込まれている?
2. 自動生成コードが含まれている?
3. 巨大なルックアップテーブルがある?
4. テスト用のモックデータが含まれている?

### 調査コマンド
```bash
# ファイルサイズ確認
ls -lh backend/app/api/endpoints/media.py

# 先頭100行
head -100 backend/app/api/endpoints/media.py

# 末尾100行
tail -100 backend/app/api/endpoints/media.py

# 関数定義の一覧
grep -n "^def \|^async def \|^class " backend/app/api/endpoints/media.py

# Base64 の存在確認
grep -c "base64" backend/app/api/endpoints/media.py

# 巨大な文字列リテラル
grep -n '"""' backend/app/api/endpoints/media.py | head -20
```

### 対策
- Base64データがある → 外部ファイルに分離
- 自動生成 → 生成スクリプトを保持、生成物は .gitignore
- 不要コード → 削除

---

## テストカバレッジ

### 現状: ほぼ0%（推定）
```bash
cd C:/Users/ishit/ads_library/backend

# テストファイルの存在確認
find . -name "test_*.py" -o -name "*_test.py" | head -20
ls tests/ 2>/dev/null

# カバレッジ計測（テストがあれば）
pytest --cov=app --cov-report=term-missing tests/
```

### 目標カバレッジ
| 層 | 現状 | v0.1 | v1.0 |
|----|------|------|------|
| API スモーク | 0% | 100% | 100% |
| サービス層 | 0% | 20% | 60% |
| モデル層 | 0% | 0% | 30% |
| フロント | 0% | ビルドのみ | 20% |

---

## Git 統計

```bash
cd C:/Users/ishit/ads_library

# コミット数
git log --oneline | wc -l

# ファイル数
git ls-files | wc -l

# 言語別行数
git ls-files | xargs wc -l | sort -n | tail -5

# 最近のコミット
git log --oneline -20

# 変更が多いファイル（ホットスポット）
git log --pretty=format: --name-only | sort | uniq -c | sort -rn | head -20
```

---

## 健全性スコアカード

| 項目 | 状態 | スコア | アクション |
|------|------|--------|-----------|
| ファイルサイズ | rankings 14K, media 99K | 🔴 2/10 | 分割 |
| テストカバレッジ | ~0% | 🔴 1/10 | スモークテスト追加 |
| 型安全性 | Python: 部分的, TS: strict | 🟡 5/10 | mypy 導入 |
| 依存パッケージ | 100+, Lambda/Worker未分離 | 🟡 4/10 | 分離 |
| エラーハンドリング | 不統一 | 🟡 4/10 | カスタム例外 |
| ドキュメント | .agent-tasks に集中 | 🟡 5/10 | コード内コメント |
| セキュリティ | CORS *, APIキー平文 | 🔴 3/10 | 即修正 |
| パフォーマンス | 未計測 | 🟡 ?/10 | ベンチマーク |
| CI/CD | GitHub Actions あり | 🟢 7/10 | テスト追加 |
| インフラ | Terraform 管理 | 🟢 7/10 | - |

**総合スコア: 3.8/10** → v0.1 リリース前に最低 5/10 を目指す
