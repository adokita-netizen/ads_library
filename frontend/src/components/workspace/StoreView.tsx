"use client";

const mockTemplates = [
  { id: 1, name: "問題解決型LP構成テンプレート", category: "LP設計", price: "無料", downloads: 245, rating: 4.8, description: "悩み共感→原因→解決策→証拠→CTAの王道構成" },
  { id: 2, name: "UGC風動画台本テンプレート", category: "動画台本", price: "無料", downloads: 189, rating: 4.6, description: "一般ユーザー風のリアルな体験談形式" },
  { id: 3, name: "権威性訴求バナーテンプレート", category: "バナー", price: "無料", downloads: 156, rating: 4.5, description: "医師監修・特許取得などの権威性を前面に" },
  { id: 4, name: "美容ジャンル分析レポート 2025年12月", category: "レポート", price: "Pro", downloads: 78, rating: 4.9, description: "美容コスメジャンルの最新トレンド・競合分析" },
  { id: 5, name: "15秒ショート動画構成集", category: "動画台本", price: "無料", downloads: 312, rating: 4.7, description: "YouTube Shorts / TikTok向け短尺動画テンプレート" },
  { id: 6, name: "A/Bテスト設計テンプレート", category: "テスト", price: "無料", downloads: 98, rating: 4.4, description: "クリエイティブA/Bテストの設計・記録シート" },
];

const categoryColors: Record<string, string> = {
  "LP設計": "bg-purple-100 text-purple-700",
  "動画台本": "bg-blue-100 text-blue-700",
  "バナー": "bg-emerald-100 text-emerald-700",
  "レポート": "bg-amber-100 text-amber-700",
  "テスト": "bg-cyan-100 text-cyan-700",
};

export default function StoreView() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">VAAPストア</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">テンプレート・レポート・ツールのマーケットプレイス</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="テンプレートを検索..."
            className="input text-xs w-52"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-5">
        <div className="grid grid-cols-2 gap-4">
          {mockTemplates.map((t) => (
            <div key={t.id} className="card hover:shadow-md transition-shadow cursor-pointer">
              <div className="flex items-center gap-2 mb-2">
                <span className={`badge text-[9px] ${categoryColors[t.category] || "bg-gray-100 text-gray-600"}`}>
                  {t.category}
                </span>
                <span className={`text-[9px] font-bold ${t.price === "無料" ? "text-emerald-600" : "text-[#4A7DFF]"}`}>
                  {t.price}
                </span>
              </div>
              <h3 className="text-[13px] font-bold text-gray-900 mb-1">{t.name}</h3>
              <p className="text-[11px] text-gray-500 mb-3">{t.description}</p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-[10px] text-gray-400">
                  <span>⬇ {t.downloads}</span>
                  <span>★ {t.rating}</span>
                </div>
                <button className="px-3 py-1 rounded bg-[#4A7DFF] text-white text-[10px] font-medium hover:bg-[#3a6ae8] transition-colors">
                  使用する
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
