"use client";

import { useState } from "react";

type CITab = "spend" | "similarity" | "destination" | "alerts" | "trends" | "classification";

// ===== Mock Data =====

const mockSpendEstimate = {
  ad_id: 1,
  estimated_spend: 450000,
  confidence_ranges: { p10: 280000, p25: 350000, p50: 450000, p75: 560000, p90: 680000 },
  cpm_info: { platform_avg: 400, genre_adjusted: 520, seasonal_factor: 1.1, user_calibrated: null as number | null },
  estimation_method: "cpm_model",
  confidence_level: 0.45,
};

const mockCalibrations = [
  { id: 1, platform: "youtube", genre: "美容・コスメ", actual_cpm: 480, notes: "Q4実績", created_at: "2025-12-20" },
  { id: 2, platform: "tiktok", genre: "健康食品", actual_cpm: 320, notes: "11月実績", created_at: "2025-12-15" },
];

const mockSimilarAds = [
  { ad_id: 101, similarity: 0.92, title: "美容セラム 口コミ動画 #2", platform: "YouTube", advertiser_name: "ビューティーラボ", auto_appeal_axes: ["authority", "social_proof"], auto_expression_type: "review" },
  { ad_id: 102, similarity: 0.87, title: "エイジングケア 比較動画", platform: "TikTok", advertiser_name: "コスメティックス", auto_appeal_axes: ["comparison", "benefit"], auto_expression_type: "comparison" },
  { ad_id: 103, similarity: 0.81, title: "医師監修セラム LP動画", platform: "Instagram", advertiser_name: "スキンケアプロ", auto_appeal_axes: ["authority", "benefit"], auto_expression_type: "authority" },
  { ad_id: 104, similarity: 0.76, title: "肌悩み解決 UGC風", platform: "YouTube", advertiser_name: "ナチュラルコスメ", auto_appeal_axes: ["problem_solution", "emotional"], auto_expression_type: "ugc" },
  { ad_id: 105, similarity: 0.72, title: "初回980円 限定オファー", platform: "Facebook", advertiser_name: "ヘルスビューティー", auto_appeal_axes: ["price", "urgency"], auto_expression_type: "tutorial" },
];

const mockLPReuse = [
  { url_hash: "abc123", url: "https://lp.example.com/serum-v3", domain: "lp.example.com", title: "美容セラムV3 記事LP", genre: "美容・コスメ", advertiser_count: 4, ad_count: 12, advertisers: ["ビューティーラボ", "コスメA", "スキンケアB", "美容C"] },
  { url_hash: "def456", url: "https://lp.example.com/diet-x", domain: "lp.example.com", title: "ダイエットX LP", genre: "健康食品", advertiser_count: 3, ad_count: 8, advertisers: ["ヘルスケアジャパン", "サプリA", "ダイエットB"] },
  { url_hash: "ghi789", url: "https://shop.example.com/tonic", domain: "shop.example.com", title: "育毛トニック LP", genre: "ヘアケア", advertiser_count: 2, ad_count: 6, advertisers: ["ヘアケアプロ", "トニックA"] },
];

const mockAlerts = [
  { id: 1, alert_type: "spend_surge", severity: "high", entity_type: "ad", entity_name: "セラムV3 動画広告", title: "消化額急増: セラムV3 (+280%)", description: "直近3日間の予想消化額が前期間比3.8倍に急増。¥120,000 → ¥456,000", change_percent: 280, detected_at: "2025-12-23T10:30:00Z", is_dismissed: false },
  { id: 2, alert_type: "new_competitor_ad", severity: "medium", entity_type: "advertiser", entity_name: "コスメティックス", title: "競合新規出稿: コスメティックス (3件)", description: "コスメティックスが3件の新しい広告を出稿。媒体: YouTube, Instagram", detected_at: "2025-12-23T08:15:00Z", is_dismissed: false },
  { id: 3, alert_type: "category_trend", severity: "high", entity_type: "genre", entity_name: "美容・コスメ", title: "ジャンル急伸: 美容・コスメ (+45%)", description: "美容・コスメの週間予想消化額が45%増加", change_percent: 45, detected_at: "2025-12-22T15:00:00Z", is_dismissed: false },
  { id: 4, alert_type: "lp_swap", severity: "medium", entity_type: "lp", entity_name: "ビューティーラボ", title: "LP変更検出: ビューティーラボ", description: "遷移先LPが変更されました: lp.example.com", detected_at: "2025-12-22T12:00:00Z", is_dismissed: false },
  { id: 5, alert_type: "spend_surge", severity: "medium", entity_type: "ad", entity_name: "ダイエットサプリX", title: "新規高消化: ダイエットサプリX (¥200,000)", description: "新規出稿で3日間の予想消化額が¥200,000に到達", change_percent: 100, detected_at: "2025-12-21T09:00:00Z", is_dismissed: true },
];

const mockTrendPredictions = [
  { ad_id: 201, momentum_score: 92, hit_probability: 0.85, predicted_hit: true, growth_phase: "growth", days_active: 4, genre: "美容・コスメ", genre_percentile: 95, title: "【新発売】美容セラムZ", platform: "YouTube", advertiser_name: "コスメA", velocity: { view_1d: 15000, view_7d: 8000, spend_1d: 120000, spend_7d: 65000, view_acceleration: 0.6, spend_acceleration: 0.5, view_3d: 12000, spend_3d: 100000 } },
  { ad_id: 202, momentum_score: 78, hit_probability: 0.72, predicted_hit: true, growth_phase: "growth", days_active: 6, genre: "健康食品", genre_percentile: 88, title: "プロテインバー 15秒", platform: "TikTok", advertiser_name: "フィットB", velocity: { view_1d: 8000, view_7d: 5000, spend_1d: 80000, spend_7d: 45000, view_acceleration: 0.4, spend_acceleration: 0.3, view_3d: 6500, spend_3d: 65000 } },
  { ad_id: 203, momentum_score: 65, hit_probability: 0.55, predicted_hit: false, growth_phase: "launch", days_active: 2, genre: "ヘアケア", genre_percentile: 75, title: "育毛トニック 新CM", platform: "YouTube", advertiser_name: "ヘアプロC", velocity: { view_1d: 5000, view_7d: 2500, spend_1d: 50000, spend_7d: 25000, view_acceleration: 0.8, spend_acceleration: 0.7, view_3d: 4000, spend_3d: 40000 } },
  { ad_id: 204, momentum_score: 48, hit_probability: 0.35, predicted_hit: false, growth_phase: "peak", days_active: 14, genre: "美容・コスメ", genre_percentile: 60, title: "アイクリーム レビュー", platform: "Instagram", advertiser_name: "コスメD", velocity: { view_1d: 3000, view_7d: 3200, spend_1d: 30000, spend_7d: 32000, view_acceleration: -0.05, spend_acceleration: -0.02, view_3d: 3100, spend_3d: 31000 } },
];

const mockProvisionalTags = [
  { id: 1, ad_id: 301, field_name: "genre", value: "美容・コスメ", confidence: 0.65, classified_by: "auto_fast", created_at: "2025-12-23T09:00:00Z" },
  { id: 2, ad_id: 302, field_name: "genre", value: "健康食品", confidence: 0.55, classified_by: "auto_fast", created_at: "2025-12-23T08:30:00Z" },
  { id: 3, ad_id: 303, field_name: "product_name", value: "ダイエットサプリZ", confidence: 0.48, classified_by: "auto_fast", created_at: "2025-12-23T08:00:00Z" },
  { id: 4, ad_id: 304, field_name: "appeal_axis", value: "authority", confidence: 0.72, classified_by: "auto_fast", created_at: "2025-12-22T16:00:00Z" },
];

// ===== Helper Labels =====

const alertTypeLabels: Record<string, string> = {
  spend_surge: "消化額急増",
  lp_swap: "LP変更",
  new_competitor_ad: "競合新規出稿",
  category_trend: "ジャンルトレンド",
  appeal_change: "訴求変更",
};

const alertTypeColors: Record<string, string> = {
  spend_surge: "bg-red-100 text-red-700",
  lp_swap: "bg-purple-100 text-purple-700",
  new_competitor_ad: "bg-blue-100 text-blue-700",
  category_trend: "bg-emerald-100 text-emerald-700",
  appeal_change: "bg-amber-100 text-amber-700",
};

const severityColors: Record<string, string> = {
  critical: "text-red-600",
  high: "text-red-500",
  medium: "text-amber-500",
  low: "text-gray-400",
};

const growthPhaseLabels: Record<string, string> = {
  launch: "ローンチ",
  growth: "成長中",
  peak: "ピーク",
  plateau: "横ばい",
  decline: "減少",
};

const growthPhaseColors: Record<string, string> = {
  launch: "bg-blue-100 text-blue-700",
  growth: "bg-emerald-100 text-emerald-700",
  peak: "bg-amber-100 text-amber-700",
  plateau: "bg-gray-100 text-gray-600",
  decline: "bg-red-100 text-red-700",
};

const appealAxisLabels: Record<string, string> = {
  benefit: "ベネフィット",
  problem_solution: "悩み解決",
  authority: "権威性",
  social_proof: "社会的証明",
  urgency: "緊急性",
  price: "価格訴求",
  comparison: "比較",
  emotional: "感情訴求",
  fear: "恐怖訴求",
  novelty: "新規性",
};

const expressionTypeLabels: Record<string, string> = {
  ugc: "UGC風",
  comparison: "比較型",
  authority: "権威型",
  review: "レビュー型",
  tutorial: "チュートリアル",
};

export default function CompetitiveIntelView() {
  const [activeTab, setActiveTab] = useState<CITab>("trends");
  const [calibPlatform, setCalibPlatform] = useState("youtube");
  const [calibGenre, setCalibGenre] = useState("");
  const [calibCPM, setCalibCPM] = useState("");
  const [similarQuery, setSimilarQuery] = useState("");

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">競合インテリジェンス</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">
            消化額推定・類似検索・遷移先分析・アラート・トレンド予測・分類管理
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 px-5 border-b border-gray-200 bg-[#f8f9fc] overflow-x-auto">
        {([
          { id: "trends" as CITab, label: "トレンド予測" },
          { id: "alerts" as CITab, label: "アラート" },
          { id: "spend" as CITab, label: "消化額推定" },
          { id: "similarity" as CITab, label: "類似検索" },
          { id: "destination" as CITab, label: "遷移先分析" },
          { id: "classification" as CITab, label: "分類管理" },
        ]).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-[12px] font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? "border-[#4A7DFF] text-[#4A7DFF] bg-white"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {/* ==================== Trend Predictions ==================== */}
        {activeTab === "trends" && (
          <div className="p-5 space-y-4">
            <div className="card bg-gradient-to-r from-emerald-50 to-blue-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22M16.5 2.25L22.5 2.25 22.5 8.25" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">ヒット予測・早期検知</h3>
              </div>
              <p className="text-[11px] text-gray-600">
                再生数の加速度・ジャンル内パーセンタイル・成長フェーズから、ヒット広告を早期に検知します。
                S字カーブモデルで成長局面を判定し、ジャンル別閾値で相対評価します。
              </p>
            </div>

            {/* Predictions table */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-[11px] text-gray-400">{mockTrendPredictions.length}件の予測</p>
                <div className="flex items-center gap-2 text-[9px] text-gray-400">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> 成長中</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> ローンチ</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> ピーク</span>
                </div>
              </div>

              {mockTrendPredictions.map((p) => (
                <div key={p.ad_id} className="card hover:shadow-md transition-shadow">
                  <div className="flex items-start gap-4">
                    {/* Momentum score */}
                    <div className="flex flex-col items-center shrink-0">
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-[14px] ${
                        p.momentum_score >= 80 ? "bg-emerald-500" : p.momentum_score >= 60 ? "bg-blue-500" : p.momentum_score >= 40 ? "bg-amber-500" : "bg-gray-400"
                      }`}>
                        {p.momentum_score}
                      </div>
                      <span className="text-[8px] text-gray-400 mt-0.5">勢いスコア</span>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`badge text-[9px] ${growthPhaseColors[p.growth_phase]}`}>
                          {growthPhaseLabels[p.growth_phase]}
                        </span>
                        {p.predicted_hit && (
                          <span className="badge text-[9px] bg-red-100 text-red-700 font-bold">HIT予測</span>
                        )}
                        <span className="text-[9px] text-gray-400">{p.days_active}日目</span>
                        <span className="text-[9px] text-gray-400">ジャンル内{p.genre_percentile}%ile</span>
                      </div>
                      <p className="text-[12px] font-medium text-gray-900 truncate">{p.title}</p>
                      <p className="text-[10px] text-gray-400">{p.platform} · {p.advertiser_name} · {p.genre}</p>

                      {/* Velocity bars */}
                      <div className="grid grid-cols-4 gap-2 mt-2">
                        <div>
                          <p className="text-[9px] text-gray-400">再生/日(1d)</p>
                          <p className="text-[11px] font-semibold text-gray-700">{(p.velocity.view_1d / 1000).toFixed(1)}k</p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-400">消化/日(1d)</p>
                          <p className="text-[11px] font-semibold text-gray-700">¥{(p.velocity.spend_1d / 1000).toFixed(0)}k</p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-400">再生加速度</p>
                          <p className={`text-[11px] font-semibold ${p.velocity.view_acceleration > 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {p.velocity.view_acceleration > 0 ? "+" : ""}{(p.velocity.view_acceleration * 100).toFixed(0)}%
                          </p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-400">HIT確率</p>
                          <p className="text-[11px] font-semibold text-[#4A7DFF]">{(p.hit_probability * 100).toFixed(0)}%</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ==================== Alerts ==================== */}
        {activeTab === "alerts" && (
          <div className="p-5 space-y-4">
            <div className="card bg-gradient-to-r from-red-50 to-amber-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">市場アラート</h3>
              </div>
              <p className="text-[11px] text-gray-600">
                消化額急増・LP変更・競合新規出稿・ジャンルトレンド変動を自動検知します。
              </p>
            </div>

            <div className="space-y-2">
              <p className="text-[11px] text-gray-400">{mockAlerts.filter(a => !a.is_dismissed).length}件のアクティブアラート</p>

              {mockAlerts.filter(a => !a.is_dismissed).map((alert) => (
                <div key={alert.id} className={`card border-l-4 ${
                  alert.severity === "high" ? "border-l-red-500" :
                  alert.severity === "critical" ? "border-l-red-700" :
                  "border-l-amber-500"
                }`}>
                  <div className="flex items-start gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`badge text-[9px] ${alertTypeColors[alert.alert_type] || "bg-gray-100 text-gray-600"}`}>
                          {alertTypeLabels[alert.alert_type] || alert.alert_type}
                        </span>
                        <span className={`text-[9px] font-bold ${severityColors[alert.severity]}`}>
                          {alert.severity.toUpperCase()}
                        </span>
                        <span className="text-[9px] text-gray-400">
                          {new Date(alert.detected_at).toLocaleDateString("ja-JP")}
                        </span>
                      </div>
                      <p className="text-[12px] font-medium text-gray-900">{alert.title}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5">{alert.description}</p>

                      {alert.change_percent && (
                        <div className="mt-2">
                          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden w-32">
                            <div
                              className={`h-full rounded-full ${alert.change_percent > 100 ? "bg-red-500" : alert.change_percent > 50 ? "bg-amber-500" : "bg-blue-500"}`}
                              style={{ width: `${Math.min(alert.change_percent, 100)}%` }}
                            />
                          </div>
                          <span className="text-[9px] text-gray-400 mt-0.5">
                            変動幅: {alert.change_percent > 0 ? "+" : ""}{alert.change_percent}%
                          </span>
                        </div>
                      )}
                    </div>

                    <button className="text-gray-300 hover:text-gray-500 transition-colors shrink-0 text-[10px]">
                      非表示
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ==================== Spend Estimation ==================== */}
        {activeTab === "spend" && (
          <div className="p-5 space-y-4">
            <div className="card bg-gradient-to-r from-indigo-50 to-purple-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">予想消化額 信頼区間モデル</h3>
              </div>
              <p className="text-[11px] text-gray-600">
                媒体×ジャンル×季節性のCPM分布から予想消化額をP10~P90のレンジで算出。
                自社の実績CPMを入力すると推定精度が向上します。
              </p>
            </div>

            {/* Example estimate visualization */}
            <div className="card">
              <h4 className="text-[12px] font-bold text-gray-900 mb-3">推定結果例</h4>
              <div className="flex items-center gap-4 mb-4">
                <div className="text-center">
                  <p className="text-[9px] text-gray-400">P10 (低)</p>
                  <p className="text-[14px] font-bold text-gray-400">¥{(mockSpendEstimate.confidence_ranges.p10 / 10000).toFixed(1)}万</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] text-gray-400">P25</p>
                  <p className="text-[14px] font-bold text-blue-400">¥{(mockSpendEstimate.confidence_ranges.p25 / 10000).toFixed(1)}万</p>
                </div>
                <div className="text-center bg-blue-50 rounded-lg px-4 py-2">
                  <p className="text-[9px] text-[#4A7DFF] font-bold">P50 (中央値)</p>
                  <p className="text-[20px] font-bold text-[#4A7DFF]">¥{(mockSpendEstimate.confidence_ranges.p50 / 10000).toFixed(1)}万</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] text-gray-400">P75</p>
                  <p className="text-[14px] font-bold text-blue-400">¥{(mockSpendEstimate.confidence_ranges.p75 / 10000).toFixed(1)}万</p>
                </div>
                <div className="text-center">
                  <p className="text-[9px] text-gray-400">P90 (高)</p>
                  <p className="text-[14px] font-bold text-gray-400">¥{(mockSpendEstimate.confidence_ranges.p90 / 10000).toFixed(1)}万</p>
                </div>
              </div>

              {/* Confidence bar */}
              <div className="relative h-6 bg-gray-100 rounded-full overflow-hidden mb-2">
                <div className="absolute h-full bg-blue-100 rounded-full" style={{ left: "15%", width: "70%" }} />
                <div className="absolute h-full bg-blue-200 rounded-full" style={{ left: "25%", width: "50%" }} />
                <div className="absolute h-full w-1 bg-[#4A7DFF]" style={{ left: "50%" }} />
              </div>
              <div className="flex justify-between text-[9px] text-gray-400">
                <span>P10</span>
                <span>P25</span>
                <span className="text-[#4A7DFF] font-bold">P50</span>
                <span>P75</span>
                <span>P90</span>
              </div>

              <div className="mt-3 flex items-center gap-4 text-[10px] text-gray-500">
                <span>推定方法: {mockSpendEstimate.estimation_method === "calibrated" ? "キャリブレーション済" : "CPMモデル"}</span>
                <span>信頼度: {(mockSpendEstimate.confidence_level * 100).toFixed(0)}%</span>
                <span>季節性係数: ×{mockSpendEstimate.cpm_info.seasonal_factor}</span>
              </div>
            </div>

            {/* CPM Calibration */}
            <div className="card">
              <h4 className="text-[12px] font-bold text-gray-900 mb-3">CPMキャリブレーション</h4>
              <p className="text-[10px] text-gray-500 mb-3">
                自社の実績CPMを登録すると、推定の精度が向上します（信頼度 45%→70%）
              </p>
              <div className="grid grid-cols-4 gap-3 mb-3">
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">媒体</label>
                  <select className="select-filter text-xs w-full mt-1" value={calibPlatform} onChange={e => setCalibPlatform(e.target.value)}>
                    <option value="youtube">YouTube</option>
                    <option value="tiktok">TikTok</option>
                    <option value="instagram">Instagram</option>
                    <option value="facebook">Facebook</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">ジャンル</label>
                  <input className="input text-xs w-full mt-1" placeholder="例: 美容・コスメ" value={calibGenre} onChange={e => setCalibGenre(e.target.value)} />
                </div>
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">実績CPM (円)</label>
                  <input type="number" className="input text-xs w-full mt-1" placeholder="例: 480" value={calibCPM} onChange={e => setCalibCPM(e.target.value)} />
                </div>
                <div className="flex items-end">
                  <button className="btn-primary text-xs w-full">保存</button>
                </div>
              </div>

              {/* Existing calibrations */}
              <div className="space-y-1">
                {mockCalibrations.map(c => (
                  <div key={c.id} className="flex items-center gap-3 text-[11px] text-gray-600 p-2 bg-gray-50 rounded">
                    <span className="badge text-[9px] bg-blue-100 text-blue-700">{c.platform}</span>
                    <span>{c.genre}</span>
                    <span className="font-bold">¥{c.actual_cpm}/CPM</span>
                    <span className="text-gray-400">{c.notes}</span>
                    <span className="text-gray-400 ml-auto">{c.created_at}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ==================== Similarity Search ==================== */}
        {activeTab === "similarity" && (
          <div className="p-5 space-y-4">
            <div className="card bg-gradient-to-r from-purple-50 to-pink-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">マルチモーダル類似検索</h3>
              </div>
              <p className="text-[11px] text-gray-600">
                動画+テキスト+音声のエンベディングで「この広告に似ている」を一撃で返します。
                訴求軸・表現タイプ・構成パターンの自動タグ付きで検索結果をフィルタできます。
              </p>
            </div>

            {/* Search input */}
            <div className="card">
              <h4 className="text-[12px] font-bold text-gray-900 mb-2">意味検索（セマンティック）</h4>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  className="input text-xs flex-1"
                  placeholder="訴求ワードや表現を自然文で入力... 例: 「医師監修の美容液で肌が変わった口コミ」"
                  value={similarQuery}
                  onChange={e => setSimilarQuery(e.target.value)}
                />
                <button className="btn-primary text-xs whitespace-nowrap">
                  <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                  </svg>
                  類似検索
                </button>
              </div>
            </div>

            {/* Results */}
            <div className="space-y-2">
              <p className="text-[11px] text-gray-400">{mockSimilarAds.length}件の類似広告</p>

              {mockSimilarAds.map((ad) => (
                <div key={ad.ad_id} className="card hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex items-start gap-3">
                    {/* Similarity score */}
                    <div className="shrink-0 text-center">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-[12px] ${
                        ad.similarity >= 0.9 ? "bg-emerald-500" : ad.similarity >= 0.8 ? "bg-blue-500" : ad.similarity >= 0.7 ? "bg-indigo-500" : "bg-gray-400"
                      }`}>
                        {(ad.similarity * 100).toFixed(0)}
                      </div>
                      <span className="text-[8px] text-gray-400">類似度</span>
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium text-gray-900 truncate">{ad.title}</p>
                      <p className="text-[10px] text-gray-400">{ad.platform} · {ad.advertiser_name}</p>

                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        {/* Appeal axes */}
                        {ad.auto_appeal_axes?.map(axis => (
                          <span key={axis} className="rounded px-1.5 py-0.5 text-[8px] font-medium bg-blue-50 text-blue-600">
                            {appealAxisLabels[axis] || axis}
                          </span>
                        ))}
                        {/* Expression type */}
                        {ad.auto_expression_type && (
                          <span className="rounded px-1.5 py-0.5 text-[8px] font-medium bg-purple-50 text-purple-600">
                            {expressionTypeLabels[ad.auto_expression_type] || ad.auto_expression_type}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ==================== Destination Analytics ==================== */}
        {activeTab === "destination" && (
          <div className="p-5 space-y-4">
            <div className="card bg-gradient-to-r from-cyan-50 to-blue-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-cyan-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-1.06l4.5-4.5a4.5 4.5 0 00-6.364-6.364l-1.757 1.757" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">遷移先アナリティクス</h3>
              </div>
              <p className="text-[11px] text-gray-600">
                同一LPを使う広告アカウント数、同一LPでのクリエイティブ差と予想消化額の関係を可視化。
                勝ちLPをLP軸で発見し、ファネル構造を分析します。
              </p>
            </div>

            {/* LP Reuse ranking */}
            <div className="card">
              <h4 className="text-[12px] font-bold text-gray-900 mb-3">LP再利用ランキング（複数広告主が使用するLP）</h4>
              <div className="space-y-2">
                {mockLPReuse.map((lp, i) => (
                  <div key={lp.url_hash} className="p-3 bg-gray-50 rounded-lg hover:bg-blue-50/50 transition-colors cursor-pointer">
                    <div className="flex items-start gap-3">
                      <span className="shrink-0 w-7 h-7 rounded-full bg-[#4A7DFF] text-white text-[11px] font-bold flex items-center justify-center">
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="badge-blue text-[9px]">{lp.genre}</span>
                          <span className="text-[10px] font-bold text-red-500">{lp.advertiser_count}社が使用</span>
                          <span className="text-[10px] text-gray-400">{lp.ad_count}件の広告</span>
                        </div>
                        <p className="text-[12px] font-medium text-gray-900 truncate">{lp.title}</p>
                        <p className="text-[10px] text-gray-400 truncate">{lp.domain}</p>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {lp.advertisers.map(a => (
                            <span key={a} className="rounded bg-white px-1.5 py-0.5 text-[9px] text-gray-600 border border-gray-200">
                              {a}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ==================== Classification Management ==================== */}
        {activeTab === "classification" && (
          <div className="p-5 space-y-4">
            <div className="card bg-gradient-to-r from-amber-50 to-orange-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">2段階分類管理</h3>
              </div>
              <p className="text-[11px] text-gray-600">
                LIVE収集時は軽量モデルで暫定タグ（provisional）を付与。後追いで重いモデル+人手レビューにより確定タグ（confirmed）に昇格。
                低信頼度のタグを優先的にレビューできます。
              </p>
            </div>

            {/* Provisional tags needing review */}
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-[12px] font-bold text-gray-900">レビュー待ち（暫定分類）</h4>
                <span className="text-[10px] text-amber-600 font-medium">{mockProvisionalTags.length}件</span>
              </div>

              <div className="space-y-2">
                {mockProvisionalTags.map(tag => (
                  <div key={tag.id} className="flex items-center gap-3 p-2 bg-amber-50/50 rounded-lg border border-amber-200/50">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="badge text-[9px] bg-amber-100 text-amber-700">暫定</span>
                        <span className="text-[10px] text-gray-500">Ad #{tag.ad_id}</span>
                        <span className="text-[9px] text-gray-400">{tag.field_name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <p className="text-[12px] font-medium text-gray-900">{tag.value}</p>
                        <span className={`text-[10px] font-bold ${
                          tag.confidence >= 0.7 ? "text-emerald-600" : tag.confidence >= 0.5 ? "text-amber-600" : "text-red-500"
                        }`}>
                          信頼度 {(tag.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button className="px-2.5 py-1 rounded bg-emerald-500 text-white text-[10px] font-medium hover:bg-emerald-600 transition-colors">
                        確定
                      </button>
                      <button className="px-2.5 py-1 rounded bg-gray-200 text-gray-600 text-[10px] font-medium hover:bg-gray-300 transition-colors">
                        修正
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Classification lifecycle diagram */}
            <div className="card">
              <h4 className="text-[12px] font-bold text-gray-900 mb-3">分類ライフサイクル</h4>
              <div className="flex items-center gap-2 justify-center">
                <div className="text-center p-3 bg-blue-50 rounded-lg">
                  <p className="text-[10px] font-bold text-blue-700">LIVE収集</p>
                  <p className="text-[9px] text-blue-500">軽量モデル</p>
                </div>
                <svg className="w-6 h-6 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
                <div className="text-center p-3 bg-amber-50 rounded-lg">
                  <p className="text-[10px] font-bold text-amber-700">暫定タグ</p>
                  <p className="text-[9px] text-amber-500">Provisional</p>
                </div>
                <svg className="w-6 h-6 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
                <div className="text-center p-3 bg-purple-50 rounded-lg">
                  <p className="text-[10px] font-bold text-purple-700">重いモデル</p>
                  <p className="text-[9px] text-purple-500">後追い分析</p>
                </div>
                <svg className="w-6 h-6 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
                <div className="text-center p-3 bg-emerald-50 rounded-lg">
                  <p className="text-[10px] font-bold text-emerald-700">確定タグ</p>
                  <p className="text-[9px] text-emerald-500">Confirmed</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
