"use client";

import { useState } from "react";
import type { MetaCampaign } from "@/types";
import { metaMarketingApi } from "@/lib/api";
import StatusToggle from "./StatusToggle";
import CreateCampaignModal from "./CreateCampaignModal";

interface Props {
  campaigns: MetaCampaign[];
  onRefresh: () => void;
  accountId?: string;
  refreshing?: boolean;
  page?: number;
  total?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
}

export default function MetaCampaignTable({ campaigns, onRefresh, accountId, refreshing, page = 1, total = 0, pageSize = 20, onPageChange }: Props) {
  const [showCreateModal, setShowCreateModal] = useState(false);

  if (campaigns.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 mb-3">
          <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <p className="text-[13px] text-gray-600 font-medium mb-1">
          キャンペーンデータがありません
        </p>
        <p className="text-[11px] text-gray-400 mb-4">
          アカウントを接続してデータを同期するか、新規キャンペーンを作成してください
        </p>
        <div className="flex items-center justify-center gap-2">
          <button onClick={onRefresh} className="btn-secondary text-[11px] px-3 py-1.5">
            データを同期
          </button>
          {accountId && (
            <button onClick={() => setShowCreateModal(true)} className="btn-primary text-[11px] px-3 py-1.5">
              新規作成
            </button>
          )}
        </div>
        {showCreateModal && accountId && (
          <CreateCampaignModal
            accountId={accountId}
            onClose={() => setShowCreateModal(false)}
            onCreated={onRefresh}
          />
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-bold text-gray-800">キャンペーン ({campaigns.length})</h3>
        <div className="flex items-center gap-2">
          {accountId && (
            <button onClick={() => setShowCreateModal(true)} className="btn-primary text-[11px] px-3 py-1">
              新規作成
            </button>
          )}
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="btn-secondary text-[11px] px-3 py-1 disabled:opacity-50"
          >
            {refreshing ? (
              <span className="inline-flex items-center gap-1">
                <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                更新中...
              </span>
            ) : "更新"}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[12px]" aria-label="キャンペーン一覧">
          <thead>
            <tr className="border-b border-gray-200">
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">名前</th>
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">ステータス</th>
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">目的</th>
              <th scope="col" className="text-right py-2 px-3 text-gray-500 font-medium">日予算</th>
              <th scope="col" className="text-right py-2 px-3 text-gray-500 font-medium">残予算</th>
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">開始日</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-2 px-3">
                  <p className="font-medium text-gray-800">{c.name}</p>
                  <p className="text-[10px] text-gray-400">{c.meta_id}</p>
                </td>
                <td className="py-2 px-3">
                  <StatusToggle
                    currentStatus={c.effective_status}
                    entityType="campaign"
                    entityName={c.name}
                    onStatusChange={async (newStatus) => {
                      await metaMarketingApi.updateCampaignStatus(c.meta_id, { status: newStatus });
                      onRefresh();
                    }}
                  />
                </td>
                <td className="py-2 px-3 text-gray-600">{c.objective || "-"}</td>
                <td className="py-2 px-3 text-right text-gray-600">
                  {c.daily_budget ? `¥${Number(c.daily_budget).toLocaleString()}` : "-"}
                </td>
                <td className="py-2 px-3 text-right text-gray-600">
                  {c.budget_remaining ? `¥${Number(c.budget_remaining).toLocaleString()}` : "-"}
                </td>
                <td className="py-2 px-3 text-gray-500">
                  {c.start_time ? new Date(c.start_time).toLocaleDateString("ja-JP") : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > pageSize && onPageChange && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <span className="text-[11px] text-gray-400">
            全{total}件中 {(page - 1) * pageSize + 1}〜{Math.min(page * pageSize, total)}件
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="text-[11px] px-2 py-1 rounded border border-gray-200 disabled:opacity-30 hover:bg-gray-50"
            >
              前へ
            </button>
            <span className="text-[11px] px-2 py-1 text-gray-500">
              {page} / {Math.ceil(total / pageSize)}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= Math.ceil(total / pageSize)}
              className="text-[11px] px-2 py-1 rounded border border-gray-200 disabled:opacity-30 hover:bg-gray-50"
            >
              次へ
            </button>
          </div>
        </div>
      )}

      {showCreateModal && accountId && (
        <CreateCampaignModal
          accountId={accountId}
          onClose={() => setShowCreateModal(false)}
          onCreated={onRefresh}
        />
      )}
    </div>
  );
}
