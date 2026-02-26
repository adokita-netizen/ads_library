"use client";

import { useEffect, useRef, useCallback } from "react";

interface ConfirmModalProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "info";
  onConfirm: () => void;
  onCancel: () => void;
}

const VARIANT_STYLES = {
  danger: {
    icon: "text-red-500",
    button: "bg-red-500 hover:bg-red-600 text-white",
  },
  warning: {
    icon: "text-amber-500",
    button: "bg-amber-500 hover:bg-amber-600 text-white",
  },
  info: {
    icon: "text-blue-500",
    button: "bg-blue-500 hover:bg-blue-600 text-white",
  },
};

export default function ConfirmModal({
  title,
  message,
  confirmLabel = "確認",
  cancelLabel = "キャンセル",
  variant = "info",
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const styles = VARIANT_STYLES[variant];

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
        return;
      }
      // Focus trap
      if (e.key === "Tab" && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [onCancel]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    confirmRef.current?.focus();
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onCancel}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-modal-title"
    >
      <div
        ref={modalRef}
        className="bg-white rounded-xl shadow-xl w-full max-w-sm p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-modal-title" className="text-[14px] font-bold text-gray-900 mb-2">
          {title}
        </h3>
        <p className="text-[12px] text-gray-600 mb-5">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="text-[12px] px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            className={`text-[12px] px-4 py-2 rounded-lg ${styles.button}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
