"use client";

import { useState } from "react";
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
      alert("生成に失敗しました。API接続とAPIキーを確認してください。");
    } finally {
      setLoading(false);
    }
  };

  const modes: { id: CreativeMode; label: string }[] = [
    { id: "script", label: "Video Script" },
    { id: "copy", label: "Ad Copy" },
    { id: "lp", label: "LP Copy" },
    { id: "storyboard", label: "Storyboard" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Creative Studio</h2>
        <p className="mt-1 text-sm text-gray-500">
          AI-powered ad creative generation
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
          <h3 className="text-lg font-semibold">Input Parameters</h3>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Product Name *
            </label>
            <input
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="e.g., Premium Skincare Cream"
              className="input mt-1"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Product Description
            </label>
            <textarea
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="Describe your product, key features, benefits..."
              className="input mt-1 h-24 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Target Audience
            </label>
            <input
              type="text"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="e.g., 30-40 women interested in skincare"
              className="input mt-1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Platform
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
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Appeal Axis
              </label>
              <select
                value={appealAxis}
                onChange={(e) => setAppealAxis(e.target.value)}
                className="input mt-1"
              >
                <option value="benefit">Benefit</option>
                <option value="price">Price</option>
                <option value="quality">Quality</option>
                <option value="convenience">Convenience</option>
                <option value="authority">Authority</option>
                <option value="social_proof">Social Proof</option>
                <option value="scarcity">Scarcity</option>
              </select>
            </div>
          </div>

          {(mode === "script" || mode === "storyboard") && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Duration (seconds)
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
                    Structure
                  </label>
                  <select
                    value={structure}
                    onChange={(e) => setStructure(e.target.value)}
                    className="input mt-1"
                  >
                    <option value="problem_solution">Problem &rarr; Solution</option>
                    <option value="ugc_testimonial">UGC Testimonial</option>
                    <option value="product_demo">Product Demo</option>
                    <option value="listicle">Listicle (Top N)</option>
                    <option value="short_impact">Short Impact (15s)</option>
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
            {loading ? "Generating..." : "Generate"}
          </button>
        </div>

        {/* Result Display */}
        <div className="card">
          <h3 className="text-lg font-semibold">Generated Result</h3>
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
              <p>Fill in the parameters and click Generate</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
