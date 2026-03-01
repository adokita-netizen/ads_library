"use client";

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { fetchApi } from "@/lib/api";
import { ErrorState } from "@/components/common/StateDisplay";

// ─── Types ───

interface DayData {
  date: string; // YYYY-MM-DD
  totalAds: number;
  hitAds: number;
  regularAds: number;
}

interface AdSummary {
  ad_id: number;
  product_name: string;
  advertiser_name: string;
  genre: string;
  is_hit: boolean;
  hit_score: number;
  cumulative_views: number;
}

// ─── Helpers ───

const WEEKDAY_LABELS = ["日", "月", "火", "水", "木", "金", "土"];

function getHeatColor(count: number, maxCount: number): string {
  if (count === 0) return "bg-gray-50";
  const ratio = count / (maxCount || 1);
  if (ratio > 0.75) return "bg-blue-200";
  if (ratio > 0.5) return "bg-blue-100";
  if (ratio > 0.25) return "bg-blue-50";
  return "bg-sky-50";
}

// ─── Component ───

export default function CalendarView() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [dayDataMap, setDayDataMap] = useState<Record<string, DayData>>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedDayAds, setSelectedDayAds] = useState<AdSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const monthLabel = `${year}年${month + 1}月`;

  // Fetch calendar data for current month
  const loadData = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setCalendarError(null);
    try {
      const data = await fetchApi<{
        days?: Array<{ day: number; total_ads: number; hit_ads: number }>;
      }>("/rankings/calendar", { params: { year, month: month + 1 } });

      if (controller.signal.aborted) return;

      const map: Record<string, DayData> = {};
      (data.days || []).forEach((d) => {
        const date = `${year}-${String(month + 1).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`;
        map[date] = {
          date,
          totalAds: d.total_ads || 0,
          hitAds: d.hit_ads || 0,
          regularAds: Math.max(0, (d.total_ads || 0) - (d.hit_ads || 0)),
        };
      });
      setDayDataMap(map);
    } catch {
      if (controller.signal.aborted) return;
      setCalendarError("カレンダーデータの取得に失敗しました");
      setDayDataMap({});
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    loadData();
    return () => { if (abortRef.current) abortRef.current.abort(); };
  }, [loadData]);

  // Calendar grid calculation
  const calendarDays = useMemo(() => {
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells: (number | null)[] = [];
    for (let i = 0; i < firstDay; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [year, month]);

  const maxAds = useMemo(() => {
    return Math.max(...Object.values(dayDataMap).map((d) => d.totalAds), 1);
  }, [dayDataMap]);

  const handleDayClick = useCallback(async (day: number) => {
    const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    setSelectedDate(dateStr);
    try {
      const res = await fetchApi<{
        items?: Array<{
          ad_id: number;
          product_name?: string;
          title?: string;
          advertiser_name?: string;
          fine_genre_en?: string;
          genre?: string;
          is_hit?: boolean;
          hit_score?: number;
          total_views?: number;
          cumulative_views?: number;
        }>;
      }>("/rankings/pro-ranking", {
        params: {
          date_from: dateStr,
          date_to: dateStr,
          sort_by: "score",
          per_page: 100,
          page: 1,
        },
      });

      const items = Array.isArray(res.items) ? res.items : [];
      setSelectedDayAds(
        items.map((ad) => ({
          ad_id: ad.ad_id,
          product_name: ad.product_name || ad.title || "不明",
          advertiser_name: ad.advertiser_name || "不明",
          genre: ad.fine_genre_en || ad.genre || "未分類",
          is_hit: Boolean(ad.is_hit),
          hit_score: Number(ad.hit_score || 0),
          cumulative_views: Number(ad.cumulative_views || ad.total_views || 0),
        }))
      );
    } catch {
      setSelectedDayAds([]);
    }
  }, [year, month]);

  const goToPrevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
    setSelectedDate(null);
    setSelectedDayAds([]);
  };
  const goToNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
    setSelectedDate(null);
    setSelectedDayAds([]);
  };
  const goToToday = () => {
    setCurrentDate(new Date());
    setSelectedDate(null);
    setSelectedDayAds([]);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">カレンダー</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">広告アクティビティを日別に可視化</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto custom-scrollbar p-5">
        {calendarError && (
          <div className="mb-4">
            <ErrorState message={calendarError} onRetry={loadData} compact />
          </div>
        )}
        <div className="flex gap-5">
          {/* Calendar Grid */}
          <div className="flex-1">
            {/* Month navigation */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <button onClick={goToPrevMonth} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                  </svg>
                </button>
                <h3 className="text-[14px] font-bold text-gray-900 min-w-[100px] text-center">{monthLabel}</h3>
                <button onClick={goToNextMonth} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </button>
                <button onClick={goToToday} className="ml-2 px-2 py-1 text-[10px] font-medium text-[#4A7DFF] bg-blue-50 rounded hover:bg-blue-100">
                  今日
                </button>
              </div>

              {/* Legend */}
              <div className="flex items-center gap-4 text-[10px] text-gray-500">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span>ヒット広告</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-gray-400"></span>
                  <span>通常広告</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="inline-block w-4 h-3 rounded bg-blue-200"></span>
                  <span>新規広告数（多）</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="inline-block w-4 h-3 rounded bg-blue-50"></span>
                  <span>新規広告数（少）</span>
                </div>
              </div>
            </div>

            {loading && (
              <div className="flex items-center justify-center py-10 text-gray-400 text-xs">読み込み中...</div>
            )}

            {/* Weekday Headers */}
            <div className="grid grid-cols-7 gap-px mb-px">
              {WEEKDAY_LABELS.map((label, i) => (
                <div key={i} className={`text-center text-[10px] font-medium py-1.5 ${i === 0 ? "text-red-400" : i === 6 ? "text-blue-400" : "text-gray-500"}`}>
                  {label}
                </div>
              ))}
            </div>

            {/* Day cells */}
            <div className="grid grid-cols-7 gap-px bg-gray-200 border border-gray-200 rounded-lg overflow-hidden">
              {calendarDays.map((day, idx) => {
                if (day === null) {
                  return <div key={idx} className="bg-gray-50 min-h-[80px]" />;
                }
                const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const data = dayDataMap[dateStr];
                const isToday =
                  new Date().getFullYear() === year &&
                  new Date().getMonth() === month &&
                  new Date().getDate() === day;
                const isSelected = selectedDate === dateStr;
                const weekday = idx % 7;

                return (
                  <button
                    key={idx}
                    onClick={() => handleDayClick(day)}
                    className={`min-h-[80px] p-1.5 text-left transition-colors ${
                      getHeatColor(data?.totalAds || 0, maxAds)
                    } ${isSelected ? "ring-2 ring-[#4A7DFF] ring-inset" : ""} hover:bg-blue-50`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-[11px] font-medium ${
                          isToday ? "bg-[#4A7DFF] text-white w-5 h-5 rounded-full flex items-center justify-center" : weekday === 0 ? "text-red-400" : weekday === 6 ? "text-blue-400" : "text-gray-700"
                        }`}
                      >
                        {day}
                      </span>
                      {data && data.totalAds > 0 && (
                        <span className="text-[9px] font-bold text-gray-500">{data.totalAds}件</span>
                      )}
                    </div>
                    {data && data.totalAds > 0 && (
                      <div className="mt-1 flex items-center gap-0.5 flex-wrap">
                        {Array.from({ length: Math.min(data.hitAds, 5) }).map((_, i) => (
                          <span key={`h${i}`} className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                        ))}
                        {Array.from({ length: Math.min(data.regularAds, 5) }).map((_, i) => (
                          <span key={`r${i}`} className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                        ))}
                        {data.totalAds > 10 && (
                          <span className="text-[8px] text-gray-400 ml-0.5">+{data.totalAds - 10}</span>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Day Detail Sidebar */}
          <div className="w-80 shrink-0">
            {selectedDate ? (
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 bg-[#f8f9fc]">
                  <h4 className="text-[13px] font-bold text-gray-900">
                    {selectedDate.replace(/-/g, "/")} の広告
                  </h4>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    {dayDataMap[selectedDate]?.totalAds || 0}件の広告
                    {dayDataMap[selectedDate]?.hitAds ? ` (ヒット: ${dayDataMap[selectedDate].hitAds}件)` : ""}
                  </p>
                </div>
                <div className="max-h-[500px] overflow-y-auto custom-scrollbar divide-y divide-gray-100">
                  {selectedDayAds.length === 0 ? (
                    <div className="p-4 text-center text-[11px] text-gray-400">広告データなし</div>
                  ) : (
                    selectedDayAds.map((ad) => (
                      <div key={ad.ad_id} className="px-4 py-3 hover:bg-gray-50 cursor-pointer">
                        <div className="flex items-center gap-2">
                          {ad.is_hit && (
                            <span className="shrink-0 w-4 h-4 rounded-full bg-amber-100 flex items-center justify-center">
                              <svg className="w-2.5 h-2.5 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
                              </svg>
                            </span>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-[11px] font-medium text-gray-900 truncate">{ad.product_name}</p>
                            <p className="text-[10px] text-gray-500 truncate">{ad.advertiser_name}</p>
                          </div>
                          <div className="text-right shrink-0">
                            <span className="text-[10px] font-bold text-[#4A7DFF]">
                              {ad.hit_score}pt
                            </span>
                            <p className="text-[9px] text-gray-400">
                              {(ad.cumulative_views / 1000).toFixed(0)}K views
                            </p>
                          </div>
                        </div>
                        <div className="mt-1 flex items-center gap-1">
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{ad.genre}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg p-6 text-center">
                <svg className="w-10 h-10 text-gray-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                </svg>
                <p className="text-[11px] text-gray-400">日付をクリックすると<br />その日の広告を表示します</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
