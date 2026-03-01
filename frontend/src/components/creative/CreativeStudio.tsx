"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { creativeApi } from "@/lib/api";

type CreativeMode = "script" | "copy" | "lp" | "storyboard";

export default function CreativeStudio() {
  const [mode, setMode] = useState<CreativeMode>("script");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  // Common fields
  const [productName, setProductName] = useState("");
  const [productDescription, setProductDescription] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [platform, setPlatform] = useState("youtube");
  const [appealAxis, setAppealAxis] = useState("benefit");

  // Script-specific
  const [duration, setDuration] = useState(30);
  const [structure, setStructure] = useState("problem_solution");
  const [tone, setTone] = useState("friendly");

  const handleGenerate = async () => {
    if (!productName.trim()) return;
    setLoading(true);
    setResult(null);

    try {
      const commonParams = {
        product_name: productName,
        product_description: productDescription,
        target_audience: targetAudience,
        appeal_axis: appealAxis,
      };

      let response;
      switch (mode) {
        case "script":
          response = await creativeApi.generateScript({
            ...commonParams,
            duration_seconds: duration,
            structure,
            platform,
            tone,
          });
          break;
        case "copy":
          response = await creativeApi.generateCopy({
            ...commonParams,
            platform,
            tone,
            num_variations: 5,
          });
          break;
        case "lp":
          response = await creativeApi.generateLPCopy(commonParams);
          break;
        case "storyboard":
          response = await creativeApi.generateStoryboard({
            ...commonParams,
            duration_seconds: Math.min(duration, 60),
            platform,
            style: "ugc",
          });
          break;
      }

      if (response) setResult(response.data);
    } catch (err) {
      console.error("Creative generation failed:", err);
      toast.error("生成に失敗しました。API接続とAPIキーを確認してください。");
    } finally {
      setLoading(false);
    }
  };

  const modes: { id: CreativeMode; label: string }[] = [
    { id: "script", label: "動画台本" },
    { id: "copy", label: "広告コピー" },
    { id: "lp", label: "LPコピー" },
    { id: "storyboard", label: "絵コンテ" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">クリエイティブ作成</h2>
        <p className="mt-1 text-sm text-gray-500">
          AIによる広告クリエイティブ生成
        </p>
      </div>

      {/* Mode Selector */}
      <div className="flex gap-1 rounded-lg border border-gray-200 bg-gray-100 p-1">
        {modes.map((m) => (
          <button
            key={m.id}
            onClick={() => {
              setMode(m.id);
              setResult(null);
            }}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              mode === m.id
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Input Form */}
        <div className="card space-y-4">
          <h3 className="text-lg font-semibold">入力項目</h3>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              商品名 *
            </label>
            <input
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="例: プレミアムスキンケアクリーム"
              className="input mt-1"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              商品説明
            </label>
            <textarea
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="商品の特徴やベネフィットを入力してください"
              className="input mt-1 h-24 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              ターゲット
            </label>
            <input
              type="text"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="例: スキンケアに関心のある30〜40代女性"
              className="input mt-1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                配信プラットフォーム
              </label>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="input mt-1"
              >
                <option value="youtube">YouTube</option>
                <option value="tiktok">TikTok</option>
                <option value="instagram">Instagram</option>
                <option value="facebook">Facebook</option>
                <option value="x_twitter">X (Twitter)</option>
                <option value="line">LINE</option>
                <option value="yahoo">Yahoo!</option>
                <option value="pinterest">Pinterest</option>
                <option value="smartnews">SmartNews</option>
                <option value="google_ads">Google Ads</option>
                <option value="gunosy">Gunosy</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                訴求軸
              </label>
              <select
                value={appealAxis}
                onChange={(e) => setAppealAxis(e.target.value)}
                className="input mt-1"
              >
                <option value="benefit">ベネフィット</option>
                <option value="price">価格</option>
                <option value="quality">品質</option>
                <option value="convenience">利便性</option>
                <option value="authority">権威性</option>
                <option value="social_proof">社会的証明</option>
                <option value="scarcity">希少性</option>
              </select>
            </div>
          </div>

          {(mode === "script" || mode === "storyboard") && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  尺（秒）
                </label>
                <input
                  type="number"
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  min={5}
                  max={180}
                  className="input mt-1"
                />
              </div>
              {mode === "script" && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    構成
                  </label>
                  <select
                    value={structure}
                    onChange={(e) => setStructure(e.target.value)}
                    className="input mt-1"
                  >
                    <option value="problem_solution">課題提示 → 解決提案</option>
                    <option value="ugc_testimonial">UGC体験談</option>
                    <option value="product_demo">商品デモ</option>
                    <option value="listicle">ランキング形式（Top N）</option>
                    <option value="short_impact">短尺インパクト（15秒）</option>
                  </select>
                </div>
              )}
            </div>
          )}

          <button
            onClick={handleGenerate}
            disabled={loading || !productName.trim()}
            className="btn-primary w-full"
          >
            {loading ? "生成中..." : "生成する"}
          </button>
        </div>

        {/* Result Display */}
        <div className="card">
          <h3 className="text-lg font-semibold">生成結果</h3>
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
            </div>
          ) : result ? (
            <div className="mt-4 max-h-[600px] overflow-y-auto">
              <pre className="whitespace-pre-wrap rounded-lg bg-gray-50 p-4 text-sm text-gray-700">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center text-gray-400">
              <p>入力後に「生成する」を押してください</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
