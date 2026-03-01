"use client";

/**
 * Unified loading / empty / error state display components.
 * B45: CI-019 — consistent state UI across all views.
 */

interface LoadingSpinnerProps {
  /** Optional label. Defaults to "読み込み中..." */
  label?: string;
  /** Size variant */
  size?: "sm" | "md" | "lg";
}

export function LoadingSpinner({ label = "読み込み中...", size = "md" }: LoadingSpinnerProps) {
  const dim = size === "sm" ? "h-4 w-4" : size === "lg" ? "h-8 w-8" : "h-5 w-5";
  const textSize = size === "sm" ? "text-[10px]" : size === "lg" ? "text-[13px]" : "text-[11px]";
  return (
    <div className="flex items-center justify-center gap-2 py-4">
      <div className={`${dim} animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent`} />
      {label && <span className={`${textSize} text-gray-400`}>{label}</span>}
    </div>
  );
}

interface FullPageLoaderProps {
  label?: string;
}

/** Centered spinner for full-view loading */
export function FullPageLoader({ label = "読み込み中..." }: FullPageLoaderProps) {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[300px]">
      <LoadingSpinner label={label} size="lg" />
    </div>
  );
}

interface SkeletonRowsProps {
  rows?: number;
  cols?: number;
}

/** Table skeleton shimmer rows */
export function SkeletonRows({ rows = 5, cols = 5 }: SkeletonRowsProps) {
  return (
    <>
      {Array.from({ length: rows }).map((_, ri) => (
        <tr key={ri} className="animate-pulse">
          {Array.from({ length: cols }).map((_, ci) => (
            <td key={ci} className="px-3 py-3">
              <div className="h-3 bg-gray-200 rounded" style={{ width: `${50 + ((ci * 17) % 40)}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

interface SkeletonCardsProps {
  count?: number;
}

/** Card skeleton shimmer */
export function SkeletonCards({ count = 4 }: SkeletonCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="animate-pulse rounded-lg border border-gray-200 p-4 space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-8 bg-gray-100 rounded w-1/2" />
          <div className="h-3 bg-gray-100 rounded w-full" />
        </div>
      ))}
    </div>
  );
}

interface EmptyStateProps {
  /** Main message */
  message?: string;
  /** Secondary guidance text */
  description?: string;
  /** Optional CTA label */
  actionLabel?: string;
  /** CTA handler */
  onAction?: () => void;
  /** Icon type */
  icon?: "search" | "data" | "chart" | "document" | "bell";
}

const emptyIcons: Record<string, JSX.Element> = {
  data: (
    <svg className="w-10 h-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
    </svg>
  ),
  search: (
    <svg className="w-10 h-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
    </svg>
  ),
  chart: (
    <svg className="w-10 h-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  ),
  document: (
    <svg className="w-10 h-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  ),
  bell: (
    <svg className="w-10 h-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
    </svg>
  ),
};

export function EmptyState({
  message = "データがありません",
  description,
  actionLabel,
  onAction,
  icon = "data",
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {emptyIcons[icon]}
      <p className="mt-3 text-[13px] font-medium text-gray-500">{message}</p>
      {description && <p className="mt-1 text-[11px] text-gray-400 max-w-xs">{description}</p>}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-4 px-4 py-1.5 text-[12px] font-medium text-white bg-[#4A7DFF] rounded-lg hover:bg-[#3a6de8] transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

interface ErrorStateProps {
  /** Error message to display */
  message?: string;
  /** Retry handler */
  onRetry?: () => void;
  /** Compact mode for inline use */
  compact?: boolean;
}

export function ErrorState({
  message = "データの読み込みに失敗しました",
  onRetry,
  compact = false,
}: ErrorStateProps) {
  if (compact) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
        <svg className="w-4 h-4 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
        <span className="text-[11px] text-amber-800 flex-1">{message}</span>
        {onRetry && (
          <button onClick={onRetry} className="text-[11px] font-medium text-amber-700 underline hover:text-amber-900 shrink-0">
            再試行
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
      </div>
      <p className="text-[13px] font-medium text-gray-700">{message}</p>
      <p className="mt-1 text-[11px] text-gray-400">ネットワーク接続を確認してもう一度お試しください</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-1.5 text-[12px] font-medium text-[#4A7DFF] border border-[#4A7DFF] rounded-lg hover:bg-[#EEF2FF] transition-colors"
        >
          再試行
        </button>
      )}
    </div>
  );
}
