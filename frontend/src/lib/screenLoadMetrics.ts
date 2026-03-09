export type ScreenLoadMetric = {
  count: number;
  latestMs: number;
  avgMs: number;
  maxMs: number;
};

export type ScreenLoadMetricsMap = Record<string, ScreenLoadMetric>;

export const SCREEN_LOAD_METRICS_STORAGE_KEY = "vaap-screen-load-metrics:v1";

export function formatScreenLoadMs(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "-";
  if (value < 1000) return `${Math.round(value)}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}

export function recordScreenLoadMetric(
  metrics: ScreenLoadMetricsMap,
  screen: string,
  elapsedMs: number,
): ScreenLoadMetricsMap {
  const normalizedMs = Number.isFinite(elapsedMs) && elapsedMs > 0 ? Math.round(elapsedMs) : 0;
  const prev = metrics[screen];
  const nextCount = (prev?.count || 0) + 1;
  const nextAvg = prev ? Math.round(((prev.avgMs * prev.count) + normalizedMs) / nextCount) : normalizedMs;

  return {
    ...metrics,
    [screen]: {
      count: nextCount,
      latestMs: normalizedMs,
      avgMs: nextAvg,
      maxMs: Math.max(prev?.maxMs || 0, normalizedMs),
    },
  };
}

export function getSlowestScreen(
  metrics: ScreenLoadMetricsMap,
): [string, ScreenLoadMetric] | null {
  const entries = Object.entries(metrics);
  if (entries.length === 0) return null;
  entries.sort((a, b) => b[1].latestMs - a[1].latestMs);
  return entries[0] || null;
}
