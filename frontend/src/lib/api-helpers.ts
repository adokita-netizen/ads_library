/**
 * Extract items from API responses that may use different key names.
 * Handles `.items`, `.rankings`, or `.results` conventions.
 */
export function extractItems<T = Record<string, unknown>>(
  data: { items?: T[]; rankings?: T[]; results?: T[] } | null | undefined
): T[] {
  if (!data) return [];
  return data.items ?? data.rankings ?? data.results ?? [];
}
