"use client";

import { useState } from "react";
import ConfirmModal from "@/components/common/ConfirmModal";

interface Props {
  currentStatus: string;
  entityType: "campaign" | "ad-set" | "ad";
  entityName: string;
  onStatusChange: (newStatus: string) => Promise<void>;
}

export default function StatusToggle({ currentStatus, entityType, entityName, onStatusChange }: Props) {
  const [updating, setUpdating] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const isActive = currentStatus === "ACTIVE";
  const targetStatus = isActive ? "PAUSED" : "ACTIVE";

  const entityTypeLabel = entityType === "campaign" ? "キャンペーン" : entityType === "ad-set" ? "広告セット" : "広告";

  const handleConfirm = async () => {
    setShowConfirm(false);
    setUpdating(true);
    try {
      await onStatusChange(targetStatus);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setShowConfirm(true)}
        disabled={updating || currentStatus === "DELETED" || currentStatus === "ARCHIVED"}
        className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-lg transition-colors disabled:opacity-50 ${
          isActive
            ? "bg-green-50 text-green-700 hover:bg-green-100"
            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
        }`}
        title={`${entityTypeLabel}を${isActive ? "停止" : "有効化"}`}
      >
        <span className={`w-2 h-2 rounded-full ${isActive ? "bg-green-500" : "bg-gray-400"}`} />
        {updating ? "変更中..." : isActive ? "ACTIVE" : "PAUSED"}
      </button>
      {showConfirm && (
        <ConfirmModal
          title={`${entityTypeLabel}のステータス変更`}
          message={
            isActive
              ? `「${entityName}」を停止してもよろしいですか？`
              : `「${entityName}」を有効にしてもよろしいですか？配信が開始されます。`
          }
          confirmLabel={isActive ? "停止する" : "有効にする"}
          variant={isActive ? "warning" : "info"}
          onConfirm={handleConfirm}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </>
  );
}
