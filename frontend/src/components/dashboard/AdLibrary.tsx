"use client";

import { useEffect, useState } from "react";
import { adsApi } from "@/lib/api";
import type { Ad } from "@/types";

interface AdLibraryProps {
  onAdSelect: (adId: number) => void;
}

const platformColors: Record<string, string> = {
  youtube: "bg-red-100 text-red-800",
  tiktok: "bg-gray-900 text-white",
  meta: "bg-blue-100 text-blue-800",
  instagram: "bg-purple-100 text-purple-800",
  facebook: "bg-blue-100 text-blue-800",
  x_twitter: "bg-gray-100 text-gray-800",
  x: "bg-gray-100 text-gray-800",
  line: "bg-green-100 text-green-800",
  yahoo: "bg-red-50 text-red-700",
  pinterest: "bg-red-100 text-red-700",
  smartnews: "bg-sky-100 text-sky-800",
  google_ads: "bg-blue-100 text-blue-700",
  gunosy: "bg-orange-100 text-orange-800",
};

const statusColors: Record<string, string> = {
  pending: "badge-yellow",
  processing: "badge-blue",
  analyzed: "badge-green",
  failed: "badge-red",
};

export default function AdLibrary({ onAdSelect }: AdLibraryProps) {
  const [ads, setAds] = useState<Ad[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [showCrawlModal, setShowCrawlModal] = useState(false);
  const pageSize = 20;

  useEffect(() => {
    loadAds();
  }, [page, platformFilter]);

  const loadAds = async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (platformFilter) params.platform = platformFilter;
      if (searchQuery) params.advertiser = searchQuery;

      const response = await adsApi.list(params);
      setAds(response.data.ads);
      setTotal(response.data.total);
    } catch {
      setAds([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadAds();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Ad Library</h2>
          <p className="mt-1 text-sm text-gray-500">
            {total} ads collected across platforms
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowCrawlModal(true)}
            className="btn-primary"
          >
            Crawl Ads
          </button>
          <label className="btn-secondary cursor-pointer">
            Upload Video
            <input
              type="file"
              accept="video/*"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) {
                  await adsApi.upload(file, { auto_analyze: true });
                  loadAds();
                }
              }}
            />
          </label>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <form onSubmit={handleSearch} className="flex gap-4">
          <input
            type="text"
            placeholder="Search by advertiser..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input flex-1"
          />
          <select
            value={platformFilter}
            onChange={(e) => {
              setPlatformFilter(e.target.value);
              setPage(1);
            }}
            className="input w-48"
          >
            <option value="">All Platforms</option>
            <option value="meta">Meta (FB/IG)</option>
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
          <button type="submit" className="btn-primary">
            Search
          </button>
        </form>
      </div>

      {/* Ad Grid */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        </div>
      ) : ads.length === 0 ? (
        <div className="card text-center">
          <p className="text-gray-500">
            No ads found. Start by crawling ads or uploading a video.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {ads.map((ad) => (
            <div
              key={ad.id}
              onClick={() => onAdSelect(ad.id)}
              className="card cursor-pointer transition-shadow hover:shadow-md"
            >
              {/* Thumbnail placeholder */}
              <div className="mb-3 flex h-40 items-center justify-center rounded-lg bg-gray-100">
                <svg
                  className="h-12 w-12 text-gray-300"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1}
                    d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              </div>

              {/* Ad Info */}
              <h4 className="truncate font-medium text-gray-900">
                {ad.title || "Untitled Ad"}
              </h4>
              <p className="mt-1 text-sm text-gray-500">
                {ad.advertiser_name || "Unknown Advertiser"}
              </p>

              <div className="mt-3 flex items-center gap-2">
                <span
                  className={`badge ${platformColors[ad.platform] || "bg-gray-100 text-gray-800"}`}
                >
                  {ad.platform}
                </span>
                <span className={statusColors[ad.status] || "badge"}>
                  {ad.status}
                </span>
                {ad.duration_seconds && (
                  <span className="text-xs text-gray-500">
                    {Math.round(ad.duration_seconds)}s
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary"
          >
            Previous
          </button>
          <span className="flex items-center px-4 text-sm text-gray-600">
            Page {page} of {Math.ceil(total / pageSize)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= Math.ceil(total / pageSize)}
            className="btn-secondary"
          >
            Next
          </button>
        </div>
      )}

      {/* Crawl Modal */}
      {showCrawlModal && (
        <CrawlModal
          onClose={() => setShowCrawlModal(false)}
          onSuccess={() => {
            setShowCrawlModal(false);
            loadAds();
          }}
        />
      )}
    </div>
  );
}

function CrawlModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [query, setQuery] = useState("");
  const [platforms, setPlatforms] = useState(["facebook", "instagram", "youtube", "tiktok", "x_twitter", "line", "yahoo", "pinterest", "smartnews", "google_ads", "gunosy"]);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(false);

  const handleCrawl = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      await adsApi.crawl({
        query,
        platforms,
        limit_per_platform: limit,
        auto_analyze: true,
      });
      onSuccess();
    } catch {
      alert("Crawl failed. Check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <h3 className="text-lg font-semibold">Crawl Competitor Ads</h3>

        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Search Query
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., competitor name, product category..."
              className="input mt-1"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Platforms
            </label>
            <div className="mt-2 flex gap-3">
              {["facebook", "instagram", "youtube", "tiktok", "x_twitter", "line", "yahoo", "pinterest", "smartnews", "google_ads", "gunosy"].map((p) => (
                <label key={p} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={platforms.includes(p)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setPlatforms([...platforms, p]);
                      } else {
                        setPlatforms(platforms.filter((x) => x !== p));
                      }
                    }}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm capitalize">{p}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Limit per Platform
            </label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              min={1}
              max={100}
              className="input mt-1 w-32"
            />
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button
            onClick={handleCrawl}
            disabled={loading || !query.trim()}
            className="btn-primary"
          >
            {loading ? "Crawling..." : "Start Crawl"}
          </button>
        </div>
      </div>
    </div>
  );
}
