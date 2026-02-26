"use client";

import { useState, useEffect, useCallback } from "react";
import { campaignsApi, adsApi } from "@/lib/api";
import { platformLabels, platformBadgeColors } from "@/lib/constants";
import type { Campaign, CampaignDetail, CampaignAdItem } from "@/types";

interface CampaignGalleryViewProps {
  onAdSelect: (adId: number) => void;
}

export default function CampaignGalleryView({ onAdSelect }: CampaignGalleryViewProps) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<CampaignDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  // Add ad form
  const [showAddAd, setShowAddAd] = useState(false);
  const [addAdId, setAddAdId] = useState("");
  const [addingAd, setAddingAd] = useState(false);
  // Video lightbox
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  // Edit campaign
  const [editingCampaign, setEditingCampaign] = useState<number | null>(null);
  const [editName, setEditName] = useState("");

  const fetchCampaigns = useCallback(async () => {
    try {
      const res = await campaignsApi.list();
      const data = res.data;
      setCampaigns(data?.campaigns || []);
    } catch (err) {
      console.error("Failed to fetch campaigns:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  const handleSelectCampaign = async (id: number) => {
    setDetailLoading(true);
    try {
      const res = await campaignsApi.getDetail(id);
      setSelectedCampaign(res.data);
    } catch (err) {
      console.error("Failed to fetch campaign detail:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await campaignsApi.create({ name: newName.trim(), description: newDesc.trim() || undefined });
      setNewName("");
      setNewDesc("");
      setShowCreateForm(false);
      await fetchCampaigns();
    } catch (err) {
      console.error("Failed to create campaign:", err);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await campaignsApi.delete(id);
      if (selectedCampaign?.id === id) setSelectedCampaign(null);
      await fetchCampaigns();
    } catch (err) {
      console.error("Failed to delete campaign:", err);
    }
  };

  const handleAddAd = async () => {
    if (!selectedCampaign || !addAdId.trim()) return;
    setAddingAd(true);
    try {
      await campaignsApi.addAd(selectedCampaign.id, { ad_id: parseInt(addAdId, 10) });
      setAddAdId("");
      setShowAddAd(false);
      await handleSelectCampaign(selectedCampaign.id);
      await fetchCampaigns();
    } catch (err) {
      console.error("Failed to add ad:", err);
    } finally {
      setAddingAd(false);
    }
  };

  const handleRemoveAd = async (adId: number) => {
    if (!selectedCampaign) return;
    try {
      await campaignsApi.removeAd(selectedCampaign.id, adId);
      await handleSelectCampaign(selectedCampaign.id);
      await fetchCampaigns();
    } catch (err) {
      console.error("Failed to remove ad:", err);
    }
  };

  const handleRename = async (id: number) => {
    if (!editName.trim()) return;
    try {
      await campaignsApi.update(id, { name: editName.trim() });
      setEditingCampaign(null);
      setEditName("");
      await fetchCampaigns();
      if (selectedCampaign?.id === id) {
        setSelectedCampaign((prev) => prev ? { ...prev, name: editName.trim() } : prev);
      }
    } catch (err) {
      console.error("Failed to rename campaign:", err);
    }
  };

  const getThumbnail = (ad: CampaignAdItem): string | null => {
    return ad.thumbnail_url || ad.image_url || ad.snapshot_url || null;
  };

  // Campaign list mode
  if (!selectedCampaign) {
    return (
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
          <div>
            <h2 className="text-[15px] font-bold text-gray-900">キャンペーン</h2>
            <p className="text-[11px] text-gray-400">キャンペーンごとに広告クリエイティブを管理・確認</p>
          </div>
          <button className="btn-primary text-xs" onClick={() => setShowCreateForm(true)}>
            <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            新規作成
          </button>
        </div>

        <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4">
          {/* Create form */}
          {showCreateForm && (
            <div className="card mb-4 border border-[#4A7DFF]/20">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">新しいキャンペーンを作成</h3>
              <div className="space-y-2">
                <input
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/20 focus:border-[#4A7DFF]"
                  placeholder="キャンペーン名"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
                <textarea
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/20 focus:border-[#4A7DFF] resize-none"
                  placeholder="説明（任意）"
                  rows={2}
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
                <div className="flex items-center gap-2">
                  <button className="btn-primary text-xs" onClick={handleCreate} disabled={creating || !newName.trim()}>
                    {creating ? "作成中..." : "作成"}
                  </button>
                  <button className="btn-secondary text-xs" onClick={() => { setShowCreateForm(false); setNewName(""); setNewDesc(""); }}>
                    キャンセル
                  </button>
                </div>
              </div>
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
              <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
            </div>
          )}

          {!loading && campaigns.length === 0 && (
            <div className="text-center py-16 text-gray-400">
              <svg className="w-10 h-10 mx-auto mb-3 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <p className="text-xs">キャンペーンがまだありません</p>
              <p className="text-[10px] mt-1">「新規作成」からキャンペーンを作成してください</p>
            </div>
          )}

          {/* Campaign Grid */}
          {!loading && campaigns.length > 0 && (
            <div className="grid grid-cols-3 gap-3">
              {campaigns.map((c) => (
                <div
                  key={c.id}
                  className="card cursor-pointer hover:shadow-md transition-shadow group relative"
                  onClick={() => handleSelectCampaign(c.id)}
                >
                  {/* Actions */}
                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                    <button
                      className="w-6 h-6 rounded flex items-center justify-center hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                      onClick={(e) => { e.stopPropagation(); setEditingCampaign(c.id); setEditName(c.name); }}
                      title="名前変更"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487z" />
                      </svg>
                    </button>
                    <button
                      className="w-6 h-6 rounded flex items-center justify-center hover:bg-red-50 text-gray-400 hover:text-red-500"
                      onClick={(e) => { e.stopPropagation(); handleDelete(c.id); }}
                      title="削除"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>

                  {/* Rename inline */}
                  {editingCampaign === c.id ? (
                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        className="flex-1 rounded border border-gray-200 px-2 py-1 text-[12px] focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/20"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") handleRename(c.id); if (e.key === "Escape") setEditingCampaign(null); }}
                        autoFocus
                      />
                      <button className="text-[10px] text-[#4A7DFF] font-medium" onClick={() => handleRename(c.id)}>保存</button>
                    </div>
                  ) : (
                    <h3 className="text-[13px] font-bold text-gray-900 truncate pr-16">{c.name}</h3>
                  )}
                  {c.description && <p className="text-[10px] text-gray-400 mt-0.5 truncate">{c.description}</p>}
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-[11px] text-gray-500">{c.ad_count}件の広告</span>
                    <span className="text-[10px] text-gray-400">{new Date(c.created_at).toLocaleDateString("ja-JP")}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Campaign detail / gallery mode
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <button
            className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
            onClick={() => setSelectedCampaign(null)}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <div>
            <h2 className="text-[15px] font-bold text-gray-900">{selectedCampaign.name}</h2>
            {selectedCampaign.description && (
              <p className="text-[11px] text-gray-400">{selectedCampaign.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-primary text-xs" onClick={() => setShowAddAd(true)}>
            <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            広告を追加
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4">
        {/* Add ad form */}
        {showAddAd && (
          <div className="card mb-4 border border-[#4A7DFF]/20">
            <h3 className="text-[13px] font-bold text-gray-900 mb-2">広告を追加</h3>
            <div className="flex items-center gap-2">
              <input
                className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-[12px] focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/20 focus:border-[#4A7DFF]"
                placeholder="広告ID（数値）"
                value={addAdId}
                onChange={(e) => setAddAdId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddAd()}
                type="number"
              />
              <button className="btn-primary text-xs" onClick={handleAddAd} disabled={addingAd || !addAdId.trim()}>
                {addingAd ? "追加中..." : "追加"}
              </button>
              <button className="btn-secondary text-xs" onClick={() => { setShowAddAd(false); setAddAdId(""); }}>
                キャンセル
              </button>
            </div>
          </div>
        )}

        {detailLoading && (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
            <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
          </div>
        )}

        {!detailLoading && selectedCampaign.ads.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <svg className="w-10 h-10 mx-auto mb-3 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
            </svg>
            <p className="text-xs">このキャンペーンにはまだ広告がありません</p>
            <p className="text-[10px] mt-1">「広告を追加」から広告IDで追加してください</p>
          </div>
        )}

        {/* Ad Gallery Grid */}
        {!detailLoading && selectedCampaign.ads.length > 0 && (
          <div className="grid grid-cols-4 gap-3">
            {selectedCampaign.ads.map((ad) => {
              const thumb = getThumbnail(ad);
              const isVideo = ad.creative_type === "video";
              return (
                <div
                  key={ad.id}
                  className="card p-0 overflow-hidden cursor-pointer hover:shadow-md transition-shadow group"
                  onClick={() => onAdSelect(ad.ad_id)}
                >
                  {/* Thumbnail */}
                  <div className="relative w-full h-[150px] bg-gray-100">
                    {thumb ? (
                      <img src={thumb} alt={ad.title || ""} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-300">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                        </svg>
                      </div>
                    )}
                    {/* Video play overlay */}
                    {isVideo && ad.video_url && (
                      <button
                        className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => { e.stopPropagation(); setLightboxUrl(ad.video_url!); }}
                      >
                        <div className="w-10 h-10 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
                          <svg className="w-5 h-5 text-gray-700 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M8 5.14v14l11-7-11-7z" />
                          </svg>
                        </div>
                      </button>
                    )}
                    {/* Platform badge */}
                    {ad.platform && (
                      <span className={`absolute top-1.5 left-1.5 badge text-[9px] ${platformBadgeColors[ad.platform] || "bg-gray-100 text-gray-700"}`}>
                        {platformLabels[ad.platform] || ad.platform}
                      </span>
                    )}
                    {/* Creative type badge */}
                    {ad.creative_type && (
                      <span className="absolute top-1.5 right-1.5 badge text-[8px] bg-black/50 text-white">
                        {ad.creative_type === "video" ? "動画" : ad.creative_type === "image" ? "静止画" : ad.creative_type}
                      </span>
                    )}
                  </div>
                  {/* Card info */}
                  <div className="p-2.5">
                    <p className="text-[11px] font-medium text-gray-900 truncate">{ad.title || `広告 #${ad.ad_id}`}</p>
                    <p className="text-[10px] text-gray-400 truncate">{ad.advertiser_name || "-"}</p>
                    <div className="flex items-center justify-between mt-1.5">
                      {ad.duration_seconds ? (
                        <span className="text-[10px] text-gray-400">{Math.round(ad.duration_seconds)}秒</span>
                      ) : <span />}
                      {/* Remove button */}
                      <button
                        className="text-[10px] text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => { e.stopPropagation(); handleRemoveAd(ad.ad_id); }}
                        title="キャンペーンから削除"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Video Lightbox */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70"
          onClick={() => setLightboxUrl(null)}
        >
          <div className="relative max-w-3xl w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <button
              className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors"
              onClick={() => setLightboxUrl(null)}
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <video
              src={lightboxUrl}
              controls
              autoPlay
              className="w-full rounded-lg shadow-2xl"
            />
          </div>
        </div>
      )}
    </div>
  );
}
