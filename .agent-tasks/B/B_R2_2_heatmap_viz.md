# B-R2-2: Heatmap & Analytics Visualization (B30)
# 優先度: P1 | 前提: なし | ブロック: なし

## 目的
曜日×時間帯のヒートマップで広告配信密度を可視化する。

## 対象ファイル
- 新規: `frontend/src/components/dashboard/HeatmapView.tsx`
- 修正: `frontend/src/app/page.tsx` (ビュー追加)

## 実装

### HeatmapView.tsx
```tsx
// 曜日×時間帯のヒートマップ
// データソース: GET /api/v1/rankings/trends/heatmap (あれば) or ローカル計算

interface HeatmapCell {
  day: number;    // 0=日, 1=月, ..., 6=土
  hour: number;   // 0-23
  value: number;  // 広告数
}

// SVGベースの描画（ライブラリ不要）
const DAYS = ['日', '月', '火', '水', '木', '金', '土'];
const CELL_SIZE = 28;
const CELL_GAP = 2;

function getColor(value: number, max: number): string {
  if (max === 0) return '#f3f4f6';
  const ratio = value / max;
  if (ratio < 0.25) return '#dbeafe';      // 青 薄
  if (ratio < 0.5) return '#93c5fd';       // 青
  if (ratio < 0.75) return '#fbbf24';      // 黄
  return '#ef4444';                         // 赤
}

// レイアウト:
// Y軸: 曜日 (7行)
// X軸: 時間帯 (24列)
// 各セル: value に応じた色付き矩形
// ホバー: ツールチップで「月曜 14:00 - 23件」
// フィルター: ジャンルセレクト, プラットフォームセレクト
```

### 追加ビジュアライゼーション（同コンポーネント内）

#### スコア分布ヒストグラム
```
- X軸: スコア帯 (0-10, 10-20, ..., 90-100)
- Y軸: 広告数
- HITライン (閾値) を縦の破線で表示
- バーの色: 閾値以下=灰, 閾値以上=青, 大HIT=金
```

#### 広告寿命分布
```
- X軸: 配信日数 (0-7, 7-14, 14-30, 30-60, 60-90, 90+)
- Y軸: 広告数
- flash/short/medium/long_runner の色分け
```

### page.tsx 統合
```tsx
// analytics-dashboard or 新しい "heatmap" ビュータイプに追加
case "analytics-dashboard":
  return <HeatmapView />;
```

## API連携
```
GET /api/v1/rankings/trends/heatmap?genre=all
→ { cells: [{ day, hour, value }], max_value: number }

フォールバック: APIが404の場合、既存の広告データから
delivery_start_time を元にローカル計算
```

## 完了条件
- [ ] ヒートマップが SVG で描画される
- [ ] ホバーツールチップが動作する
- [ ] ジャンルフィルターが動作する
- [ ] スコア分布ヒストグラムが表示される
- [ ] 広告寿命分布が表示される
- [ ] ビルド成功
- [ ] status.md に記録
