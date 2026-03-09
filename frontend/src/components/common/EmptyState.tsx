"use client";

type EmptyIcon = "search" | "chart" | "image" | "video" | "alert" | "collection";

interface EmptyStateProps {
  icon: EmptyIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  showDemo?: boolean;
  onDemo?: () => void;
}

function Icon({ icon }: { icon: EmptyIcon }) {
  switch (icon) {
    case "search":
      return <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.35-4.35m0 0A7.5 7.5 0 1 0 6.04 6.04a7.5 7.5 0 0 0 10.61 10.61Z" />;
    case "chart":
      return <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18M7 14v4m5-8v8m5-12v12" />;
    case "image":
      return <path strokeLinecap="round" strokeLinejoin="round" d="M3 6.75A2.25 2.25 0 0 1 5.25 4.5h13.5A2.25 2.25 0 0 1 21 6.75v10.5A2.25 2.25 0 0 1 18.75 19.5H5.25A2.25 2.25 0 0 1 3 17.25V6.75Zm5.25 3.75h.008v.008H8.25V10.5Zm12.75 5.25-4.5-4.5-6.75 6.75" />;
    case "video":
      return <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5 21 7.5v9l-5.25-3v1.5A2.25 2.25 0 0 1 13.5 18h-9A2.25 2.25 0 0 1 2.25 15.75v-7.5A2.25 2.25 0 0 1 4.5 6h9a2.25 2.25 0 0 1 2.25 2.25v2.25Z" />;
    case "alert":
      return <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4.5m0 3h.008v.008H12V16.5ZM10.34 3.84 1.89 18.11A1.5 1.5 0 0 0 3.18 20.4h17.64a1.5 1.5 0 0 0 1.29-2.29L13.66 3.84a1.5 1.5 0 0 0-2.58 0Z" />;
    case "collection":
      return <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 7.5h16.5M6 4.5h12m-9 6.75h6m-9 4.5h12" />;
    default:
      return null;
  }
}

export default function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  showDemo,
  onDemo,
}: EmptyStateProps) {
  return (
    <div className="px-6 py-10 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-gray-100 text-gray-500">
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
          <Icon icon={icon} />
        </svg>
      </div>
      <p className="text-[13px] font-semibold text-gray-800">{title}</p>
      <p className="mt-1 text-[12px] text-gray-500">{description}</p>
      {(actionLabel || showDemo) && (
        <div className="mt-4 flex items-center justify-center gap-2">
          {actionLabel && onAction && (
            <button
              type="button"
              onClick={onAction}
              className="rounded-lg bg-[#4A7DFF] px-3 py-1.5 text-[11px] font-medium text-white hover:bg-[#3A6AEE]"
            >
              {actionLabel}
            </button>
          )}
          {showDemo && (
            <button
              type="button"
              onClick={onDemo}
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-[11px] font-medium text-gray-700 hover:bg-gray-50"
            >
              Show Demo Data
            </button>
          )}
        </div>
      )}
    </div>
  );
}
