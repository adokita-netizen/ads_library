"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { analyticsApi } from "@/lib/api";
import type { DashboardStats } from "@/types";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

export default function DashboardView() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const response = await analyticsApi.getDashboard();
      setStats(response.data);
    } catch {
      // Use mock data if API not available
      setStats({
        total_ads: 0,
        analyzed_ads: 0,
        analysis_rate: 0,
        ads_by_platform: {},
        ads_by_category: {},
        avg_winning_score: undefined,
        sentiment_distribution: {},
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  const platformData = Object.entries(stats?.ads_by_platform || {}).map(
    ([name, value]) => ({ name, value })
  );

  const sentimentData = Object.entries(stats?.sentiment_distribution || {}).map(
    ([name, value]) => ({ name, value })
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="mt-1 text-sm text-gray-500">
          Overview of your ad analysis platform
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <KPICard
          title="Total Ads"
          value={stats?.total_ads || 0}
          subtitle="Collected ads"
        />
        <KPICard
          title="Analyzed"
          value={stats?.analyzed_ads || 0}
          subtitle={`${((stats?.analysis_rate || 0) * 100).toFixed(0)}% analyzed`}
        />
        <KPICard
          title="Avg Winning Score"
          value={stats?.avg_winning_score ? `${stats.avg_winning_score}` : "N/A"}
          subtitle="Out of 100"
        />
        <KPICard
          title="Platforms"
          value={Object.keys(stats?.ads_by_platform || {}).length}
          subtitle="Active platforms"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Platform Distribution */}
        <div className="card">
          <h3 className="mb-4 text-lg font-semibold">Ads by Platform</h3>
          {platformData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={platformData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="No platform data yet. Start by crawling or uploading ads." />
          )}
        </div>

        {/* Sentiment Distribution */}
        <div className="card">
          <h3 className="mb-4 text-lg font-semibold">Sentiment Distribution</h3>
          {sentimentData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={sentimentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${name} (${(percent * 100).toFixed(0)}%)`
                  }
                >
                  {sentimentData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="Analyze ads to see sentiment distribution." />
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="mb-4 text-lg font-semibold">Quick Actions</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <ActionCard
            title="Crawl Ads"
            description="Collect competitor ads from platforms"
            action="Start Crawling"
          />
          <ActionCard
            title="Upload Video"
            description="Upload and analyze a video ad"
            action="Upload"
          />
          <ActionCard
            title="Generate Script"
            description="AI-powered ad script generation"
            action="Create"
          />
          <ActionCard
            title="View Trends"
            description="Industry trends and patterns"
            action="Explore"
          />
        </div>
      </div>
    </div>
  );
}

function KPICard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: number | string;
  subtitle: string;
}) {
  return (
    <div className="card">
      <p className="text-sm font-medium text-gray-600">{title}</p>
      <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
      <p className="mt-1 text-sm text-gray-500">{subtitle}</p>
    </div>
  );
}

function ActionCard({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 transition-shadow hover:shadow-md">
      <h4 className="font-medium text-gray-900">{title}</h4>
      <p className="mt-1 text-sm text-gray-500">{description}</p>
      <button className="btn-primary mt-3 w-full text-center">{action}</button>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-[300px] items-center justify-center text-gray-400">
      <p className="text-center text-sm">{message}</p>
    </div>
  );
}
