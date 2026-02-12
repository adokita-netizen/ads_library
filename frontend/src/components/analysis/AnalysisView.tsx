"use client";

import { useEffect, useState } from "react";
import { adsApi, predictionsApi } from "@/lib/api";
import type { Ad, AdAnalysis, PredictionResult } from "@/types";

interface AnalysisViewProps {
  adId: number | null;
}

export default function AnalysisView({ adId }: AnalysisViewProps) {
  const [ad, setAd] = useState<Ad | null>(null);
  const [analysis, setAnalysis] = useState<AdAnalysis | null>(null);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    if (adId) loadData(adId);
  }, [adId]);

  const loadData = async (id: number) => {
    setLoading(true);
    try {
      const [adRes, analysisRes] = await Promise.all([
        adsApi.get(id),
        adsApi.getAnalysis(id).catch(() => null),
      ]);
      setAd(adRes.data);
      if (analysisRes) setAnalysis(analysisRes.data);
    } catch {
      // Handle error
    } finally {
      setLoading(false);
    }
  };

  const loadPrediction = async () => {
    if (!adId) return;
    try {
      const res = await predictionsApi.predict({ ad_id: adId });
      setPrediction(res.data);
    } catch {
      // Handle error
    }
  };

  if (!adId) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-gray-500">Select an ad from the library to view analysis</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "visual", label: "Visual Analysis" },
    { id: "audio", label: "Audio & Text" },
    { id: "prediction", label: "Prediction" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            {ad?.title || "Ad Analysis"}
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            {ad?.advertiser_name} | {ad?.platform} |{" "}
            {ad?.duration_seconds ? `${Math.round(ad.duration_seconds)}s` : "Unknown duration"}
          </p>
        </div>
        {ad?.status !== "analyzed" && (
          <button
            onClick={async () => {
              if (adId) {
                await adsApi.analyze(adId);
                setTimeout(() => loadData(adId), 2000);
              }
            }}
            className="btn-primary"
          >
            Run Analysis
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-gray-200 bg-gray-100 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              if (tab.id === "prediction" && !prediction) loadPrediction();
            }}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {!analysis ? (
        <div className="card text-center">
          <p className="text-gray-500">
            Analysis not yet available. Click &quot;Run Analysis&quot; to start.
          </p>
        </div>
      ) : (
        <>
          {activeTab === "overview" && <OverviewTab analysis={analysis} />}
          {activeTab === "visual" && <VisualTab analysis={analysis} />}
          {activeTab === "audio" && <AudioTab analysis={analysis} />}
          {activeTab === "prediction" && (
            <PredictionTab prediction={prediction} loading={!prediction} />
          )}
        </>
      )}
    </div>
  );
}

function OverviewTab({ analysis }: { analysis: AdAnalysis }) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Winning Score */}
      <div className="card">
        <h3 className="text-lg font-semibold">Winning Score</h3>
        <div className="mt-4 flex items-center gap-4">
          <div className="relative h-32 w-32">
            <svg className="h-32 w-32 -rotate-90" viewBox="0 0 36 36">
              <path
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none"
                stroke="#e5e7eb"
                strokeWidth="3"
              />
              <path
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="3"
                strokeDasharray={`${analysis.winning_score || 0}, 100`}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-2xl font-bold">
              {analysis.winning_score?.toFixed(0) || "N/A"}
            </span>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-gray-500">Sentiment: {analysis.overall_sentiment || "N/A"}</p>
            <p className="text-sm text-gray-500">Hook: {analysis.hook_type || "N/A"}</p>
            <p className="text-sm text-gray-500">Scenes: {analysis.total_scenes || "N/A"}</p>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="card">
        <h3 className="text-lg font-semibold">Key Metrics</h3>
        <div className="mt-4 space-y-3">
          <MetricBar label="Face Close-up" value={analysis.face_closeup_ratio} />
          <MetricBar label="Product Display" value={analysis.product_display_ratio} />
          <MetricBar label="Text Overlay" value={analysis.text_overlay_ratio} />
        </div>
      </div>

      {/* Content Features */}
      <div className="card">
        <h3 className="text-lg font-semibold">Content Features</h3>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <FeatureBadge label="UGC Style" value={analysis.is_ugc_style} />
          <FeatureBadge label="Narration" value={analysis.has_narration} />
          <FeatureBadge label="Subtitles" value={analysis.has_subtitles} />
          <FeatureBadge label="CTA" value={!!analysis.cta_text} />
        </div>
      </div>

      {/* Color Palette */}
      <div className="card">
        <h3 className="text-lg font-semibold">Color Palette</h3>
        <div className="mt-4 flex gap-2">
          {(analysis.dominant_color_palette || []).map((color, i) => (
            <div key={i} className="text-center">
              <div
                className="h-12 w-12 rounded-lg border border-gray-200"
                style={{ backgroundColor: color }}
              />
              <span className="mt-1 block text-xs text-gray-500">{color}</span>
            </div>
          ))}
          {!analysis.dominant_color_palette?.length && (
            <p className="text-sm text-gray-400">No color data</p>
          )}
        </div>
      </div>
    </div>
  );
}

function VisualTab({ analysis }: { analysis: AdAnalysis }) {
  return (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-lg font-semibold">Scene Analysis</h3>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Total Scenes" value={analysis.total_scenes} />
          <StatCard
            label="Avg Duration"
            value={analysis.avg_scene_duration?.toFixed(1)}
            suffix="s"
          />
          <StatCard
            label="Face Ratio"
            value={((analysis.face_closeup_ratio || 0) * 100).toFixed(0)}
            suffix="%"
          />
          <StatCard
            label="Product Ratio"
            value={((analysis.product_display_ratio || 0) * 100).toFixed(0)}
            suffix="%"
          />
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold">Hook Analysis (First 3s)</h3>
        <div className="mt-4">
          <p className="text-sm text-gray-700">
            <strong>Type:</strong> {analysis.hook_type || "N/A"}
          </p>
          {analysis.hook_text && (
            <p className="mt-2 text-sm text-gray-700">
              <strong>Text:</strong> {analysis.hook_text}
            </p>
          )}
          {analysis.hook_score !== undefined && analysis.hook_score !== null && (
            <p className="mt-2 text-sm text-gray-700">
              <strong>Score:</strong> {analysis.hook_score.toFixed(1)}/100
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function AudioTab({ analysis }: { analysis: AdAnalysis }) {
  return (
    <div className="space-y-6">
      {/* Transcript */}
      <div className="card">
        <h3 className="text-lg font-semibold">Transcript</h3>
        <div className="mt-4 max-h-64 overflow-y-auto rounded-lg bg-gray-50 p-4">
          <p className="whitespace-pre-wrap text-sm text-gray-700">
            {analysis.full_transcript || "No transcript available"}
          </p>
        </div>
      </div>

      {/* Sentiment */}
      <div className="card">
        <h3 className="text-lg font-semibold">Sentiment Analysis</h3>
        <div className="mt-4 flex items-center gap-4">
          <span
            className={`badge text-base ${
              analysis.overall_sentiment === "positive"
                ? "badge-green"
                : analysis.overall_sentiment === "negative"
                  ? "badge-red"
                  : "badge-yellow"
            }`}
          >
            {analysis.overall_sentiment || "N/A"}
          </span>
          {analysis.sentiment_score !== undefined && (
            <span className="text-sm text-gray-500">
              Score: {analysis.sentiment_score.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {/* Keywords */}
      <div className="card">
        <h3 className="text-lg font-semibold">Keywords</h3>
        <div className="mt-4 flex flex-wrap gap-2">
          {(analysis.keywords || []).slice(0, 20).map((kw, i) => (
            <span key={i} className="badge-blue">
              {typeof kw === "string" ? kw : kw.keyword}
            </span>
          ))}
          {!analysis.keywords?.length && (
            <p className="text-sm text-gray-400">No keywords extracted</p>
          )}
        </div>
      </div>

      {/* CTA */}
      {analysis.cta_text && (
        <div className="card">
          <h3 className="text-lg font-semibold">CTA Detection</h3>
          <p className="mt-2 text-sm text-gray-700">{analysis.cta_text}</p>
        </div>
      )}
    </div>
  );
}

function PredictionTab({
  prediction,
  loading,
}: {
  prediction: PredictionResult | null;
  loading: boolean;
}) {
  if (loading || !prediction) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Predictions */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="card text-center">
          <p className="text-sm text-gray-500">Predicted CTR</p>
          <p className="mt-1 text-3xl font-bold text-primary-600">
            {(prediction.predicted_ctr * 100).toFixed(2)}%
          </p>
          <p className="text-xs text-gray-400">
            {(prediction.ctr_confidence.low * 100).toFixed(2)}% -{" "}
            {(prediction.ctr_confidence.high * 100).toFixed(2)}%
          </p>
        </div>
        <div className="card text-center">
          <p className="text-sm text-gray-500">Predicted CVR</p>
          <p className="mt-1 text-3xl font-bold text-green-600">
            {(prediction.predicted_cvr * 100).toFixed(2)}%
          </p>
        </div>
        <div className="card text-center">
          <p className="text-sm text-gray-500">Winning Probability</p>
          <p className="mt-1 text-3xl font-bold text-amber-600">
            {prediction.winning_probability.toFixed(0)}%
          </p>
        </div>
      </div>

      {/* Feature Importance */}
      <div className="card">
        <h3 className="text-lg font-semibold">Feature Importance</h3>
        <div className="mt-4 space-y-2">
          {prediction.feature_importance.map((f, i) => (
            <div key={i} className="flex items-center gap-3">
              <span className="w-40 text-sm text-gray-600">{f.feature}</span>
              <div className="flex-1">
                <div
                  className="h-3 rounded-full bg-primary-500"
                  style={{ width: `${f.importance * 100}%` }}
                />
              </div>
              <span className="w-20 text-right text-xs text-gray-500">
                {f.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Suggestions */}
      <div className="card">
        <h3 className="text-lg font-semibold">Improvement Suggestions</h3>
        <div className="mt-4 space-y-3">
          {prediction.improvement_suggestions.map((s, i) => (
            <div key={i} className="rounded-lg border border-gray-200 p-3">
              <div className="flex items-center gap-2">
                <span
                  className={`badge ${
                    s.priority === "high"
                      ? "badge-red"
                      : s.priority === "medium"
                        ? "badge-yellow"
                        : "badge-green"
                  }`}
                >
                  {s.priority}
                </span>
                <span className="text-xs text-gray-500">{s.category}</span>
              </div>
              <p className="mt-1 text-sm text-gray-700">{s.suggestion}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MetricBar({ label, value }: { label: string; value?: number | null }) {
  const percentage = ((value || 0) * 100).toFixed(0);
  return (
    <div>
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{percentage}%</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-gray-200">
        <div
          className="h-2 rounded-full bg-primary-500"
          style={{ width: `${Math.min(Number(percentage), 100)}%` }}
        />
      </div>
    </div>
  );
}

function FeatureBadge({ label, value }: { label: string; value?: boolean | null }) {
  return (
    <div
      className={`rounded-lg border p-2 text-center text-sm ${
        value ? "border-green-200 bg-green-50 text-green-800" : "border-gray-200 text-gray-500"
      }`}
    >
      {label}: {value ? "Yes" : "No"}
    </div>
  );
}

function StatCard({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value?: number | string | null;
  suffix?: string;
}) {
  return (
    <div className="rounded-lg bg-gray-50 p-3 text-center">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-bold">
        {value ?? "N/A"}
        {value !== null && value !== undefined && suffix}
      </p>
    </div>
  );
}
