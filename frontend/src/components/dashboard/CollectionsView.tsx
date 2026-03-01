"use client";

import React, { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import SharedCollectionCreator from "./SharedCollectionCreator";

interface Collection {
  id: number | string;
  name: string;
  description?: string;
  ad_count: number;
  created_at?: string;
}

interface CollectionAd {
  ad_id: number;
  product_name?: string;
  title?: string;
  hit_score?: number;
  hit_level?: string;
  thumbnail?: string;
  image_url?: string;
  platform?: string;
  advertiser_name?: string;
  cumulative_spend?: number;
}

interface BookmarkedAd {
  ad_id: number;
  product_name?: string;
  title?: string;
  hit_score?: number;
  hit_level?: string;
  thumbnail?: string;
  image_url?: string;
  platform?: string;
  advertiser_name?: string;
  bookmarked_at?: string;
}

interface CollectionsViewProps {
  onAdSelect?: (adId: number) => void;
  /** When true, render with header for sidebar full-page mode */
  fullPage?: boolean;
}

export default function CollectionsView({ onAdSelect, fullPage }: CollectionsViewProps) {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null);
  const [collectionAds, setCollectionAds] = useState<CollectionAd[]>([]);
  const [adsLoading, setAdsLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showSharedCreator, setShowSharedCreator] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [activeTab, setActiveTab] = useState<"collections" | "bookmarks">("collections");
  const [bookmarks, setBookmarks] = useState<BookmarkedAd[]>([]);
  const [bookmarksLoading, setBookmarksLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadCollections = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchApi<{ items?: Collection[]; collections?: Collection[] }>("/rankings/collections").catch(() => null);
      if (res) {
        const items = res.items || res.collections || (Array.isArray(res) ? res : []);
        setCollections(Array.isArray(items) ? items : []);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadCollections(); }, [loadCollections]);

  const loadBookmarks = useCallback(async () => {
    setBookmarksLoading(true);
    try {
      const res = await fetchApi<{ items?: BookmarkedAd[]; bookmarks?: BookmarkedAd[] }>("/rankings/bookmarks");
      const items = res.items || res.bookmarks || (Array.isArray(res) ? res : []);
      setBookmarks(Array.isArray(items) ? items : []);
    } catch {
      setBookmarks([]);
    } finally {
      setBookmarksLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "bookmarks") loadBookmarks();
  }, [activeTab, loadBookmarks]);

  const loadCollectionAds = useCallback(async (collectionId: number | string) => {
    setAdsLoading(true);
    try {
      const res = await fetchApi<{ items?: CollectionAd[]; ads?: CollectionAd[] }>(`/rankings/collections/${collectionId}/ads`).catch(() => null);
      if (res) {
        const items = res.items || res.ads || (Array.isArray(res) ? res : []);
        setCollectionAds(Array.isArray(items) ? items : []);
      }
    } finally {
      setAdsLoading(false);
    }
  }, []);

  const handleCreate = async () => {
    if (!newName.trim() || creating) return;
    setCreating(true);
    try {
      await fetchApi("/rankings/collections", {
        method: "POST",
        body: { name: newName.trim(), description: newDesc.trim() || undefined },
      });
      toast.success("コレクションを作成しました");
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      loadCollections();
    } catch {
      toast.error("コレクション作成に失敗しました");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number | string) => {
    if (deleteConfirm !== id) {
      setDeleteConfirm(id);
      return;
    }
    if (deleting) return;
    setDeleting(true);
    try {
      await fetchApi(`/rankings/collections/${id}`, { method: "DELETE" });
      toast.success("コレクションを削除しました");
      if (selectedCollection?.id === id) {
        setSelectedCollection(null);
        setCollectionAds([]);
      }
      loadCollections();
    } catch {
      toast.error("削除に失敗しました");
    } finally {
      setDeleting(false);
      setDeleteConfirm(null);
    }
  };

  /* ─── Ad Card (shared) ─── */
  const renderAdCard = (ad: { ad_id: number; product_name?: string; title?: string; hit_score?: number; hit_level?: string; thumbnail?: string; image_url?: string; advertiser_name?: string; platform?: string }) => {
    const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || ad.image_url || "");
    return (
      <div
        key={ad.ad_id}
        className="card overflow-hidden cursor-pointer hover:shadow-md transition-all group"
        onClick={() => onAdSelect?.(ad.ad_id)}
      >
        <div className="relative aspect-video bg-gray-100 overflow-hidden">
          {thumbSrc && (
            <img
              src={thumbSrc}
              alt=""
              className="w-full h-full object-cover group-hover:scale-105 transition-transform"
              loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          {ad.hit_level === "mega_hit" && (
            <span className="absolute top-1 left-1 text-[7px] px-1 py-0.5 rounded bg-red-500 text-white font-bold">大HIT</span>
          )}
          {ad.hit_level === "hit" && (
            <span className="absolute top-1 left-1 text-[7px] px-1 py-0.5 rounded bg-orange-500 text-white font-bold">HIT</span>
          )}
          <span className="absolute top-1 right-1 text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-white font-bold">
            {ad.hit_score || 0}
          </span>
        </div>
        <div className="px-2.5 py-2">
          <p className="text-[11px] font-medium text-gray-900 truncate">{ad.product_name || ad.title || "不明"}</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            <p className="text-[9px] text-gray-400 truncate flex-1">{ad.advertiser_name || "-"}</p>
            {ad.platform && (
              <span className="text-[8px] px-1 py-0.5 rounded bg-gray-100 text-gray-500">{ad.platform}</span>
            )}
          </div>
        </div>
      </div>
    );
  };

  /* ─── Collection detail view ─── */
  if (selectedCollection) {
    return (
      <div className={fullPage ? "flex flex-col h-full" : "space-y-4"}>
        {fullPage && (
          <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-200 bg-white">
            <button
              onClick={() => { setSelectedCollection(null); setCollectionAds([]); }}
              className="text-[11px] px-2 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
              戻る
            </button>
            <h3 className="text-[14px] font-bold text-gray-900">{selectedCollection.name}</h3>
            <span className="text-[10px] text-gray-400">{collectionAds.length}件</span>
          </div>
        )}
        <div className={fullPage ? "flex-1 overflow-y-auto custom-scrollbar px-5 py-4" : ""}>
          {!fullPage && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => { setSelectedCollection(null); setCollectionAds([]); }}
                className="text-[11px] px-2 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                </svg>
                戻る
              </button>
              <h3 className="text-[14px] font-bold text-gray-900">{selectedCollection.name}</h3>
              <span className="text-[10px] text-gray-400">{collectionAds.length}件</span>
            </div>
          )}

          {adsLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="card animate-pulse">
                  <div className="aspect-video bg-gray-100 rounded-lg mb-2" />
                  <div className="h-3 bg-gray-200 rounded w-24 mb-1" />
                  <div className="h-2.5 bg-gray-100 rounded w-16" />
                </div>
              ))}
            </div>
          ) : collectionAds.length === 0 ? (
            <div className="card px-4 py-8 text-center mt-4">
              <p className="text-[12px] text-gray-500">このコレクションに広告がありません</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-4">
              {collectionAds.map(renderAdCard)}
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ─── Main view ─── */
  const mainContent = (
    <div className="space-y-4">
      {/* Tab switcher: Collections vs Bookmarks */}
      <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5 w-fit">
        <button
          onClick={() => setActiveTab("collections")}
          className={`px-3 py-1.5 rounded-md text-[11px] font-medium transition-colors ${
            activeTab === "collections" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          コレクション
        </button>
        <button
          onClick={() => setActiveTab("bookmarks")}
          className={`px-3 py-1.5 rounded-md text-[11px] font-medium transition-colors ${
            activeTab === "bookmarks" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          ブックマーク
        </button>
      </div>

      {activeTab === "collections" ? (
        <>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <h3 className="text-[13px] font-bold text-gray-900">コレクション</h3>
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="h-7 px-3 rounded-lg text-[10px] font-medium text-white bg-[#4A7DFF] hover:bg-[#3a6ae8] transition-colors flex items-center gap-1"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              新規作成
            </button>
          </div>

          {/* Create form */}
          {showCreate && (
            <div className="card px-4 py-3 space-y-2">
              <input
                type="text"
                placeholder="コレクション名"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full h-8 px-3 rounded-lg border border-gray-200 text-[11px] text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
                onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
              />
              <input
                type="text"
                placeholder="説明（任意）"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                className="w-full h-8 px-3 rounded-lg border border-gray-200 text-[11px] text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
              />
              <div className="flex items-center gap-2">
                <button onClick={handleCreate} className="h-7 px-3 rounded-lg text-[10px] font-medium text-white bg-[#4A7DFF] hover:bg-[#3a6ae8] transition-colors">
                  作成
                </button>
                <button onClick={() => { setShowCreate(false); setNewName(""); setNewDesc(""); }} className="h-7 px-3 rounded-lg text-[10px] text-gray-500 hover:bg-gray-100 transition-colors">
                  キャンセル
                </button>
              </div>
            </div>
          )}

          {/* Collections grid */}
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="card px-4 py-4 animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-32 mb-2" />
                  <div className="h-3 bg-gray-100 rounded w-20" />
                </div>
              ))}
            </div>
          ) : collections.length === 0 ? (
            <div className="card px-4 py-10 text-center">
              <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <p className="text-[12px] text-gray-500 mb-1">コレクションがありません</p>
              <p className="text-[10px] text-gray-400">上の「新規作成」をクリックして始めましょう</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {collections.map((col) => (
                <div
                  key={col.id}
                  className="card px-4 py-3 cursor-pointer hover:shadow-md transition-all group"
                  onClick={() => { setSelectedCollection(col); loadCollectionAds(col.id); }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="text-[12px] font-bold text-gray-900 truncate">{col.name}</h4>
                    <button
                      className={`transition-all p-0.5 ${
                        deleteConfirm === col.id
                          ? "opacity-100 text-red-500"
                          : "opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"
                      }`}
                      onClick={(e) => { e.stopPropagation(); handleDelete(col.id); }}
                      title={deleteConfirm === col.id ? "もう一度クリックで削除" : "削除"}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                  {col.description && (
                    <p className="text-[9px] text-gray-400 truncate mb-1">{col.description}</p>
                  )}
                  <div className="flex items-center gap-2">
                    <p className="text-[10px] text-gray-500">{col.ad_count}件の広告</p>
                    {col.created_at && (
                      <p className="text-[8px] text-gray-400">
                        {new Date(col.created_at).toLocaleDateString("ja-JP", { month: "short", day: "numeric" })}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        /* ─── Bookmarks Tab ─── */
        <>
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
            </svg>
            <h3 className="text-[13px] font-bold text-gray-900">ブックマーク済み広告</h3>
            <span className="text-[9px] text-gray-400">{bookmarks.length}件</span>
          </div>

          {bookmarksLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="card animate-pulse">
                  <div className="aspect-video bg-gray-100 rounded-lg mb-2" />
                  <div className="h-3 bg-gray-200 rounded w-24 mb-1" />
                  <div className="h-2.5 bg-gray-100 rounded w-16" />
                </div>
              ))}
            </div>
          ) : bookmarks.length === 0 ? (
            <div className="card px-4 py-10 text-center">
              <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
              <p className="text-[12px] text-gray-500 mb-1">ブックマークがありません</p>
              <p className="text-[10px] text-gray-400">広告の詳細画面からブックマークできます</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {bookmarks.map(renderAdCard)}
            </div>
          )}
        </>
      )}
    </div>
  );

  /* ─── Full-page wrapper ─── */
  if (fullPage) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center px-5 py-3 border-b border-gray-200 bg-white">
          <h2 className="text-[15px] font-bold text-gray-900">マイリスト</h2>
          <p className="text-[11px] text-gray-400 ml-3">コレクションとブックマークを管理</p>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-4">
          {mainContent}
        </div>
      </div>
    );
  }

  return (
    <>
      {mainContent}
      <SharedCollectionCreator
        isOpen={showSharedCreator}
        onClose={() => setShowSharedCreator(false)}
        onSave={(col) => {
          setShowSharedCreator(false);
          handleCreate();
          toast.success(`共有コレクション「${col.name}」を作成しました`);
          loadCollections();
        }}
      />
    </>
  );
}
