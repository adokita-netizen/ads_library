"use client";

import React, { useState, useCallback } from "react";

// ─── Types ───

interface SharedCollectionCreatorProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (collection: { name: string; description: string; tags: string[] }) => void;
}

// ─── Constants ───

const AVAILABLE_TAGS = ["美容", "健康", "EC", "ダイエット", "金融", "教育", "食品", "アパレル"];

// ─── Component ───

export default function SharedCollectionCreator({ isOpen, onClose, onSave }: SharedCollectionCreatorProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [visibility, setVisibility] = useState<"private" | "team">("private");

  const handleTagToggle = useCallback((tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    );
  }, []);

  const handleSave = useCallback(() => {
    if (!name.trim()) return;
    onSave({ name: name.trim(), description: description.trim(), tags: selectedTags });

    // localStorage fallback
    try {
      const existing = JSON.parse(localStorage.getItem("shared_collections") || "[]");
      existing.push({
        id: `col_${Date.now()}`,
        name: name.trim(),
        description: description.trim(),
        tags: selectedTags,
        visibility,
        createdAt: new Date().toISOString(),
      });
      localStorage.setItem("shared_collections", JSON.stringify(existing));
    } catch {
      /* silently ignore */
    }

    setName("");
    setDescription("");
    setSelectedTags([]);
    setVisibility("private");
    onClose();
  }, [name, description, selectedTags, visibility, onSave, onClose]);

  const handleCancel = useCallback(() => {
    setName("");
    setDescription("");
    setSelectedTags([]);
    setVisibility("private");
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={handleCancel}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
          <h3 className="text-[14px] font-bold text-gray-900">新規コレクション作成</h3>
          <button onClick={handleCancel} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Collection Name */}
          <div>
            <label className="block text-[11px] font-medium text-gray-700 mb-1">コレクション名 *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例: 美容系ヒット広告コレクション"
              className="w-full text-[11px] border border-gray-200 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-[11px] font-medium text-gray-700 mb-1">説明</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="このコレクションの目的や説明を入力..."
              rows={2}
              className="w-full text-[11px] border border-gray-200 rounded-lg px-3 py-2 text-gray-700 resize-none focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
            />
          </div>

          {/* Tags */}
          <div>
            <label className="block text-[11px] font-medium text-gray-700 mb-1">タグ</label>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_TAGS.map((tag) => (
                <button
                  key={tag}
                  onClick={() => handleTagToggle(tag)}
                  className={`px-2.5 py-1 rounded text-[10px] font-medium transition-colors ${
                    selectedTags.includes(tag)
                      ? "bg-[#4A7DFF] text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          {/* Visibility */}
          <div>
            <label className="block text-[11px] font-medium text-gray-700 mb-1">公開範囲</label>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="visibility"
                  checked={visibility === "private"}
                  onChange={() => setVisibility("private")}
                  className="w-3 h-3 accent-[#4A7DFF]"
                />
                <span className="text-[11px] text-gray-700">自分のみ</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="visibility"
                  checked={visibility === "team"}
                  onChange={() => setVisibility("team")}
                  className="w-3 h-3 accent-[#4A7DFF]"
                />
                <span className="text-[11px] text-gray-700">チーム全体</span>
              </label>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <button
            onClick={handleCancel}
            className="px-4 py-1.5 text-[11px] font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            キャンセル
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim()}
            className="px-4 py-1.5 text-[11px] font-medium text-white bg-[#4A7DFF] rounded-lg hover:bg-[#3d6ce0] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
