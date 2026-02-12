"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { analyticsApi } from "@/lib/api";

interface CompetitorData {
  advertiser: string;
  total_ads: number;
  analyzed_ads: number;
  platform_distribution: Record<string, number>;
  sentiment_distribution: Record<string, number>;
  top_keywords: Array<{ keyword: string; count: number }>;
  avg_winning_score?: number;
}

export default function CompetitorView() {
  const [competitorName, setCompetitorName] = useState("");
  const [data, setData] = useState<CompetitorData | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!competitorName.trim()) return;

    setLoading(true);
    try {
      const response = await analyticsApi.getCompetitor(competitorName);
      setData(response.data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const platformData = data
    ? Object.entries(data.platform_distribution).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Competitor Analysis</h2>
        <p className="mt-1 text-sm text-gray-500">
          Analyze competitor ad strategies and patterns
        </p>
      </div>

      {/* Search */}
      <div className="card">
        <form onSubmit={handleSearch} className="flex gap-4">
          <input
            type="text"
            value={competitorName}
            onChange={(e) => setCompetitorName(e.target.value)}
            placeholder="Enter competitor/advertiser name..."
            className="input flex-1"
          />
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>
      </div>

      {data && (
        <>
          {/* Overview */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="card text-center">
              <p className="text-sm text-gray-500">Total Ads</p>
              <p className="mt-1 text-3xl font-bold">{data.total_ads}</p>
            </div>
            <div className="card text-center">
              <p className="text-sm text-gray-500">Analyzed</p>
              <p className="mt-1 text-3xl font-bold">{data.analyzed_ads}</p>
            </div>
            <div className="card text-center">
              <p className="text-sm text-gray-500">Avg Winning Score</p>
              <p className="mt-1 text-3xl font-bold">
                {data.avg_winning_score ?? "N/A"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Platform Distribution */}
            <div className="card">
              <h3 className="mb-4 text-lg font-semibold">Platform Distribution</h3>
              {platformData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={platformData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="py-8 text-center text-gray-400">No data</p>
              )}
            </div>

            {/* Top Keywords */}
            <div className="card">
              <h3 className="mb-4 text-lg font-semibold">Top Keywords</h3>
              {data.top_keywords.length > 0 ? (
                <div className="space-y-2">
                  {data.top_keywords.slice(0, 15).map((kw, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-sm text-gray-700">{kw.keyword}</span>
                      <div className="flex items-center gap-2">
                        <div
                          className="h-2 rounded-full bg-primary-500"
                          style={{
                            width: `${Math.min((kw.count / data.top_keywords[0].count) * 120, 120)}px`,
                          }}
                        />
                        <span className="text-xs text-gray-500">{kw.count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-8 text-center text-gray-400">No keywords found</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
