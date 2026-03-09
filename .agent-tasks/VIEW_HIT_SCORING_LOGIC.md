# ヒットスコアリングロジック視点 — スコアの意味と改善方法

## VAAP の核心: 「何がヒットか」を判定する

---

## 現在の5シグナルスコアリング

### Signal 1: 配信継続力 (Longevity Score)
**考え方**: 長く配信され続けている広告 = 効果がある
```
days_running < 7   → 0点 (新規、判定不能)
days_running 7-14  → 30点
days_running 14-30 → 50点
days_running 30-60 → 70点
days_running 60-90 → 85点
days_running > 90  → 100点
```
**データ元**: `ad_metadata.delivery_start_time` から計算
**問題**: delivery_start_time が NULL → 0点になる → 全広告0点の可能性

### Signal 2: 推定消化額 (Spend Score)
**考え方**: 多く消化されている広告 = 効果がある
```
spend = CPM × estimated_impressions / 1000
CPM推定 = プラットフォーム別 (Facebook: ¥300-800, Instagram: ¥400-1000, ...)
impressions推定 = audience_size × reach_rate

spend < ¥50,000   → 20点
spend ¥50K-200K   → 40点
spend ¥200K-500K  → 60点
spend ¥500K-1M    → 80点
spend > ¥1M       → 100点
```
**データ元**: `ad_metadata.estimated_audience_min/max`, `ad_metadata.impressions_from_audience`
**問題**: Meta API データが無いと推定不能 → 全広告20点

### Signal 3: 配信中ボーナス (Active Bonus)
**考え方**: 今も配信中 = まだ効果が出ている
```
is_still_running = true  → 30点ボーナス
is_still_running = false → 0点ボーナス
is_still_running = null  → 0点ボーナス
```
**データ元**: `ad_metadata.is_still_running`
**問題**: 生存チェック未実行 → 全広告 null → ボーナスなし

### Signal 4: クリエイティブ品質 (Creative Quality Score)
**考え方**: 高品質なクリエイティブ = プロが作成 = 予算がある
```
video + high_resolution → 80点
video + standard_resolution → 60点
image + high_quality → 50点
image + low_quality → 30点
no_media → 10点
```
**データ元**: `ad_metadata.creative_quality`, `creative_type`, `resolution_*`
**問題**: メディア抽出未実行 → creative_quality = null → 低スコア

### Signal 5: トレンドスコア (Trend Score)
**考え方**: 急激に伸びている広告 = 今ホット
```
velocity = (current_metrics - previous_metrics) / time_delta
acceleration = (current_velocity - previous_velocity) / time_delta

high velocity + positive acceleration → 100点 (急成長)
high velocity + negative acceleration → 70点 (成長鈍化)
low velocity + positive acceleration  → 50点 (成長開始)
low velocity + negative acceleration  → 20点 (衰退)
no data → 30点 (不明)
```
**データ元**: `ad_metrics` テーブル（日次データ）
**問題**: 日次データが存在しない → 全広告30点

### 最終スコア計算
```
hit_score = (longevity × 0.25) + (spend × 0.25) + (active × 0.15) + (creative × 0.15) + (trend × 0.20)

hit_level:
  hit_score >= 75 → "mega_hit"
  hit_score >= 55 → "hit"
  hit_score >= 35 → "normal"
  hit_score < 35  → "low"
```

---

## 現状の問題: データ不足でスコアが意味をなさない

### 最悪ケース（現状に近い）
```
Signal 1 (配信継続力): delivery_start_time = NULL → 0点
Signal 2 (消化額):     audience_data = NULL → 20点
Signal 3 (配信中):     is_still_running = NULL → 0点
Signal 4 (クリエイティブ): creative_quality = NULL → 10点
Signal 5 (トレンド):    ad_metrics = empty → 30点

hit_score = (0×0.25) + (20×0.25) + (0×0.15) + (10×0.15) + (30×0.20)
          = 0 + 5 + 0 + 1.5 + 6
          = 12.5 → "low"
```

**全広告が "low" → ランキングが意味をなさない**

### データを埋めた場合
```
Signal 1: delivery_start_time あり → 30-100点
Signal 2: audience推定あり → 40-100点
Signal 3: 生存チェック済み → 0 or 30点
Signal 4: メディア抽出済み → 30-80点
Signal 5: 推定値使用 → 20-70点

hit_score = 20-75 → ランキングに差が出る → 意味がある
```

---

## スコア改善のアクションプラン

### Step 1: Signal 1 を埋める (Agent A)
```bash
python -m scripts.collect_delivery_dates
# delivery_start_time が NULL → snapshot_url からスクレイピング
# または created_at をフォールバックに使う
```

### Step 2: Signal 2 をフォールバック推定 (Agent C)
```python
# audience_data が無い場合のフォールバック:
# days_running × platform_avg_daily_spend で推定
if not audience_data:
    spend_estimate = days_running * PLATFORM_AVG_DAILY_SPEND[platform]
    # Facebook: ¥5,000/日, Instagram: ¥7,000/日, YouTube: ¥10,000/日
```

### Step 3: Signal 3 を埋める (Agent A)
```bash
python -m scripts.check_ad_survival
# snapshot_url にアクセスして配信中かチェック
```

### Step 4: Signal 4 を埋める (Agent D)
```bash
python -m scripts.extract_missing_videos
python -m scripts.fix_bad_thumbnails
# creative_type + resolution でスコア計算
```

### Step 5: Signal 5 をフォールバック推定 (Agent C)
```python
# ad_metrics が無い場合:
# days_running + is_still_running からトレンドを推定
if no_daily_metrics:
    if is_still_running and days_running > 30:
        trend_score = 70  # 長期配信中 = 安定成長
    elif is_still_running and days_running <= 30:
        trend_score = 50  # 短期配信中 = 成長初期
    elif not is_still_running and days_running > 60:
        trend_score = 40  # 長期配信→停止 = 成熟→衰退
    else:
        trend_score = 25  # 短期配信→停止 = 失敗?
```

---

## 将来のスコア改善案

### 追加シグナル候補

| シグナル | データ元 | 実装難易度 | 価値 |
|---------|---------|-----------|------|
| いいね数の伸び | ad_metrics | ★★☆ | ★★★ |
| コメント感情 | NLP分析 | ★★★ | ★★☆ |
| 類似広告数 | 埋め込み類似度 | ★★★ | ★★★ |
| 広告主の信頼度 | 過去実績 | ★★☆ | ★★☆ |
| LP品質 | LP分析 | ★★★ | ★★★ |
| テキスト品質 | NLP分析 | ★★☆ | ★★☆ |
| カルーセル枚数 | メディア抽出 | ★☆☆ | ★☆☆ |

### ML ベーススコアリング（A22タスク）
- 教師データ: 過去のヒット広告（人間がラベル付け or ルールベース）
- 特徴量: 31特徴量（feature_engineering.py に定義済み）
- モデル: LogisticRegression → XGBoost → NN
- **最低必要データ**: 500件（ヒット100件 + 非ヒット400件）

---

## ヒットラインの定義

### 動画広告分析プロの方式（参考）
- 業界・ジャンル別に「ヒットライン」を設定
- 再生数がヒットラインを超えた広告 = HIT
- 例: 美容ジャンル → 再生数 5万回以上 = HIT

### VAAP の方式
```
相対的ヒット判定:
- 同ジャンル内で上位20% → HIT
- 同ジャンル内で上位5% → MEGA HIT

絶対的ヒット判定:
- hit_score >= 75 → MEGA HIT
- hit_score >= 55 → HIT
```

### PRO DATABASE のヒットライン表示
```
genre-master API が返す hit_line_views:
- ジャンル内の上位20%の平均再生数
- テーブルでこのラインを超えた行に金色背景 + HITLINEバッジ
```

---

## スコアの信頼度表示

### フロントで表示すべき情報
```
ヒットスコア: 72.5 (★★★★☆)
信頼度: 高/中/低

高: 全5シグナルにデータあり
中: 3-4シグナルにデータあり
低: 1-2シグナルのみ → 「推定値が多いため参考程度」
```

### 実装
```python
# スコアと一緒に信頼度を返す
data_completeness = sum([
    1 if delivery_start_time else 0,
    1 if audience_data else 0,
    1 if is_still_running is not None else 0,
    1 if creative_quality else 0,
    1 if daily_metrics else 0,
]) / 5

confidence = "high" if data_completeness >= 0.8 else "medium" if data_completeness >= 0.5 else "low"
```
