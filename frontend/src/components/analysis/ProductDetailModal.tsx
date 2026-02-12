"use client";

import { useState } from "react";

interface ProductDetailModalProps {
  adId: number;
  onClose: () => void;
}

// Mock data for the selected product
const mockProduct = {
  id: 1,
  managementId: "AD-2025-00147",
  productName: "スキンケアセラムV3",
  advertiserName: "ビューティーラボ株式会社",
  genre: "美容・コスメ",
  totalSpend: 128000000,
  totalPlays: 45200000,
  publishedDate: "2025-12-15",
  duration: 30,
  platforms: ["youtube", "facebook", "instagram", "tiktok"],
  destinationType: "記事LP",
  destination: "https://lp.example.com/serum-v3",
};

// Heatmap data: rows = months, cols = days
const heatmapMonths = ["2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"];
const generateHeatmap = () => {
  return heatmapMonths.map(() => {
    return Array.from({ length: 31 }, () => {
      const r = Math.random();
      if (r < 0.3) return 0;
      if (r < 0.5) return 1;
      if (r < 0.7) return 2;
      if (r < 0.85) return 3;
      return 4;
    });
  });
};

const heatmapData = generateHeatmap();

const heatmapColors = [
  "bg-gray-100",     // 0 - no activity
  "bg-blue-100",     // 1 - low
  "bg-blue-300",     // 2 - medium
  "bg-[#4A7DFF]",    // 3 - high
  "bg-blue-700",     // 4 - very high
];

// Spend trend line data (monthly)
const spendTrend = [
  { month: "7月", spend: 12000000 },
  { month: "8月", spend: 18000000 },
  { month: "9月", spend: 22000000 },
  { month: "10月", spend: 28000000 },
  { month: "11月", spend: 24000000 },
  { month: "12月", spend: 24000000 },
];

// Media distribution
const mediaDistribution = [
  { platform: "YouTube", percentage: 42, color: "bg-red-500" },
  { platform: "Facebook", percentage: 25, color: "bg-blue-600" },
  { platform: "Instagram", percentage: 20, color: "bg-gradient-to-r from-purple-500 to-pink-500" },
  { platform: "TikTok", percentage: 13, color: "bg-gray-900" },
];

// Format distribution
const formatDistribution = [
  { format: "動画 (30秒)", percentage: 55 },
  { format: "動画 (15秒)", percentage: 25 },
  { format: "バナー", percentage: 15 },
  { format: "カルーセル", percentage: 5 },
];

// Competitor data
const competitors = [
  { name: "コスメブランドA", similarity: 92, adCount: 45, genre: "美容・コスメ" },
  { name: "スキンケアB社", similarity: 85, adCount: 32, genre: "美容・コスメ" },
  { name: "ビューティーC", similarity: 78, adCount: 28, genre: "美容・コスメ" },
  { name: "ナチュラルD", similarity: 71, adCount: 19, genre: "美容・コスメ" },
];

// Related ads table data
const relatedAds = [
  { id: "V-001", platform: "youtube", duration: 30, publishedDate: "2025-12-15", plays: 12500000, spend: 35000000, status: "配信中" },
  { id: "V-002", platform: "facebook", duration: 15, publishedDate: "2025-12-18", plays: 8200000, spend: 28000000, status: "配信中" },
  { id: "V-003", platform: "instagram", duration: 30, publishedDate: "2025-11-20", plays: 15800000, spend: 42000000, status: "配信中" },
  { id: "V-004", platform: "tiktok", duration: 15, publishedDate: "2025-11-25", plays: 8700000, spend: 23000000, status: "終了" },
];

const platformLabels: Record<string, string> = {
  youtube: "YT", shorts: "S", tiktok: "TT", facebook: "FB",
  instagram: "IG", line: "L", yahoo: "Y!", x: "X",
};

const platformColors: Record<string, string> = {
  youtube: "platform-youtube", tiktok: "platform-tiktok",
  facebook: "platform-facebook", instagram: "platform-instagram",
  line: "platform-line", yahoo: "platform-yahoo", x: "platform-x",
};

function formatYen(n: number): string {
  if (n >= 100000000) return "¥" + (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return "¥" + (n / 10000).toFixed(0) + "万";
  return "¥" + n.toLocaleString();
}

function formatNumber(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return (n / 10000).toFixed(0) + "万";
  return n.toLocaleString();
}

type TabType = "overview" | "creatives" | "competitors" | "analysis";

export default function ProductDetailModal({ adId, onClose }: ProductDetailModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const _ = adId; // Would be used for API call

  const maxSpend = Math.max(...spendTrend.map((d) => d.spend));

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-8 pb-8">
      <div className="relative w-full max-w-5xl max-h-full overflow-hidden rounded-xl bg-white shadow-2xl flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            {/* Thumbnail placeholder */}
            <div className="w-16 h-10 rounded bg-gray-200 flex items-center justify-center">
              <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
              </svg>
            </div>
            <div>
              <h2 className="text-[15px] font-bold text-gray-900">{mockProduct.productName}</h2>
              <p className="text-[11px] text-gray-400">
                {mockProduct.advertiserName} · {mockProduct.managementId} · {mockProduct.genre}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-secondary text-xs">
              <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
              マイリストに追加
            </button>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 px-6 border-b border-gray-200 bg-[#f8f9fc]">
          {([
            { id: "overview", label: "概要" },
            { id: "creatives", label: "クリエイティブ一覧" },
            { id: "competitors", label: "競合分析" },
            { id: "analysis", label: "AI分析" },
          ] as { id: TabType; label: string }[]).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-[12px] font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-[#4A7DFF] text-[#4A7DFF] bg-white"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
          {activeTab === "overview" && (
            <div className="space-y-5">
              {/* Top Stats */}
              <div className="grid grid-cols-4 gap-3">
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">累計予想消化額</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{formatYen(mockProduct.totalSpend)}</p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">累計再生回数</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{formatNumber(mockProduct.totalPlays)}</p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">出稿媒体数</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{mockProduct.platforms.length}媒体</p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">公開日</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{mockProduct.publishedDate}</p>
                </div>
              </div>

              {/* Heatmap: 全媒体の出稿状況 */}
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-3">全媒体の出稿状況</h3>
                <div className="space-y-1.5">
                  {heatmapMonths.map((month, mIdx) => (
                    <div key={month} className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-400 w-14 shrink-0">{month}</span>
                      <div className="flex gap-px">
                        {heatmapData[mIdx].map((val, dIdx) => (
                          <div
                            key={dIdx}
                            className={`heatmap-cell ${heatmapColors[val]}`}
                            title={`${month}-${(dIdx + 1).toString().padStart(2, "0")}: レベル${val}`}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-1.5 mt-3 justify-end">
                  <span className="text-[9px] text-gray-400">少</span>
                  {heatmapColors.map((color, i) => (
                    <div key={i} className={`w-3 h-3 rounded-sm ${color}`} />
                  ))}
                  <span className="text-[9px] text-gray-400">多</span>
                </div>
              </div>

              {/* Charts row */}
              <div className="grid grid-cols-2 gap-3">
                {/* Spend Trend */}
                <div className="card">
                  <h3 className="text-[13px] font-bold text-gray-900 mb-3">予想消化額推移</h3>
                  <div className="space-y-2">
                    {spendTrend.map((d) => (
                      <div key={d.month} className="flex items-center gap-2">
                        <span className="text-[10px] text-gray-400 w-8 shrink-0">{d.month}</span>
                        <div className="flex-1 h-5 bg-gray-50 rounded overflow-hidden">
                          <div
                            className="h-full bg-[#4A7DFF] rounded transition-all"
                            style={{ width: `${(d.spend / maxSpend) * 100}%` }}
                          />
                        </div>
                        <span className="text-[11px] font-medium text-gray-700 w-16 text-right">{formatYen(d.spend)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Media Distribution */}
                <div className="card">
                  <h3 className="text-[13px] font-bold text-gray-900 mb-3">出稿媒体</h3>
                  <div className="space-y-3">
                    {mediaDistribution.map((m) => (
                      <div key={m.platform}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[11px] text-gray-700 font-medium">{m.platform}</span>
                          <span className="text-[11px] text-gray-500">{m.percentage}%</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${m.color}`}
                            style={{ width: `${m.percentage}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 pt-3 border-t border-gray-100">
                    <h4 className="text-[12px] font-bold text-gray-700 mb-2">形式</h4>
                    <div className="space-y-1.5">
                      {formatDistribution.map((f) => (
                        <div key={f.format} className="flex items-center justify-between">
                          <span className="text-[11px] text-gray-600">{f.format}</span>
                          <span className="text-[11px] text-gray-500">{f.percentage}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Related Ads */}
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-3">この商材の広告一覧</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>媒体</th>
                      <th className="text-center">秒数</th>
                      <th>公開日</th>
                      <th className="text-right">再生回数</th>
                      <th className="text-right">予想消化額</th>
                      <th>ステータス</th>
                    </tr>
                  </thead>
                  <tbody>
                    {relatedAds.map((ad) => (
                      <tr key={ad.id}>
                        <td className="text-[11px] font-mono text-gray-400">{ad.id}</td>
                        <td>
                          <span className={`platform-icon ${platformColors[ad.platform]}`}>
                            {platformLabels[ad.platform]}
                          </span>
                        </td>
                        <td className="text-center text-[12px] text-gray-600">{ad.duration}秒</td>
                        <td className="text-[11px] text-gray-500">{ad.publishedDate}</td>
                        <td className="text-right text-[12px] text-gray-700">{formatNumber(ad.plays)}</td>
                        <td className="text-right text-[13px] font-semibold text-gray-900">{formatYen(ad.spend)}</td>
                        <td>
                          <span className={`badge text-[10px] ${
                            ad.status === "配信中" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
                          }`}>
                            {ad.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "creatives" && (
            <div className="space-y-4">
              <p className="text-[13px] text-gray-500">この商材の全クリエイティブバリエーションを表示します。</p>
              <div className="grid grid-cols-3 gap-3">
                {relatedAds.map((ad) => (
                  <div key={ad.id} className="card hover:shadow-md transition-shadow cursor-pointer">
                    <div className="w-full aspect-video bg-gray-100 rounded-md mb-3 flex items-center justify-center relative">
                      <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                      </svg>
                      <span className="absolute bottom-1 right-1 bg-black/75 text-white text-[9px] px-1.5 rounded">
                        0:{ad.duration.toString().padStart(2, "0")}
                      </span>
                      <span className={`absolute top-1 left-1 platform-icon ${platformColors[ad.platform]}`}>
                        {platformLabels[ad.platform]}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono text-gray-400">{ad.id}</span>
                      <span className={`badge text-[9px] ${
                        ad.status === "配信中" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
                      }`}>
                        {ad.status}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-[11px] text-gray-500">{ad.publishedDate}</span>
                      <span className="text-[12px] font-semibold text-gray-900">{formatYen(ad.spend)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "competitors" && (
            <div className="space-y-4">
              <p className="text-[13px] text-gray-500">同ジャンルの競合商材を類似度順で表示します。</p>
              <div className="space-y-2">
                {competitors.map((comp) => (
                  <div key={comp.name} className="card flex items-center justify-between hover:shadow-md transition-shadow cursor-pointer">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-400">
                        {comp.name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-[13px] font-medium text-gray-900">{comp.name}</p>
                        <p className="text-[10px] text-gray-400">{comp.genre} · 広告{comp.adCount}件</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-[10px] text-gray-400">類似度</p>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-[#4A7DFF]"
                              style={{ width: `${comp.similarity}%` }}
                            />
                          </div>
                          <span className="text-[12px] font-bold text-gray-900">{comp.similarity}%</span>
                        </div>
                      </div>
                      <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "analysis" && (
            <div className="space-y-4">
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-2">AI分析サマリー</h3>
                <div className="space-y-3 text-[12px] text-gray-600 leading-relaxed">
                  <p>
                    <span className="font-semibold text-gray-900">フック分析:</span>{" "}
                    冒頭3秒で「悩み共感型」のフックを使用。ターゲット層（30-40代女性）の肌悩みに直接訴求しており、
                    視聴継続率が業界平均を32%上回っています。
                  </p>
                  <p>
                    <span className="font-semibold text-gray-900">構成パターン:</span>{" "}
                    「問題提起 → 解決策提示 → 社会的証明 → CTA」の王道構成を採用。
                    特に中盤の医師監修ポイントが信頼性構築に効果的です。
                  </p>
                  <p>
                    <span className="font-semibold text-gray-900">勝ちパターン要素:</span>{" "}
                    テキストオーバーレイの使用率が高く（画面の65%にテキスト表示）、音声OFFでも内容が伝わる設計。
                    ビフォーアフター演出が視聴者のCVR向上に寄与しています。
                  </p>
                  <p>
                    <span className="font-semibold text-gray-900">改善提案:</span>{" "}
                    CTAボタンのタイミングを現在の25秒地点から20秒地点に前倒しすることで、
                    推定CVRが15-20%向上する可能性があります。また、サムネイルに人物の顔を大きく配置することで
                    クリック率の改善が見込めます。
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="card text-center py-4">
                  <p className="text-[10px] text-gray-400 font-medium">推定CTR</p>
                  <p className="text-2xl font-bold text-[#4A7DFF] mt-1">3.2%</p>
                  <p className="text-[10px] text-emerald-600 mt-0.5">業界平均+1.1%</p>
                </div>
                <div className="card text-center py-4">
                  <p className="text-[10px] text-gray-400 font-medium">推定CVR</p>
                  <p className="text-2xl font-bold text-[#4A7DFF] mt-1">1.8%</p>
                  <p className="text-[10px] text-emerald-600 mt-0.5">業界平均+0.6%</p>
                </div>
                <div className="card text-center py-4">
                  <p className="text-[10px] text-gray-400 font-medium">勝ちスコア</p>
                  <p className="text-2xl font-bold text-[#4A7DFF] mt-1">87</p>
                  <p className="text-[10px] text-emerald-600 mt-0.5">上位8%</p>
                </div>
              </div>

              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-3">広告疲労度</h3>
                <div className="flex items-center gap-4">
                  <div className="relative w-20 h-20">
                    <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="14" fill="none" stroke="#f3f4f6" strokeWidth="3" />
                      <circle
                        cx="18" cy="18" r="14" fill="none" stroke="#4A7DFF" strokeWidth="3"
                        strokeDasharray="88" strokeDashoffset="53" strokeLinecap="round"
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-gray-900">40%</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-[12px] text-gray-600">
                      現在の疲労度は<span className="font-semibold text-amber-600">やや上昇傾向</span>です。
                      推定残存有効期間は<span className="font-semibold text-gray-900">約21日</span>です。
                    </p>
                    <p className="text-[11px] text-gray-400 mt-1">
                      新しいクリエイティブバリエーションの準備を推奨します。
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
