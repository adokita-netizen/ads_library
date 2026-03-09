"use client";

import React from "react";

export type NumericProvenanceState = "real" | "estimated" | "missing" | "stale";

const badgeClassMap: Record<NumericProvenanceState, string> = {
  real: "bg-emerald-100 text-emerald-700",
  estimated: "bg-amber-100 text-amber-700",
  missing: "bg-gray-100 text-gray-500",
  stale: "bg-rose-100 text-rose-700",
};

const labelMap: Record<NumericProvenanceState, string> = {
  real: "実測",
  estimated: "推定",
  missing: "欠損",
  stale: "stale",
};

export function NumericProvenanceBadge({ state }: { state: NumericProvenanceState }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-medium ${badgeClassMap[state]}`}>
      {labelMap[state]}
    </span>
  );
}

export function NumericProvenanceNote({
  state,
  note,
}: {
  state: NumericProvenanceState;
  note?: string;
}) {
  if (!note) return null;
  const tone =
    state === "real"
      ? "text-emerald-700"
      : state === "estimated"
        ? "text-amber-700"
        : state === "stale"
          ? "text-rose-700"
          : "text-gray-500";
  return <p className={`mt-0.5 text-[9px] ${tone}`}>{note}</p>;
}

export function NumericProvenanceMetricCard({
  label,
  value,
  state,
  note,
  warning,
}: {
  label: string;
  value: React.ReactNode;
  state: NumericProvenanceState;
  note?: string;
  warning?: string;
}) {
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2.5">
      <div className="flex items-center gap-1.5">
        <p className="text-[10px] font-medium text-gray-400">{label}</p>
        <NumericProvenanceBadge state={state} />
      </div>
      <p className="mt-0.5 text-[15px] font-bold text-gray-900">{value}</p>
      <NumericProvenanceNote state={state} note={note} />
      {warning ? <p className="mt-1 text-[9px] text-rose-600">{warning}</p> : null}
    </div>
  );
}
