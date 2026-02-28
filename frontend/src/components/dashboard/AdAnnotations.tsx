"use client";

import React, { useState, useEffect, useCallback } from "react";

// ─── Types ───

type NoteTag = "学び" | "アイデア" | "要注意" | "参考";

interface Annotation {
  id: string;
  text: string;
  tag: NoteTag;
  createdAt: string;
}

interface AdAnnotationsProps {
  adId: number;
}

// ─── Constants ───

const TAG_OPTIONS: { value: NoteTag; label: string; color: string; bg: string }[] = [
  { value: "学び", label: "学び", color: "text-blue-700", bg: "bg-blue-100" },
  { value: "アイデア", label: "アイデア", color: "text-purple-700", bg: "bg-purple-100" },
  { value: "要注意", label: "要注意", color: "text-red-700", bg: "bg-red-100" },
  { value: "参考", label: "参考", color: "text-green-700", bg: "bg-green-100" },
];

// ─── localStorage helpers ───

function storageKey(adId: number): string {
  return `ad_annotations_${adId}`;
}

function loadNotes(adId: number): Annotation[] {
  try {
    const raw = localStorage.getItem(storageKey(adId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistNotes(adId: number, notes: Annotation[]): void {
  try {
    localStorage.setItem(storageKey(adId), JSON.stringify(notes));
  } catch {
    /* storage full – silently ignore */
  }
}

// ─── Helpers ───

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ─── Component ───

export default function AdAnnotations({ adId }: AdAnnotationsProps) {
  const [notes, setNotes] = useState<Annotation[]>([]);
  const [text, setText] = useState("");
  const [tag, setTag] = useState<NoteTag>("学び");

  useEffect(() => {
    setNotes(loadNotes(adId));
  }, [adId]);

  const handleAdd = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const note: Annotation = {
      id: `n_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      text: trimmed,
      tag,
      createdAt: new Date().toISOString(),
    };
    const updated = [note, ...notes];
    setNotes(updated);
    persistNotes(adId, updated);
    setText("");
  }, [adId, text, tag, notes]);

  const handleDelete = useCallback(
    (id: string) => {
      const updated = notes.filter((n) => n.id !== id);
      setNotes(updated);
      persistNotes(adId, updated);
    },
    [adId, notes],
  );

  const tagInfo = (t: NoteTag) => TAG_OPTIONS.find((o) => o.value === t) ?? TAG_OPTIONS[0];

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-100 bg-[#f8f9fc]">
        <h4 className="text-[12px] font-bold text-gray-900">メモ・注釈</h4>
        <p className="text-[10px] text-gray-400">この広告に関するメモを追加できます</p>
      </div>

      {/* Add note form */}
      <div className="px-4 py-3 border-b border-gray-100">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="メモを入力..."
          className="w-full text-[11px] border border-gray-200 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
        />
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1">
            {TAG_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setTag(opt.value)}
                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                  tag === opt.value
                    ? `${opt.bg} ${opt.color} ring-1 ring-current`
                    : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button
            onClick={handleAdd}
            disabled={!text.trim()}
            className="px-3 py-1 text-[10px] font-medium text-white bg-[#4A7DFF] rounded hover:bg-[#3d6ce0] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            追加
          </button>
        </div>
      </div>

      {/* Notes list */}
      <div className="max-h-[280px] overflow-y-auto divide-y divide-gray-100">
        {notes.length === 0 ? (
          <div className="px-4 py-6 text-center text-[10px] text-gray-400">まだメモがありません</div>
        ) : (
          notes.map((note) => {
            const ti = tagInfo(note.tag);
            return (
              <div key={note.id} className="px-4 py-2.5 hover:bg-gray-50 group">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${ti.bg} ${ti.color}`}>
                    {note.tag}
                  </span>
                  <span className="text-[9px] text-gray-400">{formatTimestamp(note.createdAt)}</span>
                  <button
                    onClick={() => handleDelete(note.id)}
                    className="ml-auto text-[9px] text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    削除
                  </button>
                </div>
                <p className="text-[11px] text-gray-700 whitespace-pre-wrap leading-relaxed">{note.text}</p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
