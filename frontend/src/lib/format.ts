/** Copy text to clipboard with fallback for older browsers. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  }
}

/** Format a number with Japanese suffixes (万, 億). */
export function formatNumber(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return (n / 10000).toFixed(0) + "万";
  return n.toLocaleString();
}

/** Format a number as Japanese Yen with suffixes (万, 億). */
export function formatYen(n: number): string {
  if (n >= 100000000) return "¥" + (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return "¥" + (n / 10000).toFixed(0) + "万";
  return "¥" + n.toLocaleString();
}
