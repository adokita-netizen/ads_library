"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface DatabaseStatus {
  in_memory_mode: boolean;
  connection_error: string | null;
}

export default function DatabaseSettings() {
  const [status, setStatus] = useState<DatabaseStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [databaseUrl, setDatabaseUrl] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  const loadStatus = async () => {
    try {
      const data = await fetchApi<DatabaseStatus>("/settings/database/status");
      setStatus(data);
    } catch {
      setStatus({ in_memory_mode: true, connection_error: "バックエンドに接続できません" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleConnect = async () => {
    if (!databaseUrl.trim()) return;
    setConnecting(true);
    setMessage(null);
    try {
      const result = await fetchApi<{ status: string; message: string }>("/settings/database/connect", {
        method: "POST",
        body: { database_url: databaseUrl.trim() },
      });
      if (result.status === "ok") {
        setMessage({ type: "success", text: result.message });
        setDatabaseUrl("");
        await loadStatus();
      } else {
        setMessage({ type: "error", text: result.message });
      }
    } catch (err) {
      setMessage({ type: "error", text: "接続に失敗しました。バックエンドサーバーを確認してください。" });
    } finally {
      setConnecting(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
          <span className="text-xs text-gray-400">データベース状態を確認中...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-[14px] font-bold text-gray-900 mb-1">データベース接続</h3>
        <p className="text-[11px] text-gray-400 mb-4">PostgreSQL の接続設定</p>

        {/* Status indicator */}
        {status?.in_memory_mode ? (
          <div className="space-y-3">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                <span className="text-[13px] font-bold text-amber-800">インメモリモード</span>
              </div>
              <p className="text-[12px] text-amber-700">
                現在インメモリモードで動作中です。データはサーバー再起動時に失われます。
                永続化するにはPostgreSQLのDATABASE_URLを設定してください。
              </p>
            </div>

            {status.connection_error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-[12px] text-red-700">{status.connection_error}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-[13px] font-bold text-emerald-800">PostgreSQL 接続済み</span>
            </div>
            <p className="text-[12px] text-emerald-700 mt-1">データベースに正常に接続されています。</p>
          </div>
        )}
      </div>

      {/* Connection form */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <label className="block text-[12px] font-semibold text-gray-700 mb-1">DATABASE_URL</label>
        <p className="text-[11px] text-gray-400 mb-2">
          RDS エンドポイントを含む PostgreSQL 接続 URL を入力してください。
        </p>
        <div className="flex gap-2">
          <input
            type="password"
            value={databaseUrl}
            onChange={(e) => setDatabaseUrl(e.target.value)}
            placeholder="postgresql://vaap:password@your-rds-endpoint.ap-northeast-1.rds.amazonaws.com:5432/vaap_db"
            className="flex-1 px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF] font-mono"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleConnect();
            }}
          />
          <button
            onClick={handleConnect}
            disabled={connecting || !databaseUrl.trim()}
            className="px-4 py-2 text-[12px] font-medium bg-[#4A7DFF] text-white rounded-lg hover:bg-[#3a6ae6] disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {connecting ? (
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                接続中...
              </span>
            ) : (
              "接続して保存"
            )}
          </button>
        </div>

        {/* Message */}
        {message && (
          <div
            className={`mt-3 px-3 py-2 rounded text-xs ${
              message.type === "success"
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : message.type === "info"
                ? "bg-blue-50 text-blue-700 border border-blue-200"
                : "bg-red-50 text-red-700 border border-red-200"
            }`}
          >
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}
