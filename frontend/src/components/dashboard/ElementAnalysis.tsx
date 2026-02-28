"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

// ─── Types ───

interface ElementItem {
  name: string;
  count: number;
  hit_rate: number;
  overall_rate: number;
  is_high_performer: boolean;
}

interface ElementCategory {
  label: string;
  items: ElementItem[];
}

// ─── Mock Data (TODO: Replace with API calls when endpoints are ready) ───

const MOCK_ELEMENTS: ElementCategory[] = [
  {
    label: "フックタイプ",
    items: [
      { name: "質問型", count: 120, hit_rate: 72, overall_rate: 45, is_high_performer: true },
      { name: "衝撃型", count: 87, hit_rate: 65, overall_rate: 42, is_high_performer: true },
      { name: "ベネフィット型", count: 145, hit_rate: 38, overall_rate: 40, is_high_performer: false },
      { name: "ストーリー型", count: 70, hit_rate: 55, overall_rate: 35, is_high_performer: true },
      { name: "数字型", count: 55, hit_rate: 68, overall_rate: 30, is_high_performer: true },
    ],
  },
  {
    label: "CTAタイプ",
    items: [
      { name: "限定オファー", count: 127, hit_rate: 70, overall_rate: 48, is_high_performer: true },
      { name: "無料お試し", count: 96, hit_rate: 62, overall_rate: 40, is_high_performer: true },
      { name: "保証付き", count: 63, hit_rate: 58, overall_rate: 35, is_high_performer: true },
      { name: "緊急性", count: 105, hit_rate: 32, overall_rate: 42, is_high_performer: false },
      { name: "詳細はこちら", count: 88, hit_rate: 25, overall_rate: 38, is_high_performer: false },
    ],
  },
  {
    label: "オファータイプ",
    items: [
      { name: "割引（%OFF）", count: 155, hit_rate: 55, overall_rate: 50, is_high_performer: true },
      { name: "無料トライアル", count: 85, hit_rate: 67, overall_rate: 35, is_high_performer: true },
      { name: "限定品", count: 56, hit_rate: 60, overall_rate: 28, is_high_performer: true },
      { name: "セット販売", count: 95, hit_rate: 35, overall_rate: 42, is_high_performer: false },
      { name: "送料無料", count: 72, hit_rate: 48, overall_rate: 32, is_high_performer: false },
    ],
  },
  {
    label: "感情タイプ",
    items: [
      { name: "不安・恐怖", count: 98, hit_rate: 68, overall_rate: 40, is_high_performer: true },
      { name: "希望・期待", count: 112, hit_rate: 52, overall_rate: 45, is_high_performer: true },
      { name: "怒り・不満", count: 45, hit_rate: 55, overall_rate: 25, is_high_performer: true },
      { name: "共感", count: 130, hit_rate: 45, overall_rate: 48, is_high_performer: false },
      { name: "驚き", count: 67, hit_rate: 70, overall_rate: 30, is_high_performer: true },
    ],
  },
];

// ─── Main Component ───

interface ElementAnalysisProps {
  onElementFilter?: (category: string, element: string) => void;
  genre?: string;
}

export default function ElementAnalysis({ onElementFilter, genre }: ElementAnalysisProps) {
  const [loading, setLoading] = useState(true);
  const [elements, setElements] = useState<ElementCategory[]>([]);
  const [selectedElement, setSelectedElement] = useState<{ category: string; name: string } | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // TODO: Replace with actual API call when endpoint is ready
      // const data = await fetchApi<{ categories: ElementCategory[] }>("/rankings/element-analysis", {
      //   params: { genre: genre || undefined },
      // });
      // setElements(data.categories || []);
      await new Promise((r) => setTimeout(r, 500));
      setElements(MOCK_ELEMENTS);
    } catch (err) {
      console.error("要素分析データの取得に失敗しました", err);
    } finally {
      setLoading(false);
    }
  }, [genre]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleElementClick = (category: string, name: string) => {
    if (selectedElement?.category === category && selectedElement?.name === name) {
      setSelectedElement(null);
      onElementFilter?.("", "");
    } else {
      setSelectedElement({ category, name });
      onElementFilter?.(category, name);
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-24 mb-4" />
            <div className="space-y-3">
              {[1, 2, 3].map((j) => (
                <div key={j} className="h-6 bg-gray-100 rounded" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-gray-900">要素別分析</h3>
        {selectedElement && (
          <button
            onClick={() => { setSelectedElement(null); onElementFilter?.("", ""); }}
            className="text-[11px] text-[#4A7DFF] hover:underline font-medium"
          >
            フィルター解除
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {elements.map((category) => (
          <div key={category.label} className="bg-white rounded-xl border border-gray-200 p-5">
            <h4 className="text-[13px] font-bold text-gray-900 mb-3">{category.label}</h4>
            <div className="space-y-2">
              {category.items.map((item) => {
                const isSelected = selectedElement?.category === category.label && selectedElement?.name === item.name;
                const maxHitRate = Math.max(...category.items.map((i) => i.hit_rate));
                const barWidth = maxHitRate > 0 ? (item.hit_rate / maxHitRate) * 100 : 0;
                return (
                  <button
                    key={item.name}
                    onClick={() => handleElementClick(category.label, item.name)}
                    className={`w-full text-left p-2.5 rounded-lg border transition-all ${
                      isSelected
                        ? "border-[#4A7DFF] bg-[#EEF2FF] shadow-sm"
                        : "border-transparent hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-medium text-gray-900">{item.name}</span>
                        {item.is_high_performer && (
                          <span className="px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded text-[9px] font-bold">即転用</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-gray-400">{item.count}件</span>
                        <span className={`text-[11px] font-bold ${
                          item.hit_rate >= 60 ? "text-green-600" : item.hit_rate >= 40 ? "text-yellow-600" : "text-red-500"
                        }`}>
                          {item.hit_rate}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            item.hit_rate >= 60 ? "bg-green-400" : item.hit_rate >= 40 ? "bg-yellow-400" : "bg-red-400"
                          }`}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-[9px] text-gray-400">ヒット率: {item.hit_rate}%</span>
                      <span className="text-[9px] text-gray-400">全体: {item.overall_rate}%</span>
                      {item.hit_rate > item.overall_rate && (
                        <span className="text-[9px] text-green-600 font-medium">
                          +{(item.hit_rate - item.overall_rate).toFixed(0)}pt
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
