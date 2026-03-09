# フロントエンドアーキテクチャ視点 — 22ビューの構造と改善点

## 現在の構造

### page.tsx — 神コンポーネント
```
page.tsx (Home)
  ├── ConnectivityBanner          ← API接続チェック
  ├── Sidebar                     ← 21ナビゲーション項目
  └── renderView(currentView)     ← switch文で22ビュー切替
        ├── case "pro-database"   → <ProRankingView />
        ├── case "search"         → <AdLibraryTable />
        ├── case "hit-ads"        → <HitAdAnalysisView />
        ├── case "trend"          → <TrendView />
        ├── ... (18個のcase)
        └── default               → <ProRankingView />
```

### 問題
1. **page.tsx が巨大** — 22個の dynamic import + state管理 + renderView
2. **全ビューがフラット** — Next.js の routing を使っていない
3. **状態が page.tsx に集中** — currentView, selectedAd, etc.
4. **ビュー間のデータ共有が無い** — 各ビューが独立してAPI呼び出し

---

## コンポーネント依存マップ

```
HitAdAnalysisView.tsx (最大・最複雑)
  ├── HitAdCardView.tsx          ← カードビュー
  ├── CreativeGalleryView.tsx    ← ギャラリービュー
  ├── AdDetailModal.tsx          ← 詳細モーダル
  │     ├── CreativeViewer.tsx   ← メディア表示
  │     └── SimilarAdsPanel.tsx  ← 類似広告
  ├── HitPatternPanel.tsx        ← ヒットパターン
  ├── CopyAnalysisPanel.tsx      ← コピー分析
  ├── CrawlPanel.tsx             ← クロールトリガー
  ├── FreshAdsSection.tsx        ← 最新広告
  ├── TrendCharts.tsx            ← トレンドチャート
  ├── MarketOverview.tsx         ← マーケット概要
  ├── AdvertiserLeaderboard.tsx  ← 広告主ランキング
  ├── WinningFormulas.tsx        ← 勝ちフォーミュラ
  ├── AdComparisonView.tsx       ← 広告比較
  └── (sectionTab切替で表示)

ProRankingView.tsx (メインビュー)
  ├── SmartSearchBar.tsx         ← 検索バー
  ├── ProRankingTable.tsx        ← ランキングテーブル
  └── (ジャンルサイドバー内蔵)
```

---

## 肥大化ファイルの分析

### HitAdAnalysisView.tsx
- **修正回数**: 13回以上（#3, #5, #6, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17）
- **推定行数**: 2000-3000行
- **含む機能**: テーブル, カード, ギャラリー, 広告主別, 比較, マーケット, フィルター, ソート, エクスポート, スコア分布, ジャンル比較, ヒットパターン, コピー分析, クロール, 最新広告
- **問題**: 1コンポーネントに15+機能 → 変更のたびに全体に影響

### 分割案
```
HitAdAnalysisView.tsx (オーケストレーター)
  ├── hooks/
  │     ├── useHitAdsData.ts        ← データフェッチ
  │     ├── useHitAdsFilters.ts     ← フィルター状態
  │     └── useHitAdsExport.ts      ← エクスポート
  ├── sections/
  │     ├── SummaryCards.tsx         ← サマリーカード6枚
  │     ├── FilterBar.tsx           ← フィルターバー
  │     ├── ScoreDistribution.tsx   ← スコア分布チャート
  │     └── GenreComparison.tsx     ← ジャンル比較
  └── views/
        ├── TableView.tsx           ← テーブルビュー
        ├── CardView.tsx            ← カードビュー
        ├── GalleryView.tsx         ← ギャラリービュー
        └── AdvertiserView.tsx      ← 広告主別ビュー
```

---

## 状態管理の改善

### 現状: useState の乱立（推定）
```typescript
// HitAdAnalysisView.tsx 内に大量の useState
const [ads, setAds] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);
const [selectedGenre, setSelectedGenre] = useState('all');
const [viewMode, setViewMode] = useState('table');
const [sectionTab, setSectionTab] = useState('analysis');
const [scoreRange, setScoreRange] = useState([0, 100]);
const [searchText, setSearchText] = useState('');
const [selectedIds, setSelectedIds] = useState([]);
const [showExport, setShowExport] = useState(false);
const [dashboardSummary, setDashboardSummary] = useState(null);
const [genreComparison, setGenreComparison] = useState(null);
// ... 20個以上
```

### 改善案 1: Zustand ストア（既にインストール済み）
```typescript
// stores/hitAdsStore.ts
import { create } from 'zustand';

interface HitAdsStore {
  ads: Ad[];
  loading: boolean;
  filters: {
    genre: string;
    scoreRange: [number, number];
    searchText: string;
    platform: string;
  };
  setAds: (ads: Ad[]) => void;
  setFilter: (key: string, value: any) => void;
  resetFilters: () => void;
}

export const useHitAdsStore = create<HitAdsStore>((set) => ({
  ads: [],
  loading: true,
  filters: {
    genre: 'all',
    scoreRange: [0, 100],
    searchText: '',
    platform: 'all',
  },
  setAds: (ads) => set({ ads }),
  setFilter: (key, value) => set((s) => ({
    filters: { ...s.filters, [key]: value }
  })),
  resetFilters: () => set({ filters: { genre: 'all', scoreRange: [0, 100], searchText: '', platform: 'all' } }),
}));
```

### 改善案 2: React Query のキャッシュ活用（既にインストール済み）
```typescript
// hooks/useProRanking.ts
import { useQuery } from '@tanstack/react-query';

export function useProRanking(filters: Filters) {
  return useQuery({
    queryKey: ['pro-ranking', filters],
    queryFn: () => fetchProRanking(filters),
    staleTime: 5 * 60 * 1000,  // 5分キャッシュ
    retry: 2,
  });
}
```

---

## ルーティングの改善

### 現状: 全ビューが / (ルート) に
```
https://example.com/     ← 全22ビューがここ
```
URLが変わらないので:
- ブラウザの戻る/進むが使えない
- ブックマークできない
- URLを共有できない

### 改善案: Next.js App Router
```
frontend/src/app/
  ├── page.tsx                    ← PRO DATABASE (デフォルト)
  ├── search/page.tsx             ← 検索
  ├── hit-ads/page.tsx            ← ヒット広告分析
  ├── trend/page.tsx              ← トレンド
  ├── analysis/page.tsx           ← 分析
  ├── compare/page.tsx            ← 比較
  ├── settings/page.tsx           ← 設定
  └── layout.tsx                  ← 共通レイアウト (Sidebar)
```

**メリット**:
- URL が変わる → ブックマーク可能
- ブラウザ戻る/進む対応
- コード分割が自動（ページ単位）
- SSG/SSR の選択肢

**コスト**: 大規模リファクタリング → v2.0 で検討

### 暫定対策: URLハッシュ
```typescript
// page.tsx
useEffect(() => {
  const hash = window.location.hash.replace('#', '');
  if (hash) setCurrentView(hash as ViewType);
}, []);

useEffect(() => {
  window.location.hash = currentView;
}, [currentView]);

// → https://example.com/#pro-database
// → https://example.com/#hit-ads
```

---

## バンドルサイズの最適化

### 現状: dynamic import 使用（良い）
```typescript
const ProRankingView = dynamic(() => import('@/components/dashboard/ProRankingView'), { ssr: false });
const HitAdAnalysisView = dynamic(() => import('@/components/dashboard/HitAdAnalysisView'), { ssr: false });
// ... 20個
```

### 確認コマンド
```bash
cd C:/Users/ishit/ads_library/frontend

# バンドル分析
ANALYZE=true npx next build

# チャンクサイズ確認
ls -lhS .next/static/chunks/*.js | head -20
```

### 最適化ポイント
1. **Recharts**: ツリーシェイキング
```typescript
// ❌ 全部インポート
import { BarChart, Bar, XAxis, YAxis } from 'recharts';

// ✅ 個別インポート
import { BarChart } from 'recharts/lib/chart/BarChart';
import { Bar } from 'recharts/lib/cartesian/Bar';
```

2. **Lucide Icons**: 使うアイコンだけ
```typescript
// ❌ 全部インポート
import * as Icons from 'lucide-react';

// ✅ 個別インポート
import { Search, Filter, Download } from 'lucide-react';
```

3. **date-fns**: ロケール最小化
```typescript
// ❌ 全ロケール
import { format } from 'date-fns';

// ✅ 日本語のみ
import { format } from 'date-fns/format';
import { ja } from 'date-fns/locale/ja';
```

---

## アクセシビリティ

### 確認すべきポイント
- [ ] テーブルに `<thead>`, `<tbody>`, `<th scope="col">` がある
- [ ] ボタンに aria-label がある（アイコンのみボタン）
- [ ] モーダルに focus trap がある
- [ ] キーボードナビゲーション（Tab, Enter, Escape）
- [ ] 色のコントラスト比 4.5:1 以上
- [ ] `loading="lazy"` の画像に width/height がある
