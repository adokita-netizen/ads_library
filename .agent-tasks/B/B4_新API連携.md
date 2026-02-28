# Agent B 次フェーズ: 新分析API連携

## 概要
Agent Cが構築した新しい分析APIエンドポイントとフロントエンドを連携させる。
スコア内訳ポップオーバー、広告主詳細モーダル、配信日数分析チャートを実装。

## 必ず最初に読むファイル
```
frontend/src/components/dashboard/HitAdAnalysisView.tsx  ← 主要な修正対象
frontend/src/components/analysis/ProductDetailModal.tsx   ← モーダルの既存実装
frontend/src/lib/api.ts                                  ← fetchApi関数
```

## 利用可能な新API（Agent C実装済み）
```
GET /rankings/score-breakdown/{ad_id}    → 個別スコア内訳（signals詳細付き）
GET /rankings/score-distribution         → スコア分布データ
GET /rankings/advertiser-detail?advertiser_name=X  → 広告主の全広告分析
GET /rankings/top-advertisers?limit=20&sort_by=total_spend  → 広告主ランキング
GET /rankings/longevity-analysis         → 配信日数vs.スコア相関
```

---

## タスク1: スコア内訳ポップオーバー

### 概要
テーブルのヒットスコア欄をクリックしたとき、ポップオーバーで詳細なスコア内訳を表示。

### データ取得
```tsx
const [scoreDetail, setScoreDetail] = useState<any>(null);
const [scoreDetailAdId, setScoreDetailAdId] = useState<number | null>(null);

const handleScoreClick = async (e: React.MouseEvent, adId: number) => {
  e.stopPropagation();
  if (scoreDetailAdId === adId) {
    setScoreDetailAdId(null);
    return;
  }
  const data = await fetchApi(`/rankings/score-breakdown/${adId}`);
  setScoreDetail(data);
  setScoreDetailAdId(adId);
};
```

### ポップオーバーUI
```tsx
{scoreDetailAdId === ad.ad_id && scoreDetail && (
  <div className="absolute z-50 right-0 top-full mt-1 w-64 card shadow-lg p-3">
    <p className="text-[12px] font-bold mb-2">スコア内訳 ({scoreDetail.hit_score}/100)</p>
    {Object.entries(scoreDetail.signals).map(([key, sig]: [string, any]) => (
      <div key={key} className="flex items-center gap-2 mb-1">
        <span className="text-[9px] w-16 text-gray-500">{signalLabels[key]}</span>
        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div className="h-full rounded-full"
               style={{ width: `${(sig.score / sig.max) * 100}%`, backgroundColor: signalColors[key] }} />
        </div>
        <span className="text-[9px] text-gray-600 w-10 text-right">{sig.score}/{sig.max}</span>
      </div>
    ))}
    <p className="text-[8px] text-gray-400 mt-2">{scoreDetail.signals.longevity?.detail}</p>
  </div>
)}
```

### シグナルラベル定数
```tsx
const signalLabels: Record<string, string> = {
  longevity: "配信継続力",
  spend: "消化額",
  active_bonus: "配信中ボーナス",
  creative: "クリエイティブ",
  trend: "トレンド",
};
const signalColors: Record<string, string> = {
  longevity: "#3b82f6",
  spend: "#22c55e",
  active_bonus: "#f97316",
  creative: "#a855f7",
  trend: "#ec4899",
};
```

---

## タスク2: 広告主名クリックで広告主詳細表示

### 概要
テーブルの広告主名をクリックすると、インライン展開で広告主の全広告リストと統計を表示。

### データ取得
```tsx
const [advertiserDetail, setAdvertiserDetail] = useState<any>(null);
const [selectedAdvertiser, setSelectedAdvertiser] = useState<string | null>(null);

const handleAdvertiserClick = async (e: React.MouseEvent, name: string) => {
  e.stopPropagation();
  if (selectedAdvertiser === name) {
    setSelectedAdvertiser(null);
    return;
  }
  const data = await fetchApi(`/rankings/advertiser-detail`, { params: { advertiser_name: name } });
  setAdvertiserDetail(data);
  setSelectedAdvertiser(name);
};
```

### 表示UI
広告主カラムのクリック時に下にインライン展開:
```tsx
<span
  className="text-[12px] text-[#4A7DFF] cursor-pointer hover:underline truncate max-w-[140px] block"
  onClick={(e) => handleAdvertiserClick(e, ad.advertiser_name)}
>
  {ad.advertiser_name || "-"}
</span>
```

---

## タスク3: スコア分布チャートをAPIデータに切り替え

### 概要
現在のサマリーカード内スコア分布チャートは、ローカルの `hitAds` データから計算している。
新API `/rankings/score-distribution` を使って全広告ベースの正確な分布を表示に切り替え。

### 実装方針
```tsx
// fetchData内で追加取得
const [scoreDistribution, setScoreDistribution] = useState<any>(null);

// fetchData callback内で
const distRes = await fetchApi("/rankings/score-distribution");
setScoreDistribution(distRes);
```

統計情報（mean, median, hit_count, mega_hit_count）もAPIデータで表示。

---

## コンフリクト防止ルール
- `INSTRUCTIONS.md` を厳守
- バックエンドファイルは一切触らない
- 外部ライブラリ追加不可
- 修正後に `cd C:/Users/ishit/ads_library/frontend && npx next build --no-lint` でビルド確認

## 完了条件
- スコアクリックでポップオーバーが表示される
- 広告主名クリックで詳細が展開される
- スコア分布チャートがAPIデータを使用している
- ビルドが通ること
