"use client";

import React, { useState, useCallback, useEffect } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";
import { copyToClipboard } from "@/lib/format";

// ─── Types ───

interface Archetype {
  id: string;
  name: string;
  icon: string;
  hit_rate: number;
  description: string;
  example_count: number;
}

interface ScenarioSection {
  time_range: string;
  label: string;
  text: string;
  color: string;
}

interface GeneratedScenario {
  title_options: string[];
  sections: ScenarioSection[];
  power_words: string[];
  predicted_score: number;
}

interface ScenarioVariation {
  id: string;
  title: string;
  sections: ScenarioSection[];
  predicted_score: number;
}

interface PerformancePrediction {
  predicted_score: number;
  hit_probability: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
}

interface SavedScenarioRecord {
  id: string;
  name: string;
  genre: string;
  archetype: string;
  saved_at?: string;
  updated_at?: string;
  platform?: string;
  product_name?: string;
  scenario?: unknown;
}

interface GenerateScenarioApiResponse {
  scenario?: {
    title_options?: string[];
    sections?: Array<{
      section?: string;
      type?: string;
      text?: string;
      duration?: string;
      label?: string;
      color?: string;
    }>;
    power_words_used?: string[];
    power_words?: string[];
    predicted_score?: number;
  };
}

interface ScenarioVariationsApiResponse {
  variations?: Array<{
    variation_id?: number;
    title?: string;
    hook_text?: string;
    cta_text?: string;
    structure?: string[];
    predicted_score?: number;
  }>;
  items?: ScenarioVariation[];
}

// ─── Fallback Data (used when API is unavailable) ───

const FALLBACK_ARCHETYPES: Archetype[] = [
  { id: "before_after", name: "Before/After変身型", icon: "🔄", hit_rate: 72, description: "使用前後の変化を劇的に見せるパターン", example_count: 156 },
  { id: "problem_solution", name: "問題解決型", icon: "💡", hit_rate: 65, description: "悩みを提示し解決策を提案するパターン", example_count: 203 },
  { id: "testimonial", name: "体験談・口コミ型", icon: "💬", hit_rate: 58, description: "実際のユーザー体験を中心に展開するパターン", example_count: 89 },
  { id: "urgency", name: "緊急性・限定型", icon: "⏰", hit_rate: 61, description: "期間限定や数量限定で行動を促すパターン", example_count: 134 },
  { id: "authority", name: "権威・専門家型", icon: "🏅", hit_rate: 55, description: "専門家の推薦や権威あるデータで信頼性を高めるパターン", example_count: 67 },
  { id: "storytelling", name: "ストーリーテリング型", icon: "📖", hit_rate: 68, description: "物語形式で感情に訴えかけるパターン", example_count: 112 },
  { id: "comparison", name: "比較型", icon: "⚖️", hit_rate: 52, description: "他製品との比較で優位性を示すパターン", example_count: 78 },
  { id: "educational", name: "教育・啓蒙型", icon: "🎓", hit_rate: 48, description: "知識提供を通じて製品価値を伝えるパターン", example_count: 45 },
];

// ─── Hook options ───
const hookTypes = [
  { value: "question", label: "質問型", example: "「まだ○○で悩んでいませんか？」" },
  { value: "shock", label: "衝撃型", example: "「知らなかったでは済まされない事実」" },
  { value: "benefit", label: "ベネフィット型", example: "「たった○日で実感できる変化」" },
  { value: "story", label: "ストーリー型", example: "「私がこの方法に出会うまで...」" },
];

const ctaTypes = [
  { value: "limited", label: "限定オファー", example: "「今だけ80%OFF」" },
  { value: "free_trial", label: "無料お試し", example: "「まずは無料でお試し」" },
  { value: "guarantee", label: "保証付き", example: "「30日間全額返金保証」" },
  { value: "urgency", label: "緊急性", example: "「残りわずか！お急ぎください」" },
];

const platformOptions = [
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
];

const durationOptions = [
  { value: 15, label: "15秒" },
  { value: 30, label: "30秒" },
  { value: 60, label: "60秒" },
];

const toneOptions = [
  { value: "formal", label: "フォーマル" },
  { value: "casual", label: "カジュアル" },
  { value: "urgent", label: "緊急感" },
];

const SECTION_COLORS = [
  "bg-blue-500",
  "bg-violet-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
];

function humanizeSectionLabel(label?: string): string {
  const normalized = String(label || "").trim();
  if (!normalized) return "セクション";
  const map: Record<string, string> = {
    hook: "HOOK",
    problem: "課題提起",
    solution: "解決策",
    proof: "証拠",
    cta: "CTA",
  };
  return map[normalized] || normalized.toUpperCase();
}

function normalizeGeneratedScenario(payload: GenerateScenarioApiResponse | GeneratedScenario): GeneratedScenario {
  const scenario = (("scenario" in payload && payload.scenario ? payload.scenario : payload) || {}) as {
    title_options?: string[];
    sections?: Array<{
      section?: string;
      type?: string;
      text?: string;
      duration?: string;
      time_range?: string;
      label?: string;
      color?: string;
    }>;
    power_words_used?: string[];
    power_words?: string[];
    predicted_score?: number;
  };
  const rawSections = Array.isArray(scenario.sections) ? scenario.sections : [];
  return {
    title_options: Array.isArray(scenario.title_options) ? scenario.title_options : [],
    sections: rawSections.map((section, index: number) => ({
      time_range: String(section.duration || section.time_range || ""),
      label: humanizeSectionLabel(section.label || section.section || section.type),
      text: String(section.text || ""),
      color: section.color || SECTION_COLORS[index % SECTION_COLORS.length],
    })),
    power_words: Array.isArray(scenario.power_words)
      ? scenario.power_words
      : Array.isArray(scenario.power_words_used)
      ? scenario.power_words_used
      : [],
    predicted_score: Number(scenario.predicted_score || 0),
  };
}

function normalizeScenarioVariations(payload: ScenarioVariationsApiResponse): ScenarioVariation[] {
  const items = (Array.isArray(payload.variations)
    ? payload.variations
    : Array.isArray(payload.items)
    ? payload.items
    : []) as Array<
      ScenarioVariation | {
        variation_id?: number;
        title?: string;
        hook_text?: string;
        cta_text?: string;
        structure?: string[];
        predicted_score?: number;
      }
    >;

  return items.map((item, index) => {
    if ("sections" in item && Array.isArray(item.sections)) {
      return item as ScenarioVariation;
    }
    const rawItem = item as {
      variation_id?: number;
      title?: string;
      hook_text?: string;
      cta_text?: string;
      structure?: string[];
      predicted_score?: number;
    };
    return {
      id: String(rawItem.variation_id || index + 1),
      title: String(rawItem.title || `Variation ${index + 1}`),
      predicted_score: Number(rawItem.predicted_score || 0),
      sections: [
        {
          time_range: "0:00-0:03",
          label: "HOOK",
          text: String(rawItem.hook_text || ""),
          color: SECTION_COLORS[0],
        },
        {
          time_range: "0:03-0:06",
          label: "CTA",
          text: String(rawItem.cta_text || ""),
          color: SECTION_COLORS[3],
        },
        ...((Array.isArray(rawItem.structure) ? rawItem.structure : []).map((part: string, partIndex: number) => ({
          time_range: "",
          label: humanizeSectionLabel(part),
          text: "",
          color: SECTION_COLORS[(partIndex + 1) % SECTION_COLORS.length],
        }))),
      ],
    };
  });
}

function normalizeSavedScenario(payload: SavedScenarioRecord): GeneratedScenario | null {
  if (!payload.scenario || typeof payload.scenario !== "object") return null;
  return normalizeGeneratedScenario(payload.scenario as GenerateScenarioApiResponse | GeneratedScenario);
}

// ─── Main Component ───

interface ScenarioBuilderProps {
  loadScenarioId?: string | null;
  onScenarioLoaded?: () => void;
}

export default function ScenarioBuilder({ loadScenarioId, onScenarioLoaded }: ScenarioBuilderProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 6;

  // Step 1 state
  const [genre, setGenre] = useState("all");
  const [productName, setProductName] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [keyBenefit, setKeyBenefit] = useState("");

  // Step 2 state
  const [selectedArchetype, setSelectedArchetype] = useState<string | null>(null);

  // Step 3 state
  const [hookType, setHookType] = useState("question");
  const [ctaType, setCtaType] = useState("limited");
  const [platform, setPlatform] = useState("instagram");
  const [duration, setDuration] = useState(30);
  const [tone, setTone] = useState("casual");

  // Step 4 state
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState<GeneratedScenario | null>(null);
  const [selectedTitle, setSelectedTitle] = useState(0);
  const [editingSection, setEditingSection] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  // Step 5 state
  const [generatingVariations, setGeneratingVariations] = useState(false);
  const [variations, setVariations] = useState<ScenarioVariation[]>([]);
  const [selectedVariation, setSelectedVariation] = useState<string | null>(null);

  // Step 6 state
  const [saving, setSaving] = useState(false);
  const [scenarioName, setScenarioName] = useState("");
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saved, setSaved] = useState(false);

  // Performance Prediction
  const [showPerformanceChecker, setShowPerformanceChecker] = useState(false);
  const [customText, setCustomText] = useState("");
  const [predicting, setPredicting] = useState(false);
  const [prediction, setPrediction] = useState<PerformancePrediction | null>(null);

  const steps = [
    { num: 1, label: "ジャンル・商品" },
    { num: 2, label: "アーキタイプ" },
    { num: 3, label: "カスタマイズ" },
    { num: 4, label: "生成・プレビュー" },
    { num: 5, label: "バリエーション" },
    { num: 6, label: "保存・エクスポート" },
  ];

  // ─── Archetypes from API ───
  const [archetypes, setArchetypes] = useState<Archetype[]>(FALLBACK_ARCHETYPES);

  useEffect(() => {
    fetchApi<{ archetypes?: Archetype[]; items?: Archetype[] }>("/rankings/scenario-archetypes")
      .then((res) => {
        const items = res.archetypes || res.items || (Array.isArray(res) ? (res as Archetype[]) : []);
        if (items.length > 0) setArchetypes(items);
      })
      .catch(() => { /* keep fallback */ });
  }, []);

  useEffect(() => {
    if (!loadScenarioId) return;

    let cancelled = false;
    fetchApi<{ items?: SavedScenarioRecord[]; saved_scenarios?: SavedScenarioRecord[] }>("/rankings/saved-scenarios")
      .then((res) => {
        if (cancelled) return;
        const items = res.items || res.saved_scenarios || [];
        const found = items.find((item) => String(item.id) === String(loadScenarioId));
        if (!found) {
          toast.error("保存済みシナリオが見つかりません");
          onScenarioLoaded?.();
          return;
        }

        const normalized = normalizeSavedScenario(found);
        if (!normalized) {
          toast.error("保存済みシナリオの形式が不正です");
          onScenarioLoaded?.();
          return;
        }

        setGenre(found.genre || "all");
        setScenarioName(found.name || "");
        setSelectedArchetype(found.archetype || null);
        setGenerated(normalized);
        setCurrentStep(4);
        setSaved(false);
        setSelectedTitle(0);
        toast.success("保存済みシナリオを読み込みました");
        onScenarioLoaded?.();
      })
      .catch(() => {
        if (!cancelled) {
          toast.error("保存済みシナリオの読み込みに失敗しました");
          onScenarioLoaded?.();
        }
      });

    return () => {
      cancelled = true;
    };
  }, [loadScenarioId, onScenarioLoaded]);

  // ─── API Calls ───

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    try {
      const result = await fetchApi<GenerateScenarioApiResponse>("/rankings/generate-scenario", {
        method: "POST",
        body: {
          genre_en: genre,
          product_name: productName,
          target_audience: targetAudience,
          key_benefit: keyBenefit,
          archetype: selectedArchetype,
          cta_type: ctaType,
          platform,
          duration_seconds: duration,
        },
      });
      setGenerated(normalizeGeneratedScenario(result));
      setSaved(false);
    } catch {
      toast.error("シナリオ生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  }, [genre, productName, targetAudience, keyBenefit, selectedArchetype, ctaType, platform, duration]);

  const handleGenerateVariations = useCallback(async () => {
    setGeneratingVariations(true);
    try {
      const result = await fetchApi<ScenarioVariationsApiResponse>("/rankings/scenario-variations", {
        method: "POST",
        body: {
          genre_en: genre,
          product_name: productName,
          key_benefit: keyBenefit,
          target_audience: targetAudience,
          variation_count: 4,
          base_archetype: selectedArchetype,
        },
      });
      setVariations(normalizeScenarioVariations(result));
    } catch {
      toast.error("バリエーション生成に失敗しました");
    } finally {
      setGeneratingVariations(false);
    }
  }, [genre, productName, keyBenefit, targetAudience, selectedArchetype]);

  const handleSave = useCallback(async () => {
    if (!scenarioName.trim()) return;
    setSaving(true);
    try {
      const response = await fetchApi<{ scenario?: SavedScenarioRecord; id?: string }>("/rankings/saved-scenarios", {
        method: "POST",
        body: {
          name: scenarioName,
          genre,
          archetype: selectedArchetype,
          platform,
          product_name: productName,
          scenario: generated,
          selected_variation: selectedVariation,
          variations,
        },
      });
      if (typeof window !== "undefined") {
        const scenario = response.scenario;
        window.dispatchEvent(
          new CustomEvent("saved-scenarios:changed", {
            detail: {
              action: "saved",
              scenario: scenario
                ? {
                    ...scenario,
                    platform: scenario.platform || platform,
                    product_name: scenario.product_name || productName,
                  }
                : undefined,
              scenarioId: response.id,
            },
          }),
        );
      }
      setSaved(true);
      setShowSaveModal(false);
      toast.success("シナリオを保存しました");
    } catch {
      toast.error("保存に失敗しました");
    } finally {
      setSaving(false);
    }
  }, [scenarioName, genre, selectedArchetype, platform, productName, generated, selectedVariation, variations]);

  const handlePredictPerformance = useCallback(async () => {
    if (!customText.trim()) return;
    setPredicting(true);
    try {
      const result = await fetchApi<PerformancePrediction>("/rankings/predict-scenario-performance", {
        method: "POST",
        params: {
          hook_type: hookType,
          cta_type: ctaType,
          genre,
          title: generated?.title_options?.[selectedTitle] || productName,
          description: customText,
        },
      });
      setPrediction(result);
    } catch {
      toast.error("パフォーマンス予測に失敗しました");
    } finally {
      setPredicting(false);
    }
  }, [customText, hookType, ctaType, genre, generated, selectedTitle, productName]);

  const handleExportText = () => {
    if (!generated) return;
    const text = generated.sections.map((s) => `[${s.time_range}] ${s.label}\n${s.text}`).join("\n\n");
    const title = generated.title_options[selectedTitle] || "";
    const full = `タイトル: ${title}\n\n${text}`;
    copyToClipboard(full);
  };

  const handleDownloadText = () => {
    if (!generated) return;
    const text = generated.sections.map((s) => `[${s.time_range}] ${s.label}\n${s.text}`).join("\n\n");
    const title = generated.title_options[selectedTitle] || "";
    const full = `タイトル: ${title}\n\n${text}`;
    const blob = new Blob([full], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scenario_${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSectionEdit = (idx: number) => {
    if (generated) {
      setEditingSection(idx);
      setEditText(generated.sections[idx].text);
    }
  };

  const handleSectionSave = (idx: number) => {
    if (generated) {
      const newSections = [...generated.sections];
      newSections[idx] = { ...newSections[idx], text: editText };
      setGenerated({ ...generated, sections: newSections });
      setEditingSection(null);
    }
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1: return genre !== "all" && productName.trim().length > 0;
      case 2: return selectedArchetype !== null;
      case 3: return true;
      case 4: return generated !== null;
      case 5: return true;
      default: return true;
    }
  };

  // ─── Score gauge helper ───
  const ScoreGauge = ({ score, size = "large" }: { score: number; size?: "large" | "small" }) => {
    const color = score >= 80 ? "text-green-500" : score >= 60 ? "text-yellow-500" : score >= 40 ? "text-orange-500" : "text-red-500";
    const bgColor = score >= 80 ? "bg-green-100" : score >= 60 ? "bg-yellow-100" : score >= 40 ? "bg-orange-100" : "bg-red-100";
    const sz = size === "large" ? "w-24 h-24" : "w-16 h-16";
    const txtSz = size === "large" ? "text-2xl" : "text-lg";
    return (
      <div className={`${sz} ${bgColor} rounded-full flex items-center justify-center`}>
        <span className={`${txtSz} font-bold ${color}`}>{score}</span>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#f8f9fb]">
      {/* Header */}
      <div className="shrink-0 bg-white border-b border-gray-200">
        <div className="px-5 py-3">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
              </svg>
              <h1 className="text-[16px] font-bold text-gray-900">シナリオ作成</h1>
              <span className="text-[11px] text-gray-400">圧倒的に削減。誰でも簡単に広告のシナリオが作成できる！</span>
            </div>
            <button
              onClick={() => setShowPerformanceChecker(!showPerformanceChecker)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75z" />
              </svg>
              パフォーマンス予測
            </button>
          </div>

          {/* Step Indicator */}
          <div className="flex items-center gap-1">
            {steps.map((step, idx) => (
              <React.Fragment key={step.num}>
                <button
                  onClick={() => {
                    if (step.num <= currentStep) setCurrentStep(step.num);
                  }}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                    currentStep === step.num
                      ? "bg-[#4A7DFF] text-white"
                      : step.num < currentStep
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {step.num < currentStep ? (
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <span className="w-4 h-4 rounded-full border border-current flex items-center justify-center text-[9px]">{step.num}</span>
                  )}
                  {step.label}
                </button>
                {idx < steps.length - 1 && (
                  <svg className="w-3 h-3 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4">
        {/* ─── Step 1: Genre & Product ─── */}
        {currentStep === 1 && (
          <div className="max-w-2xl mx-auto space-y-5">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-[15px] font-bold text-gray-900 mb-4">Step 1: ジャンル・商品情報</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">ジャンル</label>
                  <select
                    value={genre}
                    onChange={(e) => setGenre(e.target.value)}
                    className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF]"
                  >
                    {genreOptions.map((g) => (
                      <option key={g.value} value={g.value}>{g.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">商品名 <span className="text-red-400">*</span></label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    placeholder="例: ○○美容液"
                    className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF]"
                  />
                </div>
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">ターゲット</label>
                  <input
                    type="text"
                    value={targetAudience}
                    onChange={(e) => setTargetAudience(e.target.value)}
                    placeholder="例: 30代女性"
                    className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF]"
                  />
                </div>
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">キーベネフィット</label>
                  <input
                    type="text"
                    value={keyBenefit}
                    onChange={(e) => setKeyBenefit(e.target.value)}
                    placeholder="例: 1ヶ月で-5kg"
                    className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF]"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ─── Step 2: Archetype Selection ─── */}
        {currentStep === 2 && (
          <div className="max-w-4xl mx-auto space-y-5">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-[15px] font-bold text-gray-900 mb-1">Step 2: アーキタイプ選択</h2>
              <p className="text-[11px] text-gray-500 mb-4">広告シナリオの型を選んでください</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {archetypes.map((arch) => (
                  <button
                    key={arch.id}
                    onClick={() => setSelectedArchetype(arch.id)}
                    className={`relative p-4 rounded-xl border-2 text-left transition-all ${
                      selectedArchetype === arch.id
                        ? "border-[#4A7DFF] bg-[#EEF2FF] shadow-md"
                        : "border-gray-200 hover:border-gray-300 hover:shadow-sm"
                    }`}
                  >
                    <div className="text-2xl mb-2">{arch.icon}</div>
                    <div className="text-[13px] font-bold text-gray-900 mb-1">{arch.name}</div>
                    <div className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold mb-2 ${
                      arch.hit_rate >= 60 ? "bg-green-100 text-green-700" : arch.hit_rate >= 40 ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-600"
                    }`}>
                      ヒット率 {arch.hit_rate}%
                    </div>
                    <p className="text-[11px] text-gray-500 leading-relaxed">{arch.description}</p>
                    <p className="text-[10px] text-gray-400 mt-2">{arch.example_count}件の事例</p>
                    {selectedArchetype === arch.id && (
                      <div className="absolute top-2 right-2 w-5 h-5 bg-[#4A7DFF] rounded-full flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ─── Step 3: Customize ─── */}
        {currentStep === 3 && (
          <div className="max-w-2xl mx-auto space-y-5">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-[15px] font-bold text-gray-900 mb-4">Step 3: カスタマイズ</h2>
              <div className="space-y-5">
                {/* Hook type */}
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-2">フックタイプ</label>
                  <div className="space-y-2">
                    {hookTypes.map((h) => (
                      <label key={h.value} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                        hookType === h.value ? "border-[#4A7DFF] bg-[#EEF2FF]" : "border-gray-200 hover:bg-gray-50"
                      }`}>
                        <input
                          type="radio"
                          name="hookType"
                          value={h.value}
                          checked={hookType === h.value}
                          onChange={(e) => setHookType(e.target.value)}
                          className="mt-0.5 text-[#4A7DFF] focus:ring-[#4A7DFF]"
                        />
                        <div>
                          <div className="text-[12px] font-medium text-gray-900">{h.label}</div>
                          <div className="text-[11px] text-gray-500">{h.example}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
                {/* CTA type */}
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">CTAタイプ</label>
                  <select
                    value={ctaType}
                    onChange={(e) => setCtaType(e.target.value)}
                    className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30"
                  >
                    {ctaTypes.map((c) => (
                      <option key={c.value} value={c.value}>{c.label} - {c.example}</option>
                    ))}
                  </select>
                </div>
                {/* Platform */}
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">プラットフォーム</label>
                  <div className="flex gap-2">
                    {platformOptions.map((p) => (
                      <button
                        key={p.value}
                        onClick={() => setPlatform(p.value)}
                        className={`px-4 py-2 rounded-lg text-[12px] font-medium transition-colors ${
                          platform === p.value ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Duration */}
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">尺（Duration）</label>
                  <div className="flex gap-2">
                    {durationOptions.map((d) => (
                      <button
                        key={d.value}
                        onClick={() => setDuration(d.value)}
                        className={`px-4 py-2 rounded-lg text-[12px] font-medium transition-colors ${
                          duration === d.value ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Tone */}
                <div>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">トーン</label>
                  <div className="flex gap-2">
                    {toneOptions.map((t) => (
                      <button
                        key={t.value}
                        onClick={() => setTone(t.value)}
                        className={`px-4 py-2 rounded-lg text-[12px] font-medium transition-colors ${
                          tone === t.value ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ─── Step 4: Generate & Preview ─── */}
        {currentStep === 4 && (
          <div className="max-w-3xl mx-auto space-y-5">
            {!generated ? (
              <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
                <h2 className="text-[15px] font-bold text-gray-900 mb-2">Step 4: シナリオ生成</h2>
                <p className="text-[12px] text-gray-500 mb-6">設定に基づいてAIがシナリオを自動生成します</p>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-[#4A7DFF] text-white rounded-xl text-[13px] font-bold hover:bg-[#3b6de6] disabled:opacity-50 transition-colors"
                >
                  {generating ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      生成中...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                      </svg>
                      シナリオ生成
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Title options */}
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <h3 className="text-[13px] font-bold text-gray-900 mb-3">タイトル候補</h3>
                  <div className="space-y-2">
                    {generated.title_options.map((title, idx) => (
                      <label key={idx} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                        selectedTitle === idx ? "border-[#4A7DFF] bg-[#EEF2FF]" : "border-gray-200 hover:bg-gray-50"
                      }`}>
                        <input
                          type="radio"
                          name="title"
                          checked={selectedTitle === idx}
                          onChange={() => setSelectedTitle(idx)}
                          className="text-[#4A7DFF] focus:ring-[#4A7DFF]"
                        />
                        <span className="text-[12px] text-gray-800">{title}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Timeline */}
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-[13px] font-bold text-gray-900">タイムライン</h3>
                    <ScoreGauge score={generated.predicted_score} />
                  </div>
                  <div className="space-y-3">
                    {generated.sections.map((section, idx) => (
                      <div key={idx} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <div className={`w-3 h-3 rounded-full ${section.color}`} />
                          {idx < generated.sections.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 my-1" />}
                        </div>
                        <div className="flex-1 pb-3">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-[10px] font-mono text-gray-400">{section.time_range}</span>
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white ${section.color}`}>{section.label}</span>
                          </div>
                          {editingSection === idx ? (
                            <div className="space-y-2">
                              <textarea
                                value={editText}
                                onChange={(e) => setEditText(e.target.value)}
                                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 resize-none"
                                rows={3}
                              />
                              <div className="flex gap-2">
                                <button onClick={() => handleSectionSave(idx)} className="px-3 py-1 text-[11px] font-medium bg-[#4A7DFF] text-white rounded-lg">保存</button>
                                <button onClick={() => setEditingSection(null)} className="px-3 py-1 text-[11px] font-medium bg-gray-100 text-gray-600 rounded-lg">キャンセル</button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-start gap-2">
                              <p className="text-[12px] text-gray-700 leading-relaxed flex-1">{section.text}</p>
                              <button onClick={() => handleSectionEdit(idx)} className="shrink-0 p-1 text-gray-400 hover:text-gray-600">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487z" />
                                </svg>
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Power Words */}
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <h3 className="text-[13px] font-bold text-gray-900 mb-3">パワーワード</h3>
                  <div className="flex flex-wrap gap-2">
                    {generated.power_words.map((word, idx) => (
                      <span key={idx} className="px-2.5 py-1 bg-orange-100 text-orange-700 rounded-full text-[11px] font-bold">
                        {word}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Regenerate */}
                <div className="text-center">
                  <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="text-[12px] text-[#4A7DFF] hover:underline font-medium"
                  >
                    再生成する
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── Step 5: Variations ─── */}
        {currentStep === 5 && (
          <div className="max-w-5xl mx-auto space-y-5">
            {variations.length === 0 ? (
              <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
                <h2 className="text-[15px] font-bold text-gray-900 mb-2">Step 5: バリエーション</h2>
                <p className="text-[12px] text-gray-500 mb-6">複数のバリエーションを生成して比較できます</p>
                <button
                  onClick={handleGenerateVariations}
                  disabled={generatingVariations}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-[#4A7DFF] text-white rounded-xl text-[13px] font-bold hover:bg-[#3b6de6] disabled:opacity-50 transition-colors"
                >
                  {generatingVariations ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      生成中...
                    </>
                  ) : (
                    "バリエーション生成"
                  )}
                </button>
              </div>
            ) : (
              <div>
                <h2 className="text-[15px] font-bold text-gray-900 mb-4">バリエーション比較</h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {variations.map((v) => (
                    <div
                      key={v.id}
                      onClick={() => setSelectedVariation(v.id)}
                      className={`bg-white rounded-xl border-2 p-5 cursor-pointer transition-all ${
                        selectedVariation === v.id ? "border-[#4A7DFF] shadow-md" : "border-gray-200 hover:border-gray-300"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-[13px] font-bold text-gray-900">{v.title}</h3>
                        <ScoreGauge score={v.predicted_score} size="small" />
                      </div>
                      <div className="space-y-2">
                        {v.sections.map((s, sIdx) => (
                          <div key={sIdx} className="flex items-start gap-2">
                            <span className={`shrink-0 mt-1 w-2 h-2 rounded-full ${s.color}`} />
                            <div>
                              <span className="text-[10px] text-gray-400 font-mono">{s.time_range}</span>
                              <p className="text-[11px] text-gray-600 leading-relaxed">{s.text}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                      {selectedVariation === v.id && (
                        <div className="mt-3 flex items-center gap-1 text-[11px] text-[#4A7DFF] font-medium">
                          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                          選択中
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── Step 6: Save & Export ─── */}
        {currentStep === 6 && (
          <div className="max-w-2xl mx-auto space-y-5">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-[15px] font-bold text-gray-900 mb-4">Step 6: 保存・エクスポート</h2>
              {saved ? (
                <div className="text-center py-8">
                  <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  </div>
                  <p className="text-[14px] font-bold text-gray-900 mb-1">シナリオを保存しました！</p>
                  <p className="text-[12px] text-gray-500">「保存済みシナリオ」からいつでも確認できます</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <button
                      onClick={() => setShowSaveModal(true)}
                      className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-200 hover:border-[#4A7DFF] hover:bg-[#EEF2FF] transition-colors"
                    >
                      <svg className="w-6 h-6 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                      </svg>
                      <span className="text-[12px] font-medium text-gray-700">保存</span>
                    </button>
                    <button
                      onClick={handleExportText}
                      className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-200 hover:border-green-500 hover:bg-green-50 transition-colors"
                    >
                      <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                      </svg>
                      <span className="text-[12px] font-medium text-gray-700">クリップボードにコピー</span>
                    </button>
                    <button
                      onClick={handleDownloadText}
                      className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-200 hover:border-purple-500 hover:bg-purple-50 transition-colors"
                    >
                      <svg className="w-6 h-6 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                      </svg>
                      <span className="text-[12px] font-medium text-gray-700">テキストダウンロード</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── Performance Checker Panel ─── */}
        {showPerformanceChecker && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[80vh] overflow-auto">
              <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-[14px] font-bold text-gray-900">パフォーマンス予測</h3>
                  <button onClick={() => { setShowPerformanceChecker(false); setPrediction(null); }} className="text-gray-400 hover:text-gray-600">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <textarea
                  value={customText}
                  onChange={(e) => setCustomText(e.target.value)}
                  placeholder="広告テキストを貼り付けてください..."
                  className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 resize-none mb-3"
                  rows={5}
                />
                <button
                  onClick={handlePredictPerformance}
                  disabled={predicting || !customText.trim()}
                  className="w-full py-2 bg-[#4A7DFF] text-white rounded-lg text-[12px] font-bold disabled:opacity-50"
                >
                  {predicting ? "分析中..." : "パフォーマンス予測"}
                </button>
                {prediction && (
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-4">
                      <ScoreGauge score={prediction.predicted_score} size="small" />
                      <div>
                        <p className="text-[12px] font-bold text-gray-900">予測スコア: {prediction.predicted_score}/100</p>
                        <p className="text-[11px] text-gray-500">ヒット確率: {prediction.hit_probability}%</p>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-[11px] font-bold text-green-600 mb-1">強み</h4>
                      {prediction.strengths.map((s, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[11px] text-gray-700">
                          <svg className="w-3 h-3 text-green-500 shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
                          {s}
                        </div>
                      ))}
                    </div>
                    <div>
                      <h4 className="text-[11px] font-bold text-red-600 mb-1">弱み</h4>
                      {prediction.weaknesses.map((w, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[11px] text-gray-700">
                          <svg className="w-3 h-3 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                          {w}
                        </div>
                      ))}
                    </div>
                    <div>
                      <h4 className="text-[11px] font-bold text-yellow-600 mb-1">改善提案</h4>
                      {prediction.suggestions.map((s, i) => (
                        <div key={i} className="flex items-start gap-1.5 text-[11px] text-gray-700">
                          <svg className="w-3 h-3 text-yellow-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
                          {s}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ─── Save Modal ─── */}
        {showSaveModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-5">
              <h3 className="text-[14px] font-bold text-gray-900 mb-3">シナリオを保存</h3>
              <input
                type="text"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                placeholder="シナリオ名を入力..."
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 mb-4"
              />
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowSaveModal(false)} className="px-4 py-2 text-[12px] font-medium text-gray-600 bg-gray-100 rounded-lg">キャンセル</button>
                <button onClick={handleSave} disabled={saving || !scenarioName.trim()} className="px-4 py-2 text-[12px] font-bold text-white bg-[#4A7DFF] rounded-lg disabled:opacity-50">
                  {saving ? "保存中..." : "保存"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer Navigation */}
      <div className="shrink-0 bg-white border-t border-gray-200 px-5 py-3 flex items-center justify-between">
        <button
          onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}
          disabled={currentStep === 1}
          className="px-4 py-2 text-[12px] font-medium text-gray-600 bg-gray-100 rounded-lg disabled:opacity-30 hover:bg-gray-200 transition-colors"
        >
          戻る
        </button>
        <span className="text-[11px] text-gray-400">Step {currentStep} / {totalSteps}</span>
        {currentStep < totalSteps ? (
          <button
            onClick={() => setCurrentStep(Math.min(totalSteps, currentStep + 1))}
            disabled={!canProceed()}
            className="px-4 py-2 text-[12px] font-bold text-white bg-[#4A7DFF] rounded-lg disabled:opacity-30 hover:bg-[#3b6de6] transition-colors"
          >
            次へ
          </button>
        ) : (
          <div />
        )}
      </div>
    </div>
  );
}
